"""One configuration switch selects the ML integration without changing callers."""

from functools import lru_cache
from threading import RLock

from app.core.config import get_settings
from app.ml_client.base import MLTwinClient
from app.ml_client.http_client import HttpMLTwinClient
from app.ml_client.python_client import PythonMLTwinClient
from app.ml_client.stub_client import StubMLTwinClient

_client_lock = RLock()
_created_client: MLTwinClient | None = None


@lru_cache(maxsize=1)
def _cached_client() -> MLTwinClient:
    settings = get_settings()
    if settings.ml_backend == "stub":
        return StubMLTwinClient(settings)
    if settings.ml_backend == "python":
        return PythonMLTwinClient(settings)
    if settings.ml_backend == "http":
        return HttpMLTwinClient(settings)
    raise ValueError("Unsupported ML_BACKEND; choose stub, python, or http")


def get_ml_client() -> MLTwinClient:
    global _created_client
    with _client_lock:
        _created_client = _cached_client()
        return _created_client


def close_ml_client() -> None:
    global _created_client
    with _client_lock:
        if isinstance(_created_client, HttpMLTwinClient):
            _created_client.close()
        _created_client = None
        _cached_client.cache_clear()


# Preserve the existing factory-cache testing/maintenance interface.
get_ml_client.cache_clear = _cached_client.cache_clear
