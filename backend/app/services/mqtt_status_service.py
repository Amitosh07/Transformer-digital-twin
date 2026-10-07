"""Disabled status can be built without importing the MQTT transport."""

from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.schemas.mqtt import MqttStatus


class StatusProvider(Protocol):
    def status(self) -> dict[str, Any]: ...


def initial_status(settings: Settings) -> dict[str, Any]:
    return MqttStatus(
        enabled=settings.mqtt_enabled,
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        topic=settings.mqtt_topic,
        qos=settings.mqtt_qos,
    ).model_dump(mode="json")


def mqtt_status(consumer: StatusProvider | None) -> dict[str, Any]:
    return consumer.status() if consumer is not None else initial_status(get_settings())
