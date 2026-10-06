"""One configuration switch selects the ML integration without changing callers."""

from functools import lru_cache

from app.core.config import get_settings
from app.ml_client.base import MLTwinClient
from app.ml_client.http_client import HttpMLTwinClient
from app.ml_client.python_client import PythonMLTwinClient
from app.ml_client.stub_client import StubMLTwinClient


@lru_cache(maxsize=1)
def get_ml_client() -> MLTwinClient:
    settings = get_settings()
    if settings.ml_backend == "stub":
        return StubMLTwinClient(settings)
    if settings.ml_backend == "python":
        return PythonMLTwinClient(settings)
    if settings.ml_backend == "http":
        return HttpMLTwinClient(settings)
    raise ValueError("Unsupported ML_BACKEND; choose stub, python, or http")
