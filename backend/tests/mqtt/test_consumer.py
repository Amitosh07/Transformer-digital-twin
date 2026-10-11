from collections.abc import Callable
from threading import Event
from time import monotonic, sleep
from typing import Any
from unittest.mock import patch

import paho.mqtt.client as paho
import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ml_client.factory import get_ml_client
from app.models.analytics import Analytics
from app.models.telemetry import Telemetry
from app.mqtt.consumer import MqttConsumer
from app.services import ingestion_service
from tests.mqtt.conftest import FakeClient


def wait_for(predicate: Callable[[], bool], timeout: float = 5) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.01)
    assert predicate(), "Timed out waiting for MQTT processing"


def counts(engine: Engine, asset: str) -> tuple[int, int]:
    with Session(engine) as session:
        return tuple(
            session.scalar(
                select(func.count()).select_from(model).where(model.transformer_id == asset)
            )
            for model in (Telemetry, Analytics)
        )


def test_persist_duplicate_and_stop_drain(
    consumer_factory: Callable[..., MqttConsumer], payload: dict[str, Any], db_engine: Engine
) -> None:
    consumer = consumer_factory()
    asset = payload["transformer_id"]
    client = consumer.client
    ml = get_ml_client()
    with patch.object(
        ingestion_service, "ingest_record", wraps=ingestion_service.ingest_record
    ) as call:
        with patch.object(ml, "analyze", wraps=ml.analyze) as analyze:
            consumer.start()
            client.emit(f"transformer/{asset}/telemetry", payload)
            client.emit(f"transformer/{asset}/telemetry", payload)
            consumer.stop()
            assert call.call_count == 2
            assert all(c.kwargs["run_ml"] is True for c in call.call_args_list)
            assert analyze.call_count == 1
    assert counts(db_engine, asset) == (1, 1)
    assert consumer.status()["ingested_count"] == 1
    assert consumer.status()["duplicate_count"] == 1
    assert consumer.status()["queue_depth"] == 0
    assert not consumer._worker.is_alive()
    assert client.calls[-2:] == ["disconnect", "loop_stop"]
    with Session(db_engine) as session:
        record = session.scalar(select(Telemetry).where(Telemetry.transformer_id == asset))
        assert record.source_name is None
        assert record.scenario_id == "mqtt-demo"
        assert record.current_l1 is None


def test_worker_rolls_back_entire_array_and_survives(
    consumer_factory: Callable[..., MqttConsumer],
    payload: dict[str, Any],
    db_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    consumer = consumer_factory()
    real = ingestion_service.ingest_record
    second = {**payload, "timestamp": "2026-10-07T09:00:01Z"}

    def fail(session: Session, record: Any, **kwargs: Any) -> Any:
        if record.timestamp.second == 1:
            raise RuntimeError("secret-database-content")
        return real(session, record, **kwargs)

    with patch.object(ingestion_service, "ingest_record", side_effect=fail):
        consumer.start()
        consumer.client.emit(
            f"transformer/{payload['transformer_id']}/telemetry", [payload, second]
        )
        wait_for(lambda: consumer.status()["error_count"] == 1)
        assert counts(db_engine, payload["transformer_id"]) == (0, 0)
        consumer.client.emit(f"transformer/{payload['transformer_id']}/telemetry", payload)
        consumer.stop()
    assert counts(db_engine, payload["transformer_id"]) == (1, 1)
    assert consumer.status()["ingested_count"] == 1
    assert consumer.status()["error_count"] == 1
    assert "secret-database-content" not in caplog.text
    assert "secret" not in str(consumer.status())


def test_rejections_ring_buffer(
    consumer_factory: Callable[..., MqttConsumer], caplog: pytest.LogCaptureFixture
) -> None:
    consumer = consumer_factory()
    consumer.start()
    for _ in range(25):
        consumer.client.emit("transformer/TX-invalid/telemetry", b"secret-invalid-payload")
    consumer.stop()
    status = consumer.status()
    assert status["received_count"] == status["rejected_count"] == 25
    assert len(status["recent_rejections"]) == 20
    assert status["recent_rejections"][0]["reason"] == "INVALID_JSON"
    assert "secret" not in str(status) + caplog.text


def test_queue_full_drops_without_blocking(
    consumer_factory: Callable[..., MqttConsumer], payload: dict[str, Any]
) -> None:
    consumer = consumer_factory(settings=get_settings().model_copy(update={"mqtt_queue_max": 1}))
    entered, release = Event(), Event()
    real = ingestion_service.ingest_record

    def blocked(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert release.wait(5)
        return real(*args, **kwargs)

    with patch.object(ingestion_service, "ingest_record", side_effect=blocked):
        try:
            consumer.start()
            topic = f"transformer/{payload['transformer_id']}/telemetry"
            consumer.client.emit(topic, payload)
            assert entered.wait(5)
            consumer.client.emit(topic, payload)
            before = monotonic()
            consumer.client.emit(topic, payload)
            assert monotonic() - before < 0.5
            assert consumer.status()["dropped_count"] == 1
            assert consumer.status()["queue_depth"] == 1
        finally:
            release.set()
            consumer.stop()
    assert consumer.status()["ingested_count"] == 1
    assert consumer.status()["duplicate_count"] == 1


def test_connect_resubscribes_and_configuration() -> None:
    client = FakeClient()
    settings = get_settings().model_copy(
        update={"mqtt_qos": 2, "mqtt_username": "user", "mqtt_password": "password"}
    )
    consumer = MqttConsumer(client=client, settings=settings)
    assert client.calls[:2] == [("reconnect", 1, 30), ("credentials", "user", "password")]
    for _ in range(2):
        client.on_connect(client, None, {}, 0, None)
        assert consumer.status()["connected"] is True
        client.on_disconnect(client, None, {}, 1, None)
        assert consumer.status()["connected"] is False
    assert client.subscriptions == [(settings.mqtt_topic, 2)] * 2
    client.on_connect(client, None, {}, 1, None)
    assert len(client.subscriptions) == 2
    client.on_connect_fail(client, None)
    assert consumer.status()["last_error"] == "BROKER_UNREACHABLE"
    assert "password" not in str(consumer.status())


def test_real_client_v2_persistent_session() -> None:
    with patch("app.mqtt.consumer.mqtt.Client", wraps=paho.Client) as create:
        consumer = MqttConsumer()
        assert create.call_args.kwargs["callback_api_version"] == paho.CallbackAPIVersion.VERSION2
        assert create.call_args.kwargs["clean_session"] is False
        assert create.call_args.kwargs["client_id"] == "transformer-backend"
    consumer.stop()


def test_stop_is_bounded_and_stops_accepting(
    consumer_factory: Callable[..., MqttConsumer], payload: dict[str, Any]
) -> None:
    consumer = consumer_factory()
    entered, release = Event(), Event()
    real = ingestion_service.ingest_record

    def blocked(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert release.wait(5)
        return real(*args, **kwargs)

    with patch.object(ingestion_service, "ingest_record", side_effect=blocked):
        try:
            consumer.start()
            topic = f"transformer/{payload['transformer_id']}/telemetry"
            consumer.client.emit(topic, payload)
            assert entered.wait(5)
            consumer.client.emit(topic, payload)
            before = monotonic()
            consumer.stop(timeout=0.1)
            assert monotonic() - before < 0.5
            assert consumer.status()["last_error"] == "SHUTDOWN_TIMEOUT"
            assert consumer.status()["dropped_count"] == 1
            received = consumer.status()["received_count"]
            consumer.client.emit(topic, payload)
            assert consumer.status()["received_count"] == received
        finally:
            release.set()
            consumer._worker.join(5)
