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
from app.models.alert import Alert
from app.models.maintenance_record import MaintenanceRecord
from app.schemas.telemetry import TelemetryIn
from app.services.ingestion_service import ingest_record

BASE = datetime(2020, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def read_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in {
        "ML_BACKEND": "stub",
        "MQTT_ENABLED": "false",
        "DEFAULT_WINDOW_HOURS": "24",
        "MAX_WINDOW_DAYS": "31",
        "MAX_PAGE_LIMIT": "5000",
        "CORS_ORIGINS": "http://localhost:8501,http://127.0.0.1:8501",
        "DEMO_SOURCE_NAMES": "simulator,replay,demo,seed,mqtt,mqtt-simulator,analytics-backfill",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    close_ml_client()
    yield
    close_ml_client()
    get_settings.cache_clear()


@pytest.fixture
def read_client(db: Session) -> Iterator[TestClient]:
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db
    with TestClient(application) as client:
        yield client


@pytest.fixture
def seeded(db: Session) -> dict[str, Any]:
    assets = [f"TX-read-{uuid4().hex[:10]}" for _ in range(2)]
    for asset in assets:
        for index in range(4):
            record = TelemetryIn(
                transformer_id=asset,
                timestamp=BASE + timedelta(seconds=index * 10),
                oil_temperature=40 + index * 2 if index < 3 else None,
                oil_level=8 if index < 3 else None,
                oil_temp_alarm=int(index == 1),
                oil_temp_trip=int(index == 2),
                magnetic_oil_gauge_alarm=0,
                current_l1=0,
                source_name="replay-public-data" if asset == assets[0] else "plant-sensor",
                scenario_id="read-scenario" if asset == assets[0] else None,
            )
            ingest_record(db, record, _commit=False)
    for index, (severity, status) in enumerate(
        [("WARNING", "OPEN"), ("CRITICAL", "OPEN"), ("INFO", "RESOLVED")]
    ):
        stamp = BASE + timedelta(seconds=index * 10)
        db.add(
            Alert(
                transformer_id=assets[0],
                timestamp=stamp,
                severity=severity,
                alert_type="PROTECTION",
                trigger="oil_temp_alarm",
                evidence={"oil_temp_alarm": 1},
                threshold_or_reason="OIL_TEMP_ALARM",
                recommended_action="Inspect proxy indication",
                status=status,
                last_seen_at=stamp,
            )
        )
        db.add(
            MaintenanceRecord(
                transformer_id=assets[0],
                timestamp=stamp,
                priority="PLAN",
                recommendation="Inspect indication",
                reason_codes=["OIL_TEMP_ALARM"],
                status=["OPEN", "DONE", "DISMISSED"][index],
            )
        )
    db.flush()
    return {"demo": assets[0], "live": assets[1], "start": BASE, "count": 4}
