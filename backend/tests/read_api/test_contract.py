import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings


@pytest.mark.parametrize(
    "suffix",
    ["", "/latest", "/telemetry", "/health", "/analytics", "/alerts", "/maintenance", "/trends"],
)
def test_unknown_transformer_is_404(read_client: TestClient, suffix: str) -> None:
    result = read_client.get(
        "/api/v1/transformers/unknown-read-asset" + suffix, params={"signals": "oil_temperature"}
    )
    assert result.status_code == 404
    assert set(result.json()["error"]) == {"code", "message", "details"}
    if not suffix:
        assert (
            read_client.patch("/api/v1/transformers/unknown-read-asset", json={}).status_code == 404
        )


def test_openapi_routes_examples_and_cors(read_client: TestClient) -> None:
    document = read_client.get("/openapi.json").json()
    serialized = json.dumps(document).casefold()
    for key in ("v" + "l12", "v" + "l23", "v" + "l31"):
        assert key not in serialized
    operations = {
        "/transformers": ["get", "post"],
        "/transformers/{id}": ["get", "patch"],
        "/scenarios": ["get"],
    }
    for suffix in ["latest", "telemetry", "health", "analytics", "alerts", "maintenance", "trends"]:
        operations["/transformers/{id}/" + suffix] = ["get"]
    for path, methods in operations.items():
        for method in methods:
            operation = document["paths"]["/api/v1" + path][method]
            status = "201" if method == "post" else "200"
            content = operation["responses"][status]["content"]["application/json"]
            assert "example" in content and "schema" in content
            assert operation["tags"]
            error_schema = operation["responses"]["422"]["content"]["application/json"]["schema"]
            assert error_schema["$ref"].endswith("/ErrorResponse")
    for suffix in ["latest", "analytics", "trends"]:
        assert (
            "proxy risk"
            in document["paths"]["/api/v1/transformers/{id}/" + suffix]["get"]["description"]
        )
    result = read_client.options(
        "/api/v1/transformers",
        headers={"Origin": "http://localhost:8501", "Access-Control-Request-Method": "GET"},
    )
    assert result.status_code == 200
    assert result.headers["access-control-allow-origin"] == "http://localhost:8501"
    assert "access-control-allow-credentials" not in result.headers


def test_config_values_and_cors_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://localhost:8501", "http://127.0.0.1:8501"]
    assert settings.max_page_limit == 5000
    assert settings.default_window_hours == 24
    assert settings.max_window_days == 31
    for changes in [
        {"default_window_hours": 0},
        {"max_window_days": 0},
        {"max_page_limit": 0},
        {"default_window_hours": 1000},
    ]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **changes)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8501, http://127.0.0.1:8501")
    get_settings.cache_clear()
    assert get_settings().cors_origins == settings.cors_origins


def test_limit_is_configurable(
    read_client: TestClient, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_PAGE_LIMIT", "2")
    get_settings.cache_clear()
    path = f"/api/v1/transformers/{seeded['demo']}/telemetry"
    assert read_client.get(path, params={"limit": 2}).status_code == 200
    assert read_client.get(path, params={"limit": 3}).status_code == 422
