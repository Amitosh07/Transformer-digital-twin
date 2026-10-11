from datetime import datetime, timezone, timedelta
import itertools
import json
from importlib.resources import files
from pathlib import Path
import math
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from simulator.generator import SyntheticGenerator, thermal_step, coherent_power
from simulator.schema import TransformerConfig, TransformerRecord
from simulator.scheduler import Scheduler
from simulator.faults import FaultInjector

START = datetime(2026, 10, 9, tzinfo=timezone.utc)


def test_deterministic_incremental_and_contract():
    a, b = SyntheticGenerator(seed=42, interval_s=5), SyntheticGenerator(seed=42, interval_s=5)
    iterator = a.iter_records(START)  # intentionally unbounded, lazy
    assert a._step == 0
    records = list(itertools.islice(iterator, 12))
    assert [r.model_dump_json() for r in records] == [r.model_dump_json() for r in b.generate(START, 12)]
    assert a._step == 12
    schema = json.loads((Path(__file__).parents[2] / "tests/fixtures/hackathon/telemetry.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for record in records:
        validator.validate(record.model_dump(mode="json"))
        assert record.acquisition["source_kind"] == "SIMULATED"
        assert record.winding_temperature is None
        assert record.acquisition["field_units"]["winding_temperature"] == "STATUS"


def test_elapsed_thermal_subdivision():
    one = thermal_step(40, 75, 60)
    split = 40
    for _ in range(12):
        split = thermal_step(split, 75, 5)
    assert split == pytest.approx(one, abs=1e-12)
    assert thermal_step(40, 75, 0) == 40


@pytest.mark.parametrize("scenario", ["OVERLOAD", "CURRENT_IMBALANCE", "VOLTAGE_DEVIATION", "ALARM_TRIP"])
def test_final_power_and_actual_dt_energy(scenario):
    cfg = TransformerConfig(transformer_id="FICTIONAL-30", rated_power_kva=30, rated_voltage_lv=400)
    gen = SyntheticGenerator(cfg, seed=7, interval_s=5)
    previous = gen.next_record(START, scenario)
    assert previous.energy_kwh == 0
    for seconds in (5, 17, 90):
        current = gen.next_record(START + timedelta(seconds=seconds), scenario)
        elapsed = (current.timestamp-previous.timestamp).total_seconds()
        assert current.energy_kwh-previous.energy_kwh == pytest.approx((current.active_power_total+previous.active_power_total)/2*elapsed/3600)
        va = sum(getattr(current, f"phase_voltage_l{i}") * getattr(current, f"current_l{i}") for i in (1,2,3))/1000
        w = sum(getattr(current, f"phase_voltage_l{i}") * getattr(current, f"current_l{i}") * getattr(current, f"power_factor_l{i}") for i in (1,2,3))/1000
        assert current.apparent_power_total == pytest.approx(va)
        assert current.active_power_total == pytest.approx(w)
        assert va*va == pytest.approx(w*w + current.reactive_power_total**2)
        if scenario == "OVERLOAD":
            assert 1.3 <= va/cfg.rated_power_kva <= 1.4
        previous = current
    with pytest.raises(ValueError, match="advance"):
        gen.next_record(previous.timestamp)


def test_missing_not_zero_and_line_current():
    record = TransformerRecord(transformer_id="X", timestamp=START, current_l1=None)
    coherent_power(record)
    assert record.active_power_total is None
    cfg = TransformerConfig(rated_power_kva=30, rated_voltage_lv=400)
    gen = SyntheticGenerator(cfg)
    assert gen.config.rated_current_a == pytest.approx(30000/(math.sqrt(3)*400))


def test_standalone_fault_preserves_source_bytes():
    record = SyntheticGenerator().generate(START,1)[0]
    before = record.model_dump_json()
    changed, _ = FaultInjector().inject(record,"OVERLOAD")
    assert record.model_dump_json() == before
    assert changed.apparent_power_total > 500


def test_scheduler_25_assets_isolated():
    config = json.loads((files("simulator") / "config/server-demo-25.json").read_text())
    a, b = Scheduler(config), Scheduler(config)
    a_first, b_first = a.tick(), b.tick()
    assert len(a_first) == 25
    assert len({r.acquisition["snapshot_id"] for r in a_first.values()}) == 25
    assert len({clock.unit_id for clock in a.assets.values()}) == 25
    assert {k:r.model_dump_json() for k,r in a_first.items()} == {k:r.model_dump_json() for k,r in b_first.items()}
    key = list(a.assets)[0]
    for _ in range(25):
        alarm = a.advance(key)
    assert alarm.oil_temp_trip == 1
    other = list(a.assets)[1]
    untouched = a.advance(other)
    expected = b.advance(other)
    assert untouched.model_dump_json() == expected.model_dump_json()
    assert untouched.oil_temp_trip == 0
    bad = json.loads(json.dumps(config))
    bad["assets"][1]["unit_id"] = bad["assets"][0]["unit_id"]
    with pytest.raises(ValueError, match="duplicate"):
        Scheduler(bad)


@pytest.mark.parametrize("change", [{"timestamp":"2026-10-09T00:00:00"}, {"current_l1":float("nan")}, {"current_l1":True}, {"oil_temp_trip":1.0}, {"oil_temp_trip":2}, {"received_at":"2026-10-09T00:00:00Z"}, {"VL12":400}])
def test_invalid_source(change):
    data = {"transformer_id":"X", "timestamp":START, **change}
    with pytest.raises(ValueError):
        TransformerRecord.model_validate(data)
