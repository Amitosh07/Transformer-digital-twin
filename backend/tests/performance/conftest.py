from collections.abc import Iterator

import pytest

from app.core.config import get_settings
from app.ml_client.factory import close_ml_client


@pytest.fixture(autouse=True)
def performance_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ML_BACKEND", "stub")
    monkeypatch.setenv("MQTT_ENABLED", "false")
    monkeypatch.setenv("MAX_BATCH_SIZE", "10000")
    get_settings.cache_clear()
    close_ml_client()
    yield
    close_ml_client()
    get_settings.cache_clear()
