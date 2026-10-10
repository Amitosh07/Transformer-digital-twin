"""H06 historical pre-roll and explicit container binding only."""
import json
from pathlib import Path
import pytest
from simulator.modbus_server import SimulationServer


def config():
    return json.loads((Path(__file__).parents[1] / 'config/hackathon-native-server.json').read_text())


def test_preroll_uses_declared_event_time_then_forward_cadence():
    server = SimulationServer(config())
    first = server.snapshots['H06-SIM-05']
    assert first.timestamp.isoformat() == '2026-10-09T00:00:00+00:00'
    assert first.acquisition['sequence'] == 60
    next_record = server.scheduler.advance('H06-SIM-05')
    assert (next_record.timestamp-first.timestamp).total_seconds() == 5
    assert next_record.acquisition['sequence'] == 61


def test_container_bind_requires_explicit_opt_in():
    value = config(); value.pop('container_network', None); value['host'] = '0.0.0.0'
    with pytest.raises(ValueError, match='loopback'):
        SimulationServer(value)
    value['container_network'] = True
    assert SimulationServer(value).host == '0.0.0.0'


def test_preroll_is_bounded():
    value = config(); value['pre_roll_steps'] = 10001
    with pytest.raises(ValueError, match='bounded pre-roll'):
        SimulationServer(value)
