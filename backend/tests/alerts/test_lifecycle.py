from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.models import Alert, Analytics, MaintenanceRecord, Telemetry
from app.repositories import alert_repo
from app.schemas.telemetry import TelemetryIn
from app.services import hooks, ingestion_service
from app.services.ingestion_service import ingest_record
from tests.alerts.conftest import BASE, record, result


def alerts(db: Session, asset: str) -> dict[str, Alert]:
    return {
        row.alert_type: row
        for row in db.scalars(select(Alert).where(Alert.transformer_id == asset).order_by(Alert.id))
    }


def test_twenty_trips_dedupe_and_duplicate_skips_hook(
    db: Session,
    asset_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = Mock(wraps=hooks.evaluate_alerts)
    monkeypatch.setattr(hooks, "evaluate_alerts", spy)
    for second in range(20):
        output = ingest_record(db, record(asset_id, second, oil_temp_trip=1))
        assert "ALERT_HOOK_FAILED" not in output.warnings
    row = alerts(db, asset_id)["OIL_TEMP_TRIP"]
    assert row.status == "OPEN"
    assert row.timestamp == BASE
    assert row.last_seen_at == BASE + timedelta(seconds=19)
    assert row.evidence == {"oil_temp_trip": 1}
    assert row.clear_count == 0
    assert row.telemetry_id == output.telemetry_id
    assert row.analytics_id == db.scalar(
        select(Analytics.id).where(Analytics.telemetry_id == output.telemetry_id)
    )
    assert spy.call_count == 20
    duplicate = ingest_record(db, record(asset_id, 19, oil_temp_trip=1))
    assert duplicate.duplicate
    assert spy.call_count == 20


def test_escalation_never_downgrades_and_acknowledged_is_not_reraised(
    db: Session,
    alert_client: TestClient,
    asset_id: str,
) -> None:
    ingest_record(db, record(asset_id, oil_temp_alarm=1))
    initial = alerts(db, asset_id)
    ids = {kind: row.id for kind, row in initial.items()}
    assert initial["LOW_HEALTH_INDEX"].severity == "WARNING"
    assert (
        alert_client.patch(f"/api/v1/alerts/{ids['LOW_HEALTH_INDEX']}/acknowledge").status_code
        == 200
    )
    ingest_record(db, record(asset_id, 1, oil_temp_trip=1))
    ingest_record(db, record(asset_id, 2, oil_temp_alarm=1))
    rows = alerts(db, asset_id)
    for kind in ["ANOMALOUS_PATTERN", "LOW_HEALTH_INDEX", "PROXY_FAULT_RISK"]:
        assert rows[kind].id == ids[kind]
        assert rows[kind].severity == "CRITICAL"
    assert rows["LOW_HEALTH_INDEX"].status == "ACKNOWLEDGED"
    assert rows["LOW_HEALTH_INDEX"].evidence == {"health_index": 55.0}
    assert rows["LOW_HEALTH_INDEX"].last_seen_at == BASE + timedelta(seconds=2)


def test_auto_resolve_exactly_five_and_reset(db: Session, asset_id: str) -> None:
    ingest_record(db, record(asset_id, oil_temp_trip=1))
    for second in range(1, 5):
        ingest_record(db, record(asset_id, second))
        row = alerts(db, asset_id)["OIL_TEMP_TRIP"]
        assert row.clear_count == second
        assert row.status == "OPEN" and row.resolved_at is None
    ingest_record(db, record(asset_id, 5, oil_temp_trip=1))
    row = alerts(db, asset_id)["OIL_TEMP_TRIP"]
    assert row.clear_count == 0
    for second in range(6, 11):
        ingest_record(db, record(asset_id, second))
    row = alerts(db, asset_id)["OIL_TEMP_TRIP"]
    assert row.clear_count == 5 and row.status == "RESOLVED"
    assert row.resolved_at == BASE + timedelta(seconds=10)
    assert row.last_seen_at == BASE + timedelta(seconds=5)
    old_id = row.id
    ingest_record(db, record(asset_id, 11, oil_temp_trip=1))
    rows = list(
        db.scalars(
            select(Alert)
            .where(Alert.transformer_id == asset_id, Alert.alert_type == "OIL_TEMP_TRIP")
            .order_by(Alert.id)
        )
    )
    assert len(rows) == 2
    assert rows[0].id == old_id and rows[0].status == "RESOLVED"
    assert rows[1].status == "OPEN" and rows[1].clear_count == 0


def test_auto_resolve_uses_configuration(
    db: Session,
    asset_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALERT_AUTO_RESOLVE_AFTER", "2")
    get_settings.cache_clear()
    ingest_record(db, record(asset_id, oil_temp_trip=1))
    for second in [1, 2]:
        ingest_record(db, record(asset_id, second))
    assert alerts(db, asset_id)["OIL_TEMP_TRIP"].status == "RESOLVED"


def test_unknown_contact_never_clears_trip(db: Session, asset_id: str) -> None:
    ingest_record(db, record(asset_id, oil_temp_trip=1))
    for second in range(1, 7):
        ingest_record(db, record(asset_id, second, oil_temp_trip=None))
    row = alerts(db, asset_id)['OIL_TEMP_TRIP']
    assert row.status == 'OPEN' and row.clear_count == 0


def test_insufficient_does_not_clear_ml_alerts_but_clears_protection(
    db: Session,
    asset_id: str,
) -> None:
    ingest_record(db, record(asset_id, oil_temp_trip=1))
    for second in range(1, 6):
        output = ingest_record(db, record(asset_id, second, oil_temperature=None))
        assert output.analytics.inference_status == "INSUFFICIENT_DATA"
    rows = alerts(db, asset_id)
    assert rows["OIL_TEMP_TRIP"].status == "RESOLVED"
    for kind in ["LOW_HEALTH_INDEX", "PROXY_FAULT_RISK", "ANOMALOUS_PATTERN", "MAINTENANCE_URGENT"]:
        assert rows[kind].clear_count == 0 and rows[kind].status == "OPEN"


@pytest.mark.parametrize("failure", [False, True])
def test_protection_fires_for_insufficient_or_ml_failure(
    db: Session,
    asset_id: str,
    monkeypatch: pytest.MonkeyPatch,
    failure: bool,
) -> None:
    if failure:

        class Broken:
            def analyze(self, *args: Any) -> None:
                raise RuntimeError("private diagnostic")

        monkeypatch.setattr(ingestion_service, "get_ml_client", Broken)
    output = ingest_record(
        db,
        record(
            asset_id,
            oil_temperature=None,
            oil_temp_trip=1,
            oil_temp_alarm=1,
            magnetic_oil_gauge_alarm=1,
        ),
    )
    if failure:
        assert output.analytics is None
    else:
        assert output.analytics.inference_status == "INSUFFICIENT_DATA"
    assert set(alerts(db, asset_id)) == {"OIL_TEMP_ALARM", "OIL_TEMP_TRIP", "MOG_ALARM"}
    assert "ALERT_HOOK_FAILED" not in output.warnings
    assert ("ML_UNAVAILABLE" in output.warnings) == failure
    assert not list(
        db.scalars(select(MaintenanceRecord).where(MaintenanceRecord.transformer_id == asset_id))
    )


def test_older_rows_cannot_clear_or_replace_newer_evidence(db: Session, asset_id: str) -> None:
    ingest_record(db, record(asset_id, 20, oil_temp_trip=1))
    ingest_record(db, record(asset_id, 21))
    for second in range(5):
        ingest_record(db, record(asset_id, second))
    rows = alerts(db, asset_id)
    assert all(row.status == "OPEN" and row.clear_count == 1 for row in rows.values())
    assert all(row.last_seen_at == BASE + timedelta(seconds=20) for row in rows.values())
    ingest_record(db, record(asset_id, 10, oil_temp_alarm=1))
    health = alerts(db, asset_id)["LOW_HEALTH_INDEX"]
    assert health.evidence == {"health_index": 25.0}
    assert health.severity == "CRITICAL" and health.clear_count == 1
    assert health.last_seen_at == BASE + timedelta(seconds=20)


@pytest.mark.parametrize("failure", ["python", "database"])
def test_failing_alert_repository_rolls_back_observation(
    db: Session,
    asset_id: str,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    original = alert_repo.insert_active

    def fail(session: Session, values: dict[str, Any]) -> Alert:
        # Fail after one insert to prove all hook mutations are rolled back together.
        if values["alert_type"] == "LOW_HEALTH_INDEX":
            if failure == "database":
                session.execute(text("SELECT 1 / 0"))
            raise RuntimeError("private repository details")
        return original(session, values)

    monkeypatch.setattr(alert_repo, "insert_active", fail)
    # H02 makes telemetry, analytics and lifecycle effects one atomic transaction.
    with pytest.raises(SQLAlchemyError if failure == "database" else RuntimeError):
        ingest_record(db, record(asset_id, oil_temp_trip=1))
    assert not db.scalar(select(Telemetry).where(Telemetry.transformer_id == asset_id))
    assert not db.scalar(select(Analytics).where(Analytics.transformer_id == asset_id))
    assert not alerts(db, asset_id)
    assert not list(
        db.scalars(select(MaintenanceRecord).where(MaintenanceRecord.transformer_id == asset_id))
    )


def test_partial_index_conflict_returns_existing_active_row(db: Session, asset_id: str) -> None:
    ingest_record(db, record(asset_id, oil_temp_trip=1))
    row = alerts(db, asset_id)["OIL_TEMP_TRIP"]
    existing = alert_repo.insert_active(
        db,
        {
            "transformer_id": asset_id,
            "alert_type": row.alert_type,
            "severity": "CRITICAL",
            "timestamp": BASE,
            "last_seen_at": BASE,
            "trigger": "oil_temp_trip",
            "evidence": {"oil_temp_trip": 1},
            "threshold_or_reason": "OIL_TEMP_TRIP",
            "recommended_action": "Inspect trip indication",
            "status": "OPEN",
        },
    )
    assert existing.id == row.id


def test_hook_does_not_commit_callers_transaction(db: Session, asset_id: str) -> None:
    ingest_record(db, record(asset_id, oil_temp_trip=1), _commit=False)
    assert alerts(db, asset_id)
    db.rollback()
    assert not alerts(db, asset_id)
    assert not db.scalar(select(Telemetry).where(Telemetry.transformer_id == asset_id))


def test_maintenance_reason_set_dedupe_escalation_and_new_reasons(
    db: Session,
    asset_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs = {"maintenance_priority": "PLAN", "reason_codes": ["OVERLOAD", "HIGH_OIL_TEMP"]}

    class Controlled:
        def analyze(self, transformer: Any, telemetry: TelemetryIn, history: Any) -> Any:
            return result(telemetry, **outputs)

    monkeypatch.setattr(ingestion_service, "get_ml_client", Controlled)
    ingest_record(db, record(asset_id))
    outputs["reason_codes"] = ["HIGH_OIL_TEMP", "OVERLOAD", "HIGH_OIL_TEMP"]
    ingest_record(db, record(asset_id, 1))
    outputs["maintenance_priority"] = "URGENT"
    ingest_record(db, record(asset_id, 2))
    outputs["maintenance_priority"] = "NORMAL"
    ingest_record(db, record(asset_id, 3))
    rows = list(
        db.scalars(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.transformer_id == asset_id)
            .order_by(MaintenanceRecord.id)
        )
    )
    assert [(row.priority, row.status) for row in rows] == [("PLAN", "OPEN"), ("URGENT", "OPEN")]
    outputs.update(maintenance_priority="PLAN", reason_codes=["OVERLOAD"])
    ingest_record(db, record(asset_id, 4))
    assert (
        len(
            list(
                db.scalars(
                    select(MaintenanceRecord).where(MaintenanceRecord.transformer_id == asset_id)
                )
            )
        )
        == 3
    )
