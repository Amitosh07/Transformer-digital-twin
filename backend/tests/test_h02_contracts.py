"""H02 boundary checks using established H00 examples, not the H00 suite."""
import copy
import json
from pathlib import Path
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas.telemetry import TelemetryIn, TelemetryOut
from app.schemas.transformer import TransformerIn, TransformerPatch
from app.schemas.analytics import AnalyticsOut
from app.schemas.query import AnalyticsPoint
from app.models.analytics import Analytics
from app.ml_client.base import parse_ml_result, MLClientError
from app.repositories.analytics_repo import persistence_values
from app.services.semantic_payload import digest, canonical
from app.mqtt.message_handler import parse_message, MessageRejected

FIXTURES = Path(__file__).resolve().parents[2] / 'tests/fixtures/hackathon'


def example(name):
    return copy.deepcopy(next(row['payload'] for row in json.loads(
        (FIXTURES / 'examples.json').read_text(encoding='utf-8')) if row['name'] == name))


def test_acquisition_and_unknown_legacy_round_trip():
    raw = example('telemetry-valid')
    source = TelemetryIn.model_validate(raw)
    serialized = source.model_dump(mode='json')
    assert serialized['acquisition'] == raw['acquisition']
    out = TelemetryOut.model_validate(serialized | {'id': 1, 'is_missing_critical': False,
        'received_at': '2026-10-09T00:00:01Z'})
    assert out.model_dump(mode='json')['acquisition'] == raw['acquisition']
    legacy = TelemetryIn(transformer_id='legacy', timestamp='2026-10-09T00:00:00Z')
    assert legacy.acquisition is None and legacy.oil_temperature is None
    with pytest.raises(ValidationError):
        TelemetryIn.model_validate(raw | {'received_at': '2026-10-09T00:00:01Z'})


def test_backend_uses_frozen_hash_vectors():
    vectors = json.loads((FIXTURES / 'hash-vectors.json').read_text(encoding='utf-8'), parse_float=Decimal)
    for vector in vectors:
        for raw in vector['equivalent_inputs']:
            # These are hash contexts: server/retry keys are not source POST fields.
            payload = {k:v for k,v in raw.items() if k in TelemetryIn.model_fields}
            record = TelemetryIn.model_validate(payload)
            assert canonical(record) == vector['canonical_utf8']
            assert digest(record) == vector['sha256']
        for raw in vector['different_inputs']:
            assert digest(TelemetryIn.model_validate(raw)) != vector['sha256']


def test_mqtt_retains_decimal_semantics_and_rejects_duplicate_keys():
    a = parse_message('transformer/precision/telemetry',
        b'{"timestamp":"2026-10-09T00:00:00Z","oil_temperature":42.000000000000001}')[0]
    b = parse_message('transformer/precision/telemetry',
        b'{"timestamp":"2026-10-09T00:00:00Z","oil_temperature":42.000000000000002}')[0]
    assert a.oil_temperature == b.oil_temperature
    assert digest(a) != digest(b)
    with pytest.raises(MessageRejected, match='INVALID_JSON'):
        parse_message('transformer/precision/telemetry', b'{"timestamp":null,"timestamp":null}')


def test_metadata_survives_ml_orm_and_history_serialization():
    raw = example('analytics-valid')
    parsed = parse_ml_result(raw)
    row = Analytics(telemetry_id=1, **persistence_values(parsed))
    response = AnalyticsOut.model_validate(row).model_dump(mode='json')
    point = AnalyticsPoint.model_validate(row).model_dump(mode='json')
    assert response['metadata'] == parsed.metadata.model_dump(mode='json')
    assert point['metadata'] == response['metadata']
    assert response['fault_risk'] is None
    assert row.ml_metadata is not Analytics(telemetry_id=2).ml_metadata


def test_registry_nullable_removal_and_units():
    raw = example('asset-valid')
    asset = TransformerIn.model_validate(raw)
    assert asset.configuration_metadata.status == 'SYNTHETIC_CONFIG'
    patch = TransformerPatch(ct_ratio=None)
    assert patch.model_dump(exclude_unset=True) == {'ct_ratio': None}
    for changes in ({'rated_power_kva': -1}, {'ct_ratio': {'primary': 100, 'secondary': 0, 'unit': 'A'}}):
        with pytest.raises(ValidationError):
            TransformerIn.model_validate(raw | changes)
    bad = copy.deepcopy(raw)
    bad['configuration_metadata']['field_metadata']['rated_power_kva']['unit'] = 'W'
    with pytest.raises(ValidationError):
        TransformerIn.model_validate(bad)


def test_unreleased_operational_forecast_rejected():
    raw = example('analytics-valid')
    with pytest.raises(MLClientError):
        parse_ml_result(raw | {'fault_risk': 0.8})
