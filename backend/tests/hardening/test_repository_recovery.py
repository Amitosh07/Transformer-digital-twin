from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import Alert, Analytics
from app.repositories import alert_repo, analytics_repo, telemetry_repo
from app.schemas.analytics import MLResultIn
from app.services.ingestion_service import ingest_batch, ingest_record
from tests.performance.test_differential import mixed


def test_analytics_conflict_preserves_original_and_reports_missing_lookup(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset = "TX-analysis-conflict-" + uuid4().hex
    record = mixed(asset, 0)
    output = ingest_record(db, record)
    existing = analytics_repo.get_for_telemetry(db, output.telemetry_id)
    proposed = MLResultIn.model_validate(output.analytics.model_dump() | {"health_index": 1})
    row, created = analytics_repo.insert_analytics(db, output.telemetry_id, proposed)
    assert not created and row.id == existing.id and row.health_index == 90
    monkeypatch.setattr(analytics_repo, "get_for_telemetry", lambda *args: None)
    with pytest.raises(RuntimeError, match="Analytics lookup did not return a row"):
        analytics_repo.insert_analytics(db, output.telemetry_id, proposed)
    assert (
        db.scalar(
            select(Analytics).where(Analytics.telemetry_id == output.telemetry_id)
        ).health_index
        == 90
    )


def test_empty_bulk_operations_execute_no_sql(db: Session) -> None:
    statements = []
    connection = db.get_bind()

    def count(*args: Any) -> None:
        statements.append(args)

    event.listen(connection, "before_cursor_execute", count)
    try:
        assert analytics_repo.insert_many(db, []) == {}
        assert telemetry_repo.insert_many(db, []) == {}
    finally:
        event.remove(connection, "before_cursor_execute", count)
    assert not statements


def test_bulk_alert_conflict_reconciles_through_existing_row_path(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset = "TX-cache-conflict-" + uuid4().hex
    ingest_record(db, mixed(asset, 13))
    original = alert_repo.active
    old_ids = {row.alert_type: row.id for row in original(db, asset)}
    first = True

    def stale_snapshot(session: Session, asset: str) -> list[Alert]:
        nonlocal first
        if first:
            first = False
            return []
        return original(session, asset)

    monkeypatch.setattr(alert_repo, "active", stale_snapshot)
    summary = ingest_batch(
        db, [mixed(asset, index).model_dump(mode="json") for index in range(14, 18)]
    )
    assert summary.inserted_count == 4
    rows = original(db, asset)
    assert {row.alert_type: row.id for row in rows} == old_ids
    assert all(row.last_seen_at == mixed(asset, 17).timestamp for row in rows)


def test_external_duplicate_safety_path_keeps_original_telemetry(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = telemetry_repo.insert_telemetry

    def inserted_elsewhere(session: Session, record, **kwargs):
        # Simulate the competing accepted row on the current single-record
        # insertion path, then exercise its real ON CONFLICT lookup.
        original(session, record, **kwargs)
        return original(session, record, **kwargs)

    monkeypatch.setattr(telemetry_repo, "insert_telemetry", inserted_elsewhere)
    asset = "TX-external-conflict-" + uuid4().hex
    summary = ingest_batch(db, [mixed(asset, 0).model_dump(mode="json")])
    assert summary.inserted_count == 0 and summary.duplicate_count == 1
    assert not db.scalar(select(Analytics).where(Analytics.transformer_id == asset))
