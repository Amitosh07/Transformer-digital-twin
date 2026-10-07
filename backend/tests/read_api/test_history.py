from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.query import TimeWindow
from app.schemas.telemetry import TelemetryIn
from app.services.ingestion_service import ingest_record
from app.services.query_service import resolve_window


@pytest.mark.parametrize("group", ["telemetry", "health", "analytics"])
def test_anchor_paging_order_and_insufficient(
    read_client: TestClient, seeded: dict[str, Any], group: str
) -> None:
    path = f"/api/v1/transformers/{seeded['demo']}/{group}"
    assert read_client.get(path).json()["items"] == []
    page = read_client.get(path, params={"anchor": "latest"}).json()
    assert page["total"] == 4
    assert [row["timestamp"] for row in page["items"]] == sorted(
        row["timestamp"] for row in page["items"]
    )
    pieces = [
        read_client.get(path, params={"anchor": "latest", "limit": 2, "offset": offset}).json()
        for offset in (0, 2)
    ]
    assert pieces[0]["items"] + pieces[1]["items"] == page["items"]
    descending = read_client.get(path, params={"anchor": "latest", "order": "desc"}).json()
    assert descending["items"] == page["items"][::-1]
    if group in ("health", "analytics"):
        last = page["items"][-1]
        assert last["inference_status"] == "INSUFFICIENT_DATA"
        assert last["health_index" if group == "health" else "anomaly_score"] is None
        assert "error_detail" not in last
    if group == "analytics":
        assert page["items"][1]["fault_risk"] == 0.6
        assert page["items"][2]["fault_risk"] == 0.9


@pytest.mark.parametrize(
    "parameters,message",
    [
        ({"from": "2020-01-01T00:00:00Z", "to": "2020-01-01T00:00:00Z"}, "earlier"),
        ({"from": "2020-01-02T00:00:00Z", "to": "2020-01-01T00:00:00Z"}, "earlier"),
        ({"from": "2020-01-01T00:00:00Z", "to": "2020-02-02T00:00:00Z"}, "MAX_WINDOW_DAYS=31"),
        ({"from": "2020-01-01T00:00:00"}, "timezone"),
        ({"to": "2020-01-01T00:00:00"}, "timezone"),
        ({"limit": 5001}, "MAX_PAGE_LIMIT=5000"),
        ({"limit": 0}, "greater"),
        ({"offset": -1}, "greater"),
        ({"order": "random"}, "Input"),
    ],
)
def test_window_and_page_rejections(
    read_client: TestClient, seeded: dict[str, Any], parameters: dict, message: str
) -> None:
    response = read_client.get(
        f"/api/v1/transformers/{seeded['demo']}/telemetry", params=parameters
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert message in str(response.json())


def test_offset_time_conversion_and_explicit_window_overrides_anchor(
    read_client: TestClient, seeded: dict[str, Any]
) -> None:
    response = read_client.get(
        f"/api/v1/transformers/{seeded['demo']}/telemetry",
        params={
            "from": "2020-01-01T05:30:00+05:30",
            "to": "2020-01-01T05:30:20+05:30",
            "anchor": "latest",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["items"][0]["timestamp"] == "2020-01-01T00:00:00Z"


def test_defaults_and_configuration(
    db: Session, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    before, after = datetime.now(UTC), None
    resolved = resolve_window(db, seeded["live"], TimeWindow())
    after = datetime.now(UTC)
    assert before <= resolved.end <= after
    assert resolved.end - resolved.start == timedelta(hours=24)
    monkeypatch.setenv("DEFAULT_WINDOW_HOURS", "6")
    get_settings.cache_clear()
    resolved = resolve_window(db, seeded["live"], TimeWindow(anchor="latest"))
    assert resolved.end - resolved.start == timedelta(hours=6)
    assert resolved.end.year == 2020


def test_fields_projection_and_nulls(read_client: TestClient, seeded: dict[str, Any]) -> None:
    path = f"/api/v1/transformers/{seeded['demo']}/telemetry"
    response = read_client.get(
        path, params={"anchor": "latest", "fields": "oil_temperature,current_l1"}
    )
    assert response.status_code == 200
    assert all(
        set(row) == {"timestamp", "oil_temperature", "current_l1"}
        for row in response.json()["items"]
    )
    assert response.json()["items"][-1]["oil_temperature"] is None
    assert response.json()["items"][-1]["current_l1"] == 0
    assert read_client.get(path, params={"anchor": "latest", "fields": "id"}).json()["items"][
        0
    ].keys() == {"id", "timestamp"}


@pytest.mark.parametrize(
    "field", ["V" + "L12", "v" + "l23", "V" + "L_31", "unknown", "", "schema_version", "V" + "L1"]
)
def test_unknown_fields_list_allowlist(
    read_client: TestClient, seeded: dict[str, Any], field: str
) -> None:
    response = read_client.get(
        f"/api/v1/transformers/{seeded['demo']}/telemetry", params={"fields": field}
    )
    assert response.status_code == 422
    assert "Allowed names" in response.text
    assert "oil_temperature" in response.text


def test_current_rows_in_default_window(
    read_client: TestClient, seeded: dict[str, Any], db: Session
) -> None:
    ingest_record(
        db, TelemetryIn(transformer_id=seeded["live"], timestamp=datetime.now(UTC)), _commit=False
    )
    result = read_client.get(f"/api/v1/transformers/{seeded['live']}/telemetry").json()
    assert result["total"] == 1


@pytest.mark.parametrize("group", ["health", "analytics", "alerts", "maintenance", "trends"])
def test_all_history_groups_share_window_rules(
    read_client: TestClient, seeded: dict[str, Any], group: str
) -> None:
    path = f"/api/v1/transformers/{seeded['demo']}/{group}"
    for parameters in [
        {"from": "2020-01-01T00:00:00"},
        {"from": "2020-01-02T00:00:00Z", "to": "2020-01-01T00:00:00Z"},
        {"from": "2020-01-01T00:00:00Z", "to": "2020-02-02T00:00:00Z"},
    ]:
        response = read_client.get(path, params=parameters | {"signals": "oil_temperature"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_maximum_window_and_limit_configuration(
    read_client: TestClient, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_WINDOW_DAYS", "1")
    get_settings.cache_clear()
    path = f"/api/v1/transformers/{seeded['demo']}/telemetry"
    params = {"from": "2020-01-01T00:00:00Z", "to": "2020-01-02T00:00:00Z", "limit": 5000}
    assert read_client.get(path, params=params).status_code == 200
    too_large = read_client.get(path, params=params | {"to": "2020-01-02T00:00:01Z"})
    assert too_large.status_code == 422
    assert "MAX_WINDOW_DAYS=1" in too_large.text
