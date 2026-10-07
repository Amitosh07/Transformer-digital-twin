from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.ingestion_service import ingest_record
from tests.alerts.conftest import record
from tests.alerts.test_lifecycle import alerts


def assert_error(response: Any, status: int) -> None:
    assert response.status_code == status
    assert set(response.json()) == {"error"}
    assert set(response.json()["error"]) == {"code", "message", "details"}


def test_alert_transitions_and_latest_count(
    db: Session,
    alert_client: TestClient,
    asset_id: str,
) -> None:
    ingest_record(db, record(asset_id, oil_temperature=None, oil_temp_trip=1))
    row = alerts(db, asset_id)["OIL_TEMP_TRIP"]
    path = f"/api/v1/alerts/{row.id}"
    latest = f"/api/v1/transformers/{asset_id}/latest"
    fetched = alert_client.get(path)
    assert fetched.status_code == 200
    assert "clear_count" not in fetched.json()
    assert fetched.json()["resolved_at"] is None
    assert fetched.json()["last_seen_at"]
    assert alert_client.get(latest).json()["open_alerts_count"] == 1
    ack = alert_client.patch(path + "/acknowledge")
    assert ack.status_code == 200 and ack.json()["status"] == "ACKNOWLEDGED"
    assert datetime.fromisoformat(ack.json()["acknowledged_at"]).utcoffset().total_seconds() == 0
    assert alert_client.patch(path + "/acknowledge").json() == ack.json()
    assert alert_client.get(latest).json()["open_alerts_count"] == 0
    ingest_record(db, record(asset_id, 1, oil_temperature=None, oil_temp_trip=1))
    assert alerts(db, asset_id)["OIL_TEMP_TRIP"].id == row.id
    assert alert_client.get(latest).json()["open_alerts_count"] == 0
    resolved = alert_client.patch(path + "/resolve")
    assert resolved.status_code == 200 and resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["resolved_at"]
    assert alert_client.patch(path + "/resolve").json() == resolved.json()
    assert_error(alert_client.patch(path + "/acknowledge"), 409)
    assert alert_client.get(path).json() == resolved.json()


def test_open_alert_can_be_resolved_directly(
    db: Session,
    alert_client: TestClient,
    asset_id: str,
) -> None:
    ingest_record(db, record(asset_id, oil_temp_trip=1))
    row = alerts(db, asset_id)["OIL_TEMP_TRIP"]
    response = alert_client.patch(f"/api/v1/alerts/{row.id}/resolve")
    assert response.status_code == 200 and response.json()["status"] == "RESOLVED"


@pytest.mark.parametrize("status", ["DONE", "DISMISSED"])
def test_maintenance_status_transition(
    db: Session,
    alert_client: TestClient,
    asset_id: str,
    status: str,
) -> None:
    from sqlalchemy import select

    from app.models import MaintenanceRecord

    ingest_record(db, record(asset_id, oil_temp_alarm=1))
    row = db.scalar(select(MaintenanceRecord).where(MaintenanceRecord.transformer_id == asset_id))
    path = f"/api/v1/maintenance/{row.id}"
    assert alert_client.get(path).json()["status"] == "OPEN"
    response = alert_client.patch(path, json={"status": status})
    assert response.status_code == 200 and response.json()["status"] == status
    assert alert_client.get(path).json() == response.json()
    assert_error(alert_client.patch(path, json={"status": status}), 409)
    # Closing maintenance allows a later occurrence with the same priority and reasons.
    ingest_record(db, record(asset_id, 1, oil_temp_alarm=1))
    assert (
        len(
            list(
                db.scalars(
                    select(MaintenanceRecord).where(MaintenanceRecord.transformer_id == asset_id)
                )
            )
        )
        == 2
    )


@pytest.mark.parametrize(
    "path,method,payload",
    [
        ("alerts/999999999", "get", None),
        ("alerts/999999999/acknowledge", "patch", None),
        ("alerts/999999999/resolve", "patch", None),
        ("maintenance/999999999", "get", None),
        ("maintenance/999999999", "patch", {"status": "DONE"}),
    ],
)
def test_unknown_ids(alert_client: TestClient, path: str, method: str, payload: Any) -> None:
    assert_error(alert_client.request(method, "/api/v1/" + path, json=payload), 404)


@pytest.mark.parametrize(
    "payload", [{"status": "OPEN"}, {"status": "invalid"}, {"status": "DONE", "extra": 1}, {}]
)
def test_maintenance_payload_validation(alert_client: TestClient, payload: Any) -> None:
    assert_error(alert_client.patch("/api/v1/maintenance/1", json=payload), 422)
