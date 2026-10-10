"""
Schema conformance tests — simulator_README §13.

Verify that every generated record conforms to dataschema.md:
  • All fields use canonical names.
  • Required fields (transformer_id, timestamp) are present.
  • Alarm/trip fields are 0 or 1 (not temperature values).
  • Excluded fields (VL12, VL23, VL31) never appear.
  • Missing data is None — never silently zero.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from simulator.faults import SCENARIO_CATALOGUE, FaultInjector
from simulator.generator import SyntheticGenerator
from simulator.schema import EXCLUDED_SOURCE_FIELDS, TransformerConfig, TransformerRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_records(count: int = 10, seed: int = 42) -> list[TransformerRecord]:
    cfg = TransformerConfig(transformer_id="TX-TEST")
    gen = SyntheticGenerator(config=cfg, seed=seed)
    return gen.generate(start=_dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc), count=count)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchemaConformance:
    """Verify generated records match dataschema.md."""

    def test_required_identity_fields(self) -> None:
        for rec in _make_records():
            assert rec.transformer_id is not None
            assert rec.transformer_id != ""
            assert rec.timestamp is not None

    def test_canonical_field_names(self) -> None:
        """All field names in the record must be canonical names from dataschema.md."""
        canonical_names = set(TransformerRecord.model_fields.keys())
        for rec in _make_records():
            record_fields = set(rec.model_dump().keys())
            assert record_fields.issubset(canonical_names), (
                f"Non-canonical fields found: {record_fields - canonical_names}"
            )

    def test_excluded_fields_absent(self) -> None:
        """VL12, VL23, VL31 must never appear in any output."""
        for rec in _make_records():
            data = rec.model_dump()
            for excluded in EXCLUDED_SOURCE_FIELDS:
                assert excluded not in data
                assert excluded.lower() not in data

    def test_alarm_trip_are_boolean(self) -> None:
        """Alarm/trip fields must be 0 or 1, not temperature values."""
        for rec in _make_records():
            for field_name in ("oil_temp_alarm", "oil_temp_trip", "magnetic_oil_gauge_alarm"):
                val = getattr(rec, field_name)
                if val is not None:
                    assert val in (0, 1), f"{field_name} = {val}, expected 0 or 1"

    def test_no_silent_zero_fill(self) -> None:
        """
        Generator should produce floats for measurement fields (not None
        in normal mode), but this test ensures the schema allows None and
        does not silently convert None → 0.
        """
        rec = TransformerRecord(
            transformer_id="TX-NULL",
            timestamp=_dt.datetime.now(_dt.timezone.utc),
        )
        # All measurement fields should be None, not 0
        assert rec.oil_temperature is None
        assert rec.current_l1 is None
        assert rec.active_power_total is None


# ---------------------------------------------------------------------------
# Generator coherence tests
# ---------------------------------------------------------------------------

class TestGeneratorCoherence:
    """Verify generated data is physically plausible (not independently random)."""

    def test_power_follows_current(self) -> None:
        """Apparent power should be correlated with current magnitude."""
        records = _make_records(100)
        for rec in records:
            if all(v is not None for v in [rec.current_l1, rec.current_l2, rec.current_l3, rec.apparent_power_total]):
                i_avg = (rec.current_l1 + rec.current_l2 + rec.current_l3) / 3.0
                # Apparent power should be positive and roughly proportional to current
                assert rec.apparent_power_total > 0
                # Very loose check — just that both are positive when current is positive
                if i_avg > 10:
                    assert rec.apparent_power_total > 1.0

    def test_oil_temp_above_ambient(self) -> None:
        """Oil temperature should generally be above ambient (transformer heats oil)."""
        records = _make_records(100)
        above_count = sum(
            1 for r in records
            if r.oil_temperature is not None and r.ambient_temperature is not None
            and r.oil_temperature > r.ambient_temperature
        )
        assert above_count > 80, "Oil temp should be above ambient in > 80 % of normal records"

    def test_energy_cumulative(self) -> None:
        """energy_kwh should be monotonically increasing."""
        records = _make_records(50)
        energies = [r.energy_kwh for r in records if r.energy_kwh is not None]
        for i in range(1, len(energies)):
            assert energies[i] >= energies[i - 1], "energy_kwh must be non-decreasing"

    def test_power_factor_in_range(self) -> None:
        """Power factors should be in [0, 1]."""
        for rec in _make_records(100):
            for pf_field in ("power_factor_l1", "power_factor_l2", "power_factor_l3"):
                val = getattr(rec, pf_field)
                if val is not None:
                    assert 0.0 <= val <= 1.0, f"{pf_field} = {val}, out of [0,1]"


# ---------------------------------------------------------------------------
# Fault injection tests — scenario tests (§13)
# ---------------------------------------------------------------------------

class TestFaultInjection:
    """Verify each fault scenario modifies the expected canonical fields."""

    @pytest.fixture
    def base_records(self) -> list[TransformerRecord]:
        return _make_records(5)

    @pytest.fixture
    def injector(self) -> FaultInjector:
        return FaultInjector(seed=99)

    def test_all_scenarios_registered(self) -> None:
        required = {
            "HEALTHY", "OVERLOAD", "THERMAL_STRESS", "RAPID_TEMPERATURE_RISE",
            "CURRENT_IMBALANCE", "VOLTAGE_DEVIATION", "LOW_OIL_LEVEL",
            "ALARM_TRIP", "SENSOR_ANOMALY",
        }
        assert required.issubset(set(SCENARIO_CATALOGUE.keys()))

    def test_healthy_no_change(self, base_records, injector) -> None:
        for rec in base_records:
            mutated, meta = injector.inject(rec, "HEALTHY")
            assert mutated.current_l1 == rec.current_l1
            assert mutated.oil_temperature == rec.oil_temperature

    def test_overload_increases_current(self, base_records, injector) -> None:
        for rec in base_records:
            mutated, _ = injector.inject(rec, "OVERLOAD")
            if rec.current_l1 is not None:
                assert mutated.current_l1 > rec.current_l1

    def test_thermal_stress_increases_temp(self, base_records, injector) -> None:
        for rec in base_records:
            mutated, _ = injector.inject(rec, "THERMAL_STRESS")
            if rec.oil_temperature is not None:
                assert mutated.oil_temperature > rec.oil_temperature

    def test_current_imbalance_reduces_l2(self, base_records, injector) -> None:
        for rec in base_records:
            mutated, _ = injector.inject(rec, "CURRENT_IMBALANCE")
            if rec.current_l2 is not None and rec.current_l2 > 0:
                assert mutated.current_l2 < rec.current_l2

    def test_voltage_deviation_sags_l3(self, base_records, injector) -> None:
        for rec in base_records:
            mutated, _ = injector.inject(rec, "VOLTAGE_DEVIATION")
            if rec.phase_voltage_l3 is not None:
                assert mutated.phase_voltage_l3 < rec.phase_voltage_l3

    def test_low_oil_activates_alarm(self, base_records, injector) -> None:
        for rec in base_records:
            mutated, _ = injector.inject(rec, "LOW_OIL_LEVEL")
            assert mutated.magnetic_oil_gauge_alarm == 1

    def test_alarm_trip_both_active(self, base_records, injector) -> None:
        for rec in base_records:
            mutated, _ = injector.inject(rec, "ALARM_TRIP")
            assert mutated.oil_temp_alarm == 1
            assert mutated.oil_temp_trip == 1

    def test_injected_record_still_valid(self, base_records, injector) -> None:
        """Every mutated record must still be a valid TransformerRecord."""
        for scenario_name in SCENARIO_CATALOGUE:
            for rec in base_records:
                mutated, _ = injector.inject(rec, scenario_name)
                # Re-validate through Pydantic
                validated = TransformerRecord.model_validate(mutated.model_dump())
                assert validated.transformer_id == rec.transformer_id

    def test_scenario_metadata_complete(self) -> None:
        """Every scenario must have an id, severity, and expected_response."""
        for name, meta in SCENARIO_CATALOGUE.items():
            assert meta.scenario_id, f"{name} missing scenario_id"
            assert meta.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL"), (
                f"{name} invalid severity: {meta.severity}"
            )
            if name != "HEALTHY":
                assert len(meta.expected_response) > 0, f"{name} missing expected_response"
