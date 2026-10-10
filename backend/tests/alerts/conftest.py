from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.ml_client.factory import close_ml_client
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn

BASE = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def alert_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in {
        "ML_BACKEND": "stub",
        "MQTT_ENABLED": "false",
        "ALERT_HEALTH_WARN": "60",
        "ALERT_HEALTH_CRIT": "40",
        "ALERT_ANOMALY_CRITICAL": "0.9",
        "ALERT_FAULT_RISK_WARN": "0.5",
        "ALERT_FAULT_RISK_CRIT": "0.8",
        "ALERT_AUTO_RESOLVE_AFTER": "5",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("ALERT_REASON_SEVERITY", raising=False)
    get_settings.cache_clear()
    close_ml_client()
    yield
    close_ml_client()
    get_settings.cache_clear()


@pytest.fixture
def asset_id() -> str:
    return f"TX-alert-{uuid4().hex[:12]}"


@pytest.fixture
def alert_client(db: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client


def record(asset: str, second: int = 0, **overrides: Any) -> TelemetryIn:
    return TelemetryIn.model_validate(
        {
            "transformer_id": asset,
            "timestamp": BASE + timedelta(seconds=second),
            "oil_temperature": 42,
            "oil_level": 8,
            "oil_temp_alarm": 0,
            "oil_temp_trip": 0,
            "magnetic_oil_gauge_alarm": 0,
            "current_l1": 0,
            "current_l2": 0,
            "current_l3": 0,
            "phase_voltage_l1": 0,
            "phase_voltage_l2": 0,
            "phase_voltage_l3": 0,
            **overrides,
        }
    )


def result(record: TelemetryIn, **overrides: Any) -> MLResultIn:
    return MLResultIn.model_validate(
        {
            "transformer_id": record.transformer_id,
            "timestamp": record.timestamp,
            "inference_status": "OK",
            "schema_version": "1.0.0",
            "feature_version": "1.0.0",
            "model_version": "test-1",
            **overrides,
        }
    )
