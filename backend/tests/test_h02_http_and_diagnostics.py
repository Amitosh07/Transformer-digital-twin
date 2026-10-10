"""HTTP decoding and bounded MQTT diagnostics; no SQL/broker substitution."""
from fastapi.testclient import TestClient
from app.main import create_app
from app.db.session import get_db
from app.core.config import Settings
from app.schemas.ingestion import IngestResult
from app.schemas.telemetry import TelemetryIn
from app.services.semantic_payload import digest
from app.repositories.telemetry_repo import SemanticConflict
from app.mqtt.consumer import MqttConsumer
from tests.mqtt.conftest import FakeClient


def test_http_decimals_and_invalid_json_reach_contract(monkeypatch):
    import app.api.v1.telemetry as route
    captured = []
    def accept(db, record, run_ml):
        captured.append(record)
        return IngestResult(telemetry_id=len(captured), snapshot_id=digest(record))
    monkeypatch.setattr(route, 'ingest_record', accept)
    application = create_app()
    application.dependency_overrides[get_db] = lambda: object()
    with TestClient(application) as client:
        for number in ('42.000000000000001', '42.000000000000002'):
            response = client.post('/api/v1/telemetry', content=(
                '{"transformer_id":"precision","timestamp":"2026-10-09T00:00:00Z","oil_temperature":'+number+'}'),
                headers={'content-type':'application/json'})
            assert response.status_code == 201
        assert digest(captured[0]) != digest(captured[1])
        for payload in ('{"oil_temperature":NaN}', '{"timestamp":null,"timestamp":null}'):
            assert client.post('/api/v1/telemetry', content=payload,
                               headers={'content-type':'application/json'}).status_code == 422


def test_mqtt_rejections_conflicts_and_validation_counts_are_bounded():
    settings = Settings(_env_file=None, mqtt_queue_max=1, ml_backend='stub')
    consumer = MqttConsumer(FakeClient(), settings=settings)
    consumer._accepting = True
    consumer.client.emit('transformer/wrong/telemetry', {'transformer_id':'other','timestamp':'2026-10-09T00:00:00Z'})
    assert consumer.status()['last_error'] == 'TOPIC_ID_MISMATCH'
    record = TelemetryIn(transformer_id='a', timestamp='2026-10-09T00:00:00Z')
    for _ in range(30):
        consumer._worker_error(record, SemanticConflict(record, 'a'*64))
    status = consumer.status()
    assert status['conflicted_count'] == 30
    assert status['last_error'] == 'SEMANTIC_PAYLOAD_CONFLICT'
    assert len(status['recent_rejections']) == 20
    for _ in range(2):
        consumer.client.emit('transformer/a/telemetry', {'timestamp':'2026-10-09T00:00:00Z'})
    assert consumer.status()['validated_count'] == 2
    assert consumer.status()['dropped_count'] == 1
    assert consumer.status()['committed_count'] == 0
