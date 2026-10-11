"""Real PostgreSQL active-scope pagination; legacy rows are never removed."""
import json
from pathlib import Path
import pytest
from app.core.config import get_settings
from app.core.operational_fleet import active_ids
from app.schemas.transformer import TransformerIn

FLEET = Path(__file__).resolve().parents[3] / 'simulator/config/operational-fleet.json'


def test_default_active_fleet_order_pagination_and_legacy_lookup(read_client, monkeypatch):
    ids = active_ids(str(FLEET))
    monkeypatch.setenv('OPERATIONAL_FLEET_FILE', str(FLEET))
    get_settings.cache_clear()
    for asset in [*reversed(ids), 'LEGACY-RETAINED']:
        assert read_client.post('/api/v1/transformers', json={'id':asset,'name':asset}).status_code == 201
    for _ in range(2):
        first = read_client.get('/api/v1/transformers?limit=5').json()
        second = read_client.get('/api/v1/transformers?limit=5&offset=5').json()
        assert first['total'] == second['total'] == 10
        assert [a['id'] for a in first['items']] == ids[:5]
        assert [a['id'] for a in second['items']] == ids[5:]
    assert read_client.get('/api/v1/transformers?scope=all&limit=5000').json()['total'] >= 11
    assert read_client.get('/api/v1/transformers/LEGACY-RETAINED').status_code == 200
    assert read_client.get('/api/v1/transformers?scope=unknown').status_code == 422
    assert read_client.get('/api/v1/transformers?offset=10').json()['items'] == []


def test_config_fail_closed_and_requested_ids_need_no_schema_change(tmp_path):
    ids = active_ids(str(FLEET))
    assert len(ids) == len(set(ids)) == 10
    assert all(TransformerIn(id=a, name=a).id == a for a in ids)
    assert all(not a.startswith('H07-') for a in ids)
    assert active_ids(None) is None
    value = json.loads(FLEET.read_text())
    value['assets'][1]['transformer_id'] = ids[0]
    path = tmp_path/'bad.json'; path.write_text(json.dumps(value))
    with pytest.raises(ValueError): active_ids(str(path))
