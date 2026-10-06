"""Environment configuration; optional integrations are disabled by default."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://transformer:transformer@localhost:5432/transformer"
    env: str = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    schema_version: str = "1.0.0"
    default_transformer_id: str = "TX-001"
    ml_backend: Literal["stub", "python", "http"] = "stub"
    ml_http_url: str | None = None
    ml_python_entrypoint: str | None = None
    ml_history_window: int = Field(default=60, ge=1)
    cors_origins: list[str] = Field(default_factory=list)
    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = Field(default=1883, ge=1, le=65535)
    mqtt_topic: str = "transformers/telemetry"

    @field_validator("database_url")
    @classmethod
    def require_postgres(cls, value: str) -> str:
        if make_url(value).drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value

    @field_validator("ml_http_url", "ml_python_entrypoint", mode="before")
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
