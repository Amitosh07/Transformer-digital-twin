from collections.abc import Iterator

import pytest

from app.core.config import get_settings
from app.ml_client.factory import close_ml_client


@pytest.fixture(autouse=True)
def demo_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name, value in {
        "ENV": "development",
        "ML_BACKEND": "stub",
        "MQTT_ENABLED": "false",
        "MAX_BATCH_SIZE": "5000",
        "DEMO_RESET_ENABLED": "false",
        "DEMO_ADMIN_TOKEN": "",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    close_ml_client()
    yield
    close_ml_client()
    get_settings.cache_clear()
