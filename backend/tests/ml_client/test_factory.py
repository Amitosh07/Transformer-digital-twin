import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.ml_client.factory import get_ml_client
from app.ml_client.http_client import HttpMLTwinClient
from app.ml_client.python_client import PythonMLTwinClient
from app.ml_client.stub_client import StubMLTwinClient


@pytest.mark.parametrize(
    "backend,expected",
    [("stub", StubMLTwinClient), ("python", PythonMLTwinClient), ("http", HttpMLTwinClient)],
)
def test_selection_and_cache(
    backend: str,
    expected: type,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_BACKEND", backend)
    monkeypatch.setenv("ML_HTTP_URL", "https://twin.example/analyze")
    monkeypatch.delenv("ML_PYTHON_ENTRYPOINT", raising=False)
    get_settings.cache_clear()
    get_ml_client.cache_clear()
    client = None
    try:
        client = get_ml_client()
        assert isinstance(client, expected)
        assert get_ml_client() is client
    finally:
        if isinstance(client, HttpMLTwinClient):
            client.close()
        get_ml_client.cache_clear()
        get_settings.cache_clear()


def test_unknown_backend_rejected_by_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ML_BACKEND", "unsupported")
    with pytest.raises(ValidationError, match="ml_backend"):
        Settings(_env_file=None)


def test_factory_defensively_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.ml_client.factory as module

    settings = Settings(_env_file=None)
    settings.ml_backend = "unsupported"
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    get_ml_client.cache_clear()
    try:
        with pytest.raises(ValueError, match="Unsupported ML_BACKEND"):
            get_ml_client()
    finally:
        get_ml_client.cache_clear()
