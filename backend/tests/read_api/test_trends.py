from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.telemetry import TelemetryIn
from app.services.ingestion_service import ingest_record
from app.services.trend_service import WINDOWS
from tests.read_api.conftest import BASE


def test_trend_hand_computed_math_and_gaps(read_client: TestClient, seeded: dict[str, Any]) -> None:
    response = read_client.get(
        f"/api/v1/transformers/{seeded['demo']}/trends",
        params={
            "signals": "oil_temperature,current_l1,neutral_current,health_index,fault_risk",
            "window": "1h",
            "from": "2020-01-01T00:00:00Z",
            "to": "2020-01-01T00:01:00Z",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["bucket_seconds"] == 15
    first = result["signals"]["oil_temperature"][0]
    assert first == {
        "bucket_start": "2020-01-01T00:00:00Z",
        "avg": 41,
        "min": 40,
        "max": 42,
        "count": 2,
    }
    assert result["signals"]["oil_temperature"][1]["avg"] == 44
    assert result["signals"]["oil_temperature"][2]["count"] == 0
    assert result["signals"]["oil_temperature"][2]["avg"] is None
    assert result["signals"]["current_l1"][2]["avg"] == 0
    assert result["signals"]["health_index"][0]["avg"] == 72.5
    assert result["signals"]["fault_risk"][0]["avg"] == pytest.approx(0.325)
    assert result["no_data_signals"] == ["neutral_current"]
    assert [row["timestamp"] for row in result["protection_events"]] == [
        "2020-01-01T00:00:10Z",
        "2020-01-01T00:00:20Z",
    ]
    assert all(
        bucket["avg"] is bucket["min"] is bucket["max"] is None
        for bucket in result["signals"]["neutral_current"]
    )


@pytest.mark.parametrize("window", list(WINDOWS))
def test_trend_anchor_and_bucket_bounds(
    read_client: TestClient, seeded: dict[str, Any], window: str
) -> None:
    result = read_client.get(
        f"/api/v1/transformers/{seeded['demo']}/trends",
        params={"signals": "oil_temperature", "anchor": "latest", "window": window},
    ).json()
    assert result["end"] == "2020-01-01T00:00:30Z"
    assert len(result["signals"]["oil_temperature"]) <= 301
    assert sum(bucket["count"] for bucket in result["signals"]["oil_temperature"]) == 3
    assert result["bucket_seconds"] == WINDOWS[window][1]


@pytest.mark.parametrize(
    "signals",
    [
        "unknown",
        "oil_temp_alarm",
        "V" + "L12",
        "",
        "oil_temperature,current_l1,current_l2,current_l3,phase_voltage_l1,phase_voltage_l2,phase_voltage_l3,health_index,fault_risk",
    ],
)
def test_trend_signal_rejections(
    read_client: TestClient, seeded: dict[str, Any], signals: str
) -> None:
    result = read_client.get(
        f"/api/v1/transformers/{seeded['demo']}/trends", params={"signals": signals}
    )
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"


def test_protection_events_cap_and_custom_window_width(
    read_client: TestClient, seeded: dict[str, Any], db: Session
) -> None:
    from datetime import timedelta

    for index in range(501):
        ingest_record(
            db,
            TelemetryIn(
                transformer_id=seeded["live"],
                timestamp=BASE + timedelta(minutes=index + 1),
                oil_temp_trip=1,
            ),
            run_ml=False,
            _commit=False,
        )
    result = read_client.get(
        f"/api/v1/transformers/{seeded['live']}/trends",
        params={
            "signals": "oil_temperature",
            "window": "1h",
            "from": "2020-01-01T00:00:00Z",
            "to": "2020-01-31T00:00:00Z",
        },
    ).json()
    assert len(result["signals"]["oil_temperature"]) <= 301
    assert len(result["protection_events"]) == 500
