from datetime import timedelta

from fastapi.testclient import TestClient

from tests.alerts.conftest import BASE, record


def test_protection_to_alert_health_proxy_risk_and_recommendation_http_scenario(
    alert_client: TestClient,
    asset_id: str,
) -> None:
    latest_path = f"/api/v1/transformers/{asset_id}/latest"
    params = {"from": BASE.isoformat(), "to": (BASE + timedelta(hours=1)).isoformat()}

    def ingest(second: int, **flags: int) -> dict:
        response = alert_client.post(
            "/api/v1/telemetry",
            json=record(
                asset_id, second, source_name="simulator", scenario_id="alerts-demo", **flags
            ).model_dump(mode="json"),
        )
        assert response.status_code == 201
        assert "ALERT_HOOK_FAILED" not in response.json()["warnings"]
        return alert_client.get(latest_path).json()

    def read_alerts() -> dict:
        response = alert_client.get(f"/api/v1/transformers/{asset_id}/alerts", params=params)
        assert response.status_code == 200
        return {row["alert_type"]: row for row in response.json()["items"]}

    normal = ingest(0)
    assert normal["analytics"]["health_index"] == 90
    assert normal["analytics"]["fault_risk"] == 0.05
    assert normal["open_alerts_count"] == 0
    assert normal["demo_mode"] is True
    alarm = ingest(1, oil_temp_alarm=1)
    assert alarm["analytics"]["health_index"] == 55
    assert alarm["analytics"]["fault_risk"] == 0.6
    assert alarm["analytics"]["maintenance_priority"] == "PLAN"
    assert alarm["analytics"]["maintenance_recommendation"]
    warning = read_alerts()
    assert warning["OIL_TEMP_ALARM"]["severity"] == "WARNING"
    assert warning["LOW_HEALTH_INDEX"]["severity"] == "WARNING"
    assert alarm["open_alerts_count"] == len(warning)
    ingest(2, oil_temp_alarm=1)
    trip = ingest(3, oil_temp_trip=1)
    assert trip["analytics"]["health_index"] == 25
    assert trip["analytics"]["fault_risk"] == 0.9
    assert trip["analytics"]["maintenance_priority"] == "URGENT"
    assert trip["analytics"]["maintenance_recommendation"]
    critical = read_alerts()
    assert critical["OIL_TEMP_TRIP"]["severity"] == "CRITICAL"
    assert critical["LOW_HEALTH_INDEX"]["severity"] == "CRITICAL"
    assert critical["LOW_HEALTH_INDEX"]["id"] == warning["LOW_HEALTH_INDEX"]["id"]
    assert (
        "proxy risk (alarm/trip-based prediction)"
        in critical["PROXY_FAULT_RISK"]["threshold_or_reason"]
    )
    assert trip["open_alerts_count"] == len(critical)
    maintenance_path = f"/api/v1/transformers/{asset_id}/maintenance"
    maintenance = alert_client.get(maintenance_path, params=params).json()
    assert maintenance["total"] == 2
    assert {row["priority"] for row in maintenance["items"]} == {"PLAN", "URGENT"}
    assert all(row["status"] == "OPEN" for row in maintenance["items"])
    for second in range(4, 8):
        latest = ingest(second)
        assert read_alerts()["OIL_TEMP_TRIP"]["status"] == "OPEN"
    latest = ingest(8)
    assert latest["analytics"]["health_index"] == 90
    assert latest["open_alerts_count"] == 0
    resolved = read_alerts()
    assert all(row["status"] == "RESOLVED" and row["resolved_at"] for row in resolved.values())
    assert all("clear_count" not in row for row in resolved.values())
    assert resolved["OIL_TEMP_TRIP"]["resolved_at"] == "2026-01-01T00:00:08Z"
    maintenance = alert_client.get(maintenance_path, params=params).json()
    assert maintenance["total"] == 2 and all(
        row["status"] == "OPEN" for row in maintenance["items"]
    )
