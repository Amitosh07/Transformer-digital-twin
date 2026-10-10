import builtins
from time import monotonic
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.mqtt.consumer import MqttConsumer
from tests.mqtt.conftest import FakeClient


def test_disabled_imports_and_starts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    original = builtins.__import__

    def guard(name: str, *args: Any, **kwargs: Any) -> Any:
        assert not name.startswith("app.mqtt"), "Disabled lifespan imported MQTT"
        return original(name, *args, **kwargs)

    application = create_app()
    with monkeypatch.context() as context:
        context.setattr(builtins, "__import__", guard)
        with TestClient(application) as client:
            assert not hasattr(application.state, "mqtt_consumer")
            assert client.get("/api/v1/ingest/mqtt/status").json()["enabled"] is False


def test_unreachable_broker_keeps_app_healthy(
    monkeypatch: pytest.MonkeyPatch, db_engine: Engine
) -> None:
    monkeypatch.setenv("MQTT_ENABLED", "true")
    monkeypatch.setenv("MQTT_HOST", "127.0.0.1")
    monkeypatch.setenv("MQTT_PORT", "51884")
    get_settings.cache_clear()
    application = create_app()
    with Session(db_engine) as session:
        application.dependency_overrides[get_db] = lambda: session
        before = monotonic()
        with TestClient(application) as client:
            assert monotonic() - before < 2
            assert client.get("/health").json()["db"] == "ok"
            status = client.get("/api/v1/ingest/mqtt/status")
            assert status.status_code == 200
            assert status.json()["enabled"] is True
            assert status.json()["connected"] is False
        assert not application.state.mqtt_consumer._worker.is_alive()


def test_consumer_stops_before_ml_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_ENABLED", "true")
    get_settings.cache_clear()
    consumer = MqttConsumer(client=FakeClient())
    order: list[str] = []
    original_stop = consumer.stop

    def stop() -> None:
        original_stop()
        order.append("mqtt")

    with patch("app.mqtt.consumer.MqttConsumer", return_value=consumer):
        with patch.object(consumer, "stop", side_effect=stop):
            with patch("app.main.close_ml_client", side_effect=lambda: order.append("ml")):
                with TestClient(create_app()):
                    pass
    assert order == ["mqtt", "ml"]
