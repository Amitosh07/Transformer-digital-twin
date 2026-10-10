import os
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import paho.mqtt.client as mqtt
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.mqtt.consumer import MqttConsumer
from tests.mqtt.test_consumer import counts, wait_for


@pytest.fixture
def broker_consumer(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[MqttConsumer]:
    host = os.getenv("MQTT_TEST_HOST")
    if not host:
        pytest.skip("Set MQTT_TEST_HOST and MQTT_TEST_PORT to run the real Mosquitto test")
    monkeypatch.setenv("MQTT_ENABLED", "true")
    monkeypatch.setenv("MQTT_HOST", host)
    monkeypatch.setenv("MQTT_PORT", os.getenv("MQTT_TEST_PORT", "1883"))
    monkeypatch.setenv("MQTT_CLIENT_ID", f"backend-test-{uuid4().hex}")
    get_settings.cache_clear()
    consumer = MqttConsumer(session_factory=sessionmaker(db_engine, expire_on_commit=False))
    consumer.start()
    try:
        wait_for(lambda: consumer.status()["connected"], 8)
        yield consumer
    finally:
        consumer.stop()


def test_real_broker_to_postgres(
    broker_consumer: MqttConsumer, db_engine: Engine, payload: dict[str, Any]
) -> None:
    import json

    settings = get_settings()
    publisher = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=f"publisher-test-{uuid4().hex}"
    )
    publisher.connect(settings.mqtt_host, settings.mqtt_port)
    publisher.loop_start()
    try:
        topic = f"transformer/{payload['transformer_id']}/telemetry"
        for expected in (1, 2):
            delivery = publisher.publish(topic, json.dumps(payload), qos=1)
            delivery.wait_for_publish(5)
            assert delivery.is_published()
            wait_for(
                lambda expected=expected: broker_consumer.status()["received_count"] >= expected
            )
        wait_for(lambda: broker_consumer.status()["duplicate_count"] == 1)
        assert counts(db_engine, payload["transformer_id"]) == (1, 1)
        assert broker_consumer.status()["ingested_count"] == 1
        assert broker_consumer.status()["error_count"] == 0
    finally:
        publisher.disconnect()
        publisher.loop_stop()
