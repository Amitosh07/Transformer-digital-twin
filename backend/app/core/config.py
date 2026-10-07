"""Environment configuration; optional integrations are disabled by default."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
    ml_timeout_seconds: float = Field(default=5.0, gt=0, allow_inf_nan=False)
    ml_max_retries: int = Field(default=2, ge=0)
    max_batch_size: int = Field(default=5000, ge=1)
    cors_origins: list[str] = Field(default_factory=list)
    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = Field(default=1883, ge=1, le=65535)
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = Field(default="transformer-backend", min_length=1)
    mqtt_topic: str = Field(default="transformer/+/telemetry", min_length=1)
    mqtt_qos: int = Field(default=1, ge=0, le=2)
    mqtt_queue_max: int = Field(default=10000, ge=1)
    mqtt_source_name: str = Field(default="mqtt", min_length=1, max_length=255)
    mqtt_reconnect_min_s: int = Field(default=1, ge=1)
    mqtt_reconnect_max_s: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def mqtt_configuration(self) -> "Settings":
        if self.mqtt_reconnect_max_s < self.mqtt_reconnect_min_s:
            raise ValueError("MQTT_RECONNECT_MAX_S must be >= MQTT_RECONNECT_MIN_S")
        segments = self.mqtt_topic.split("/")
        if segments.count("+") > 1:
            raise ValueError("MQTT_TOPIC permits at most one identity wildcard")
        for index, segment in enumerate(segments):
            if ("+" in segment and segment != "+") or (
                "#" in segment and (segment != "#" or index != len(segments) - 1)
            ):
                raise ValueError("MQTT_TOPIC contains an invalid wildcard")
        return self

    @field_validator("database_url")
    @classmethod
    def require_postgres(cls, value: str) -> str:
        if make_url(value).drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value

    @field_validator(
        "ml_http_url", "ml_python_entrypoint", "mqtt_username", "mqtt_password", mode="before"
    )
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
