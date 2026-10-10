from collections.abc import Callable

from fastapi.testclient import TestClient

from app.main import create_app
from app.mqtt.consumer import MqttConsumer
from app.schemas.mqtt import MqttStatus


def test_status_schema_and_openapi(consumer_factory: Callable[..., MqttConsumer]) -> None:
    application = create_app()
    with TestClient(application) as client:
        response = client.get("/api/v1/ingest/mqtt/status")
        assert response.status_code == 200
        assert set(response.json()) == set(MqttStatus.model_fields)
        assert response.json()["enabled"] is False
        application.state.mqtt_consumer = consumer_factory()
        assert client.get("/api/v1/ingest/mqtt/status").json() == (
            application.state.mqtt_consumer.status()
        )
        document = client.get("/openapi.json").json()
        operation = document["paths"]["/api/v1/ingest/mqtt/status"]["get"]
        example = operation["responses"]["200"]["content"]["application/json"]["example"]
        assert set(example) == set(MqttStatus.model_fields)
        assert "connected=false" in operation["description"]
        assert MqttStatus.model_validate(example).enabled is True
