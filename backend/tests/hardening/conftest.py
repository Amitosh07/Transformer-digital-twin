from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.ml_client.factory import close_ml_client


@pytest.fixture(autouse=True)
def hardening_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ML_BACKEND", "stub")
    monkeypatch.setenv("MQTT_ENABLED", "false")
    monkeypatch.setenv("MAX_BATCH_SIZE", "10000")
    get_settings.cache_clear()
    close_ml_client()
    yield
    close_ml_client()
    get_settings.cache_clear()


@pytest.fixture
def hard_client(db: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
