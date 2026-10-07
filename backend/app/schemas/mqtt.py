"""Public MQTT diagnostics contain configuration and counters, never credentials."""

from datetime import datetime

from pydantic import BaseModel, Field


class MqttRejection(BaseModel):
    time: datetime
    topic: str
    reason: str
    field: str | None = None


class MqttStatus(BaseModel):
    enabled: bool
    connected: bool = False
    host: str
    port: int
    topic: str
    qos: int
    queue_depth: int = 0
    received_count: int = 0
    ingested_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    dropped_count: int = 0
    error_count: int = 0
    last_message_at: datetime | None = None
    last_error: str | None = None
    recent_rejections: list[MqttRejection] = Field(default_factory=list)
