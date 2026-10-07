from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import Alert, Analytics, MaintenanceRecord, Telemetry
from app.repositories import alert_repo
from app.schemas.telemetry import TelemetryIn
from app.services import ingestion_service
from app.services.ingestion_service import ingest_batch, ingest_record

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def mixed(asset: str, index: int) -> TelemetryIn:
    phase = index % 30
    return TelemetryIn(
        transformer_id=asset,
        timestamp=BASE + timedelta(seconds=index),
        oil_temperature=None if phase >= 25 else 42,
        oil_level=None if phase == 29 else 8,
        oil_temp_alarm=int(8 <= phase < 13),
        oil_temp_trip=int(13 <= phase < 18),
        magnetic_oil_gauge_alarm=int(phase == 24),
        source_name="simulator",
        scenario_id="differential",
        current_l1=0,
        current_l2=0,
        current_l3=0,
        phase_voltage_l1=0,
        phase_voltage_l2=0,
        phase_voltage_l3=0,
    )


def snapshot(session: Session, asset: str) -> dict[str, list[dict[str, Any]]]:
    telemetry = list(session.scalars(select(Telemetry).where(Telemetry.transformer_id == asset)))
    analytics = list(session.scalars(select(Analytics).where(Analytics.transformer_id == asset)))
    references = {
        "telemetry_id": {row.id: row.timestamp for row in telemetry},
        "analytics_id": {row.id: row.timestamp for row in analytics},
    }
    output = {}
    for model in [Telemetry, Analytics, Alert, MaintenanceRecord]:
        values = []
        for row in session.scalars(select(model).where(model.transformer_id == asset)):
            value = {}
            for column in model.__table__.columns:
                if column.name in {"id", "created_at", "ingested_at", "transformer_id"}:
                    continue
                item = getattr(row, column.name)
                if column.name in references:
                    item = references[column.name].get(item)
                value[column.name] = item
            values.append(value)
        output[model.__tablename__] = sorted(values, key=repr)
    return output


@pytest.mark.parametrize("chunk_size", [37, 1000])
def test_500_mixed_rows_match_row_by_row_with_late_arrivals(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    chunk_size: int,
) -> None:
    monkeypatch.setattr(ingestion_service, "CHUNK_SIZE", chunk_size)
    assets = ["TX-diff-" + uuid4().hex for _ in range(2)]
    for asset in assets:
        ingest_record(db, mixed(asset, 313))
    # Descending arrival order contains late backfills relative to existing trip evidence.
    rows = [mixed(assets[0], index) for index in reversed(range(500))]
    result = ingest_batch(db, [row.model_dump(mode="json") for row in rows])
    assert result.inserted_count == 499 and result.duplicate_count == 1
    for index in range(500):
        row_result = ingest_record(db, mixed(assets[1], index))
        assert "ALERT_HOOK_FAILED" not in row_result.warnings
    assert snapshot(db, assets[0]) == snapshot(db, assets[1])
    records = snapshot(db, assets[0])
    assert any(row["status"] == "RESOLVED" for row in records["alerts"])
    assert any(row["clear_count"] for row in records["alerts"])
    assert {row["priority"] for row in records["maintenance_records"]} == {"PLAN", "URGENT"}


def test_duplicate_chunks_bypass_inference_hook_and_bulk_writes(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset = "TX-duplicates-" + uuid4().hex
    rows = [mixed(asset, index).model_dump(mode="json") for index in range(50)]
    ingest_batch(db, rows)

    def unexpected(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Duplicate must not reach inference, hook, insertion or history")

    for module, name in [
        (ingestion_service, "get_ml_client"),
        (ingestion_service.hooks, "evaluate_alerts"),
    ]:
        monkeypatch.setattr(module, name, unexpected)
    from app.repositories import analytics_repo, telemetry_repo

    monkeypatch.setattr(telemetry_repo, "insert_many", unexpected)
    monkeypatch.setattr(analytics_repo, "insert_many", unexpected)
    monkeypatch.setattr(telemetry_repo, "load_batch_history", unexpected)
    result = ingest_batch(db, rows + rows)
    assert result.inserted_count == 0 and result.duplicate_count == 100


def test_batch_repository_failure_preserves_telemetry_and_analytics(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = "TX-buffer-fail-" + uuid4().hex
    original = alert_repo.insert_active

    def broken(session: Session, values: dict[str, Any]) -> Any:
        if values["alert_type"] == "OIL_TEMP_TRIP":
            raise RuntimeError("repository failed")
        return original(session, values)

    monkeypatch.setattr(alert_repo, "insert_active", broken)
    rows = [mixed(asset, index).model_dump(mode="json") for index in range(40)]
    ingest_batch(db, rows)
    data = snapshot(db, asset)
    assert len(data["telemetry"]) == len(data["analytics"]) == 40
    assert not any(row["alert_type"] == "OIL_TEMP_TRIP" for row in data["alerts"])
    assert any(row["alert_type"] == "OIL_TEMP_ALARM" for row in data["alerts"])


def test_chunk_sql_count_does_not_grow_per_healthy_row(db: Session) -> None:
    asset = "TX-sql-" + uuid4().hex
    statements = []
    engine = db.get_bind()

    def count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        rows = [mixed(asset, index * 30).model_dump(mode="json") for index in range(100)]
        ingest_batch(db, rows)
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert len(statements) < 30
    assert sum("FOR NO KEY UPDATE" in statement for statement in statements) == 1
    assert (
        sum("SAVEPOINT" in statement and "RELEASE" not in statement for statement in statements) < 6
    )


def test_alert_conflicts_work_with_postgres_generic_prepared_plans(db: Session) -> None:
    from sqlalchemy import text

    connection = db.connection().connection.driver_connection
    prior_threshold = connection.prepare_threshold
    connection.prepare_threshold = 0
    try:
        db.execute(text("SET LOCAL plan_cache_mode = force_generic_plan"))
        asset = "TX-prepared-" + uuid4().hex
        for index in range(100):
            output = ingest_record(db, mixed(asset, index))
            assert "ALERT_HOOK_FAILED" not in output.warnings
    finally:
        connection.prepare_threshold = prior_threshold
