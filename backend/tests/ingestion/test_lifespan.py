import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.ml_client.factory import close_ml_client, get_ml_client
from app.ml_client.http_client import HttpMLTwinClient


def test_shutdown_closes_cached_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ML_BACKEND", "http")
    monkeypatch.setenv("ML_HTTP_URL", "https://twin.example/analyze")
    get_settings.cache_clear()
    close_ml_client()
    client = get_ml_client()
    assert isinstance(client, HttpMLTwinClient)
    assert not client._client.is_closed
    with TestClient(create_app()):
        pass
    assert client._client.is_closed
