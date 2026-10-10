import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
from click.testing import CliRunner
from ml.pipeline.identity import payload_hash
from simulator.cli import cli
from simulator.fleet import load_fleet, load_runtime_config, registry_payloads, register_fleet
from simulator.register_map import encode, decode
from simulator.scheduler import Scheduler

CONFIG = Path(__file__).resolve().parents[1] / 'config'


def test_ten_ids_repeat_deterministically_and_have_isolated_modbus_state():
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    config = load_runtime_config(CONFIG/'operational-server-native.json', 'server', now)
    fleet = load_fleet(CONFIG/'operational-fleet.json')
    expected = [a['transformer_id'] for a in fleet['assets']]
    server, restarted = Scheduler(config), Scheduler(copy.deepcopy(config))
    first, repeated, second = server.tick(), restarted.tick(), server.tick()
    assert list(first) == expected and len(set(expected)) == 10
    for item in fleet['assets']:
        asset = item['transformer_id']
        assert first[asset].model_dump() == repeated[asset].model_dump()
        assert second[asset].timestamp - first[asset].timestamp == timedelta(seconds=5)
        assert second[asset].current_l1 != first[asset].current_l1
        decoded = decode(encode(second[asset], item['unit_id']), transformer_id=asset,
            unit_id=item['unit_id'], gateway_id='KA-BLR-SIM-GW', expected_interval_seconds=5)
        assert decoded.transformer_id == asset
        assert decoded.acquisition['snapshot_id'] == payload_hash(decoded.model_dump(mode='json'))
        assert decoded.acquisition['source_kind'] == 'SIMULATED'
        import jsonschema
        schema = json.loads((CONFIG.parents[1]/'tests/fixtures/hackathon/telemetry.schema.json').read_text(encoding='utf-8'))
        jsonschema.Draft202012Validator(schema).validate(decoded.model_dump(mode='json'))
    untouched = second[expected[1]].model_dump()
    server.advance(expected[0])
    assert server.assets[expected[1]].event_time == config_time(now, 10)
    assert second[expected[1]].model_dump() == untouched
    later = load_runtime_config(CONFIG/'operational-server-native.json', 'server', now + timedelta(hours=1))
    assert [a['transformer_id'] for a in later['assets']] == expected
    assert later['start_utc'] != config['start_utc']
    bridge = load_runtime_config(CONFIG/'operational-bridge-native.json', 'bridge')
    assert [a['transformer_id'] for a in bridge['assets']] == expected
    assert [a['unit_id'] for a in bridge['assets']] == list(range(1, 11))
    affected = copy.deepcopy(config)
    affected['assets'][0]['timeline'] = [dict(from_seconds=0,to_seconds=10,scenario='ALARM_TRIP')]
    isolated = Scheduler(affected).tick()
    assert isolated[expected[0]].oil_temp_trip == 1
    assert all(isolated[a].oil_temp_trip == 0 for a in expected[1:])


def config_time(start, seconds):
    return start + timedelta(seconds=seconds)


def test_idempotent_registration_does_not_seed_or_overwrite():
    stored = {}; counts = {'create': 0}
    def handle(request):
        if request.method == 'GET':
            return httpx.Response(200, json=stored[request.url.path.split('/')[-1]])
        value = json.loads(request.content)
        if value['id'] in stored: return httpx.Response(409)
        stored[value['id']] = value; counts['create'] += 1
        return httpx.Response(201, json=value)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        register_fleet('http://test', CONFIG/'operational-fleet.json', client)
        register_fleet('http://test', CONFIG/'operational-fleet.json', client)
        assert counts['create'] == len(stored) == 10
        stored[next(iter(stored))]['rated_power_kva'] = 99
        with pytest.raises(ValueError, match='conflicts'):
            register_fleet('http://test', CONFIG/'operational-fleet.json', client)


def test_default_seed_and_stream_use_shared_fleet_without_random_ids():
    with patch('simulator.fleet.register_fleet') as seed:
        result = CliRunner().invoke(cli, ['seed'])
        assert result.exit_code == 0, result.output
        seed.assert_called_once()
    with patch('simulator.modbus_bridge.run_bridge') as bridge:
        result = CliRunner().invoke(cli, ['stream'])
        assert result.exit_code == 0, result.output
        bridge.assert_called_once()


def test_duplicate_mapping_and_conflicting_override_rejected(tmp_path):
    value = load_fleet(CONFIG/'operational-fleet.json')
    value['assets'][1]['unit_id'] = 1
    bad = tmp_path/'fleet.json'; bad.write_text(json.dumps(value))
    with pytest.raises(ValueError): load_fleet(bad)
    wrapper = tmp_path/'server.json'; wrapper.write_text(json.dumps({'fleet_file':'fleet.json','assets':[]}))
    with pytest.raises(ValueError): load_runtime_config(wrapper, 'server')
