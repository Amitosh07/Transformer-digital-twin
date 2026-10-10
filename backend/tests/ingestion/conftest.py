from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.ml_client.factory import close_ml_client


@pytest.fixture(autouse=True)
def ingestion_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MAX_BATCH_SIZE", "10000")
    monkeypatch.setenv("ML_BACKEND", "stub")
    get_settings.cache_clear()
    close_ml_client()
    yield
    close_ml_client()
    get_settings.cache_clear()


@pytest.fixture
def asset_id() -> str:
    return f"TX-ingest-{uuid4().hex[:12]}"


@pytest.fixture
def payload(asset_id: str) -> dict[str, Any]:
    return make_record(asset_id, 0)


def make_record(asset: str, seconds: int) -> dict[str, Any]:
    return {
        "transformer_id": asset,
        "timestamp": (datetime(2026, 10, 6, tzinfo=UTC) + timedelta(seconds=seconds)).isoformat(),
        "oil_temperature": 42,
        "oil_level": 8,
        "oil_temp_alarm": 0,
        "current_l1": 0,
        "current_l2": 0,
        "current_l3": 0,
        "phase_voltage_l1": 0,
        "phase_voltage_l2": 0,
        "phase_voltage_l3": 0,
    }


@pytest.fixture
def ingestion_session(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def ingest_client(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    import app.services.replay_service as replay

    factory = sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(replay, "SessionLocal", factory)
    application = create_app()

    def database() -> Iterator[Session]:
        with factory() as session:
            yield session

    application.dependency_overrides[get_db] = database
    with TestClient(application) as client:
        yield client
