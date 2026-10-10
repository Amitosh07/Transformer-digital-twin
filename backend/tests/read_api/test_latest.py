from datetime import timedelta
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories import analytics_repo, telemetry_repo
from app.schemas.telemetry import TelemetryIn
from app.services.ingestion_service import ingest_record
from tests.read_api.conftest import BASE


def test_latest_empty_and_populated(read_client: TestClient, seeded: dict[str, Any]) -> None:
    asset = f"TX-empty-{uuid4().hex[:8]}"
    assert (
        read_client.post("/api/v1/transformers", json={"id": asset, "name": "Empty"}).status_code
        == 201
    )
    empty = read_client.get(f"/api/v1/transformers/{asset}/latest")
    assert empty.status_code == 200
    assert empty.json()["telemetry"] is empty.json()["analytics"] is None
    assert empty.json()["open_alerts_count"] == 0
    assert empty.json()["demo_mode"] is False
    assert empty.json()["data_source"] == {"source_name": None, "scenario_id": None}
    for kind, demo in [("demo", True), ("live", False)]:
        result = read_client.get(f"/api/v1/transformers/{seeded[kind]}/latest").json()
        assert result["telemetry"]["timestamp"] == "2020-01-01T00:00:30Z"
        assert result["analytics"]["inference_status"] == "INSUFFICIENT_DATA"
        assert result["demo_mode"] is demo
        assert result["schema_version"] == "1.0.0"
        assert result["feature_version"] == "1.0.0"
        assert result["model_version"] == "stub-0.0.0"
        assert result["open_alerts_count"] == (2 if demo else 0)


def test_latest_uses_own_analytics_and_sanitizes_errors(
    read_client: TestClient, seeded: dict[str, Any], db: Session
) -> None:
    asset = seeded["live"]
    row = telemetry_repo.get_latest(db, asset)
    analytics = analytics_repo.get_for_telemetry(db, row.id)
    analytics.error_detail = "secret database exception"
    db.flush()
    result = read_client.get(f"/api/v1/transformers/{asset}/latest")
    assert result.json()["analytics"]["error_detail"] == "ML analysis failed"
    assert "secret" not in result.text
    ingest_record(
        db,
        TelemetryIn(transformer_id=asset, timestamp=BASE + timedelta(minutes=1)),
        run_ml=False,
        _commit=False,
    )
    latest = read_client.get(f"/api/v1/transformers/{asset}/latest").json()
    assert latest["analytics"] is None
    assert latest["feature_version"] is latest["model_version"] is None
