import json
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.ml_client.factory import close_ml_client
from app.mqtt.consumer import MqttConsumer


class FakeClient:
    def __init__(self) -> None:
        self.subscriptions: list[tuple[str, int]] = []
        self.calls: list[Any] = []

    def reconnect_delay_set(self, minimum: int, maximum: int) -> None:
        self.calls.append(("reconnect", minimum, maximum))

    def username_pw_set(self, username: str, password: str | None) -> None:
        self.calls.append(("credentials", username, password))

    def connect_async(self, host: str, port: int) -> None:
        self.calls.append(("connect", host, port))

    def loop_start(self) -> None:
        self.calls.append("loop_start")

    def disconnect(self) -> None:
        self.calls.append("disconnect")

    def loop_stop(self) -> None:
        self.calls.append("loop_stop")

    def subscribe(self, topic: str, qos: int) -> None:
        self.subscriptions.append((topic, qos))

    def emit(self, topic: str, value: Any) -> None:
        payload = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.on_message(self, None, SimpleNamespace(topic=topic, payload=payload))


@pytest.fixture(autouse=True)
def mqtt_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MQTT_ENABLED", "false")
    monkeypatch.setenv("MQTT_TOPIC", "transformer/+/telemetry")
    monkeypatch.setenv("MAX_BATCH_SIZE", "5000")
    monkeypatch.setenv("ML_BACKEND", "stub")
    get_settings.cache_clear()
    close_ml_client()
    yield
    close_ml_client()
    get_settings.cache_clear()


@pytest.fixture
def asset_id() -> str:
    return f"TX-mqtt-{uuid4().hex[:12]}"


@pytest.fixture
def payload(asset_id: str) -> dict[str, Any]:
    return {
        "transformer_id": asset_id,
        "timestamp": "2026-10-07T09:00:00Z",
        "oil_temperature": 42,
        "oil_level": 8,
        "scenario_id": "mqtt-demo",
    }


@pytest.fixture
def consumer_factory(db_engine: Engine) -> Iterator[Callable[..., MqttConsumer]]:
    consumers: list[MqttConsumer] = []

    def make(**kwargs: Any) -> MqttConsumer:
        consumer = MqttConsumer(
            client=kwargs.pop("client", FakeClient()),
            session_factory=sessionmaker(db_engine, expire_on_commit=False),
            **kwargs,
        )
        consumers.append(consumer)
        return consumer

    yield make
    for consumer in consumers:
        consumer.stop()
