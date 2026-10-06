import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.main import create_app


def test_app_factory_and_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:8501"]')
    get_settings.cache_clear()
    try:
        application = create_app()
        assert "/health" in application.openapi()["paths"]
        with TestClient(application) as client:
            response = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:8501",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == "http://localhost:8501"
    finally:
        get_settings.cache_clear()


def test_logging_level() -> None:
    previous = logging.getLogger().level
    try:
        configure_logging("DEBUG")
        assert logging.getLogger().level == logging.DEBUG
    finally:
        logging.getLogger().setLevel(previous)
