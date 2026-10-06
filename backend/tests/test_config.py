import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.schema_version == "1.0.0"
    assert settings.default_transformer_id == "TX-001"
    assert settings.ml_backend == "stub"
    assert settings.ml_history_window == 60
    assert settings.mqtt_enabled is False
    assert settings.max_batch_size == 5000


def test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:8501"]')
    monkeypatch.setenv("ML_HTTP_URL", "")
    monkeypatch.setenv("ML_PYTHON_ENTRYPOINT", "")
    monkeypatch.setenv("ML_BACKEND", "http")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://localhost:8501"]
    assert settings.ml_http_url is None
    assert settings.ml_python_entrypoint is None
    assert settings.ml_backend == "http"


@pytest.mark.parametrize(
    "field,value",
    [
        ("database_url", "sqlite:///test.db"),
        ("ml_backend", "invalid"),
        ("ml_history_window", 0),
        ("mqtt_port", 65536),
        ("max_batch_size", 0),
        ("log_level", "INVALID"),
    ],
)
def test_invalid_configuration(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_settings_are_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()
