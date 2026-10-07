"""
Fault injection library - simulator_README §7, §8, §14.

Each scenario mutates a canonical TransformerRecord in a deterministic,
physically plausible way and carries ScenarioMetadata describing the
injection and expected downstream Digital Twin response.

Required scenarios (§7):
  OVERLOAD, HIGH_TEMPERATURE, RAPID_TEMPERATURE_RISE, CURRENT_IMBALANCE,
  VOLTAGE_DEVIATION, LOW_OIL_LEVEL, ALARM/TRIP ACTIVATION, SENSOR_ANOMALY

Demo scenarios (§14):
  1. Healthy
  2. Overload
  3. Thermal Stress
  4. Current Imbalance
  5. Low Oil / Alarm
"""

from __future__ import annotations

import copy
import datetime as _dt
from typing import Callable, Optional

import numpy as np

from .schema import ScenarioMetadata, TransformerRecord


# ---------------------------------------------------------------------------
# Scenario catalogue
# ---------------------------------------------------------------------------

def _scenario_healthy() -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id="SCN_HEALTHY_01",
        description="Normal healthy operation - baseline reference.",
        severity="LOW",
        injected_variables=[],
        expected_response=[
            "health index stays high (>=80)",
            "anomaly score stays low",
            "maintenance priority stays NORMAL",
        ],
    )


def _scenario_overload() -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id="SCN_OVERLOAD_01",
        description="All three phase currents raised to ~130 % of rated.",
        severity="HIGH",
        injected_variables=["current_l1", "current_l2", "current_l3",
                            "active_power_total", "apparent_power_total"],
        expected_response=[
            "loading increases",
            "thermal stress increases",
            "anomaly score increases",
            "health index decreases",
            "maintenance priority increases",
        ],
    )


def _scenario_thermal_stress() -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id="SCN_THERMAL_STRESS_01",
        description="Oil temperature elevated with rapid rise rate.",
        severity="HIGH",
        injected_variables=["oil_temperature", "winding_temperature"],
        expected_response=[
            "thermal residual rises",
            "anomaly score increases",
            "health index decreases",
            "fault risk increases",
            "maintenance recommendation mentions thermal",
        ],
    )


def _scenario_rapid_temp_rise() -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id="SCN_RAPID_TEMP_RISE_01",
        description="Rapid temperature ramp (+5 source units per step).",
        severity="CRITICAL",
        injected_variables=["oil_temperature", "winding_temperature"],
        expected_response=[
            "temperature rate feature spikes",
            "anomaly detected",
            "health index degrades rapidly",
            "maintenance priority URGENT",
        ],
    )


def _scenario_current_imbalance() -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id="SCN_CURRENT_IMBALANCE_01",
        description="Phase L2 current dropped to ~40 % while L1/L3 stay normal.",
        severity="MEDIUM",
        injected_variables=["current_l2", "neutral_current"],
        expected_response=[
            "current imbalance percent rises",
            "neutral current magnitude rises",
            "anomaly detected",
            "health index decreases",
        ],
    )


def _scenario_voltage_deviation() -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id="SCN_VOLTAGE_DEV_01",
        description="Phase L3 voltage sags by ~15 %.",
        severity="MEDIUM",
        injected_variables=["phase_voltage_l3"],
        expected_response=[
            "voltage imbalance percent rises",
            "anomaly detected",
        ],
    )


def _scenario_low_oil_level() -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id="SCN_LOW_OIL_01",
        description="Oil level drops progressively; MOG alarm activates.",
        severity="HIGH",
        injected_variables=["oil_level", "magnetic_oil_gauge_alarm"],
        expected_response=[
            "oil level deviation increases",
            "MOG alarm flag set",
            "health index decreases",
            "maintenance recommendation mentions oil",
        ],
    )


def _scenario_alarm_trip() -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id="SCN_ALARM_TRIP_01",
        description="Oil temperature alarm and trip both activate.",
        severity="CRITICAL",
        injected_variables=["oil_temp_alarm", "oil_temp_trip",
                            "oil_temperature", "winding_temperature"],
        expected_response=[
            "alarm condition degrades",
            "health index drops sharply",
            "fault risk high",
            "maintenance priority URGENT",
        ],
    )


def _scenario_sensor_anomaly() -> ScenarioMetadata:
    return ScenarioMetadata(
        scenario_id="SCN_SENSOR_ANOMALY_01",
        description="Oil temperature sensor outputs erratic spikes / freezes.",
        severity="MEDIUM",
        injected_variables=["oil_temperature"],
        expected_response=[
            "anomaly score increases",
            "thermal residual becomes erratic",
            "maintenance recommendation mentions sensor inspection",
        ],
    )


# ---------------------------------------------------------------------------
# Catalogue registry
# ---------------------------------------------------------------------------

SCENARIO_CATALOGUE: dict[str, ScenarioMetadata] = {
    "HEALTHY":                _scenario_healthy(),
    "OVERLOAD":               _scenario_overload(),
    "THERMAL_STRESS":         _scenario_thermal_stress(),
    "RAPID_TEMPERATURE_RISE": _scenario_rapid_temp_rise(),
    "CURRENT_IMBALANCE":      _scenario_current_imbalance(),
    "VOLTAGE_DEVIATION":      _scenario_voltage_deviation(),
    "LOW_OIL_LEVEL":          _scenario_low_oil_level(),
    "ALARM_TRIP":             _scenario_alarm_trip(),
    "SENSOR_ANOMALY":         _scenario_sensor_anomaly(),
}


# ---------------------------------------------------------------------------
# Injection functions - mutate a record
# ---------------------------------------------------------------------------

class FaultInjector:
    """
    Applies a named fault scenario to a canonical TransformerRecord.

    The injector returns a *new* record (the input is not mutated).
    """

    def __init__(self, seed: int = 99) -> None:
        self.rng = np.random.default_rng(seed)
        self._rapid_temp_counter: int = 0    # accumulator for ramp scenario

    def inject(
        self,
        record: TransformerRecord,
        scenario_name: str,
    ) -> tuple[TransformerRecord, ScenarioMetadata]:
        """
        Return *(mutated_record, metadata)* for the given scenario.

        Raises ``KeyError`` if *scenario_name* is not in the catalogue.
        """
        meta = SCENARIO_CATALOGUE[scenario_name]
        fn = _INJECTION_FNS.get(scenario_name)
        if fn is None or scenario_name == "HEALTHY":
            return record.model_copy(), meta

        mutated = record.model_copy()
        fn(self, mutated)
        return mutated, meta

    # -- individual injectors (mutate *rec* in place) ----------------------

    def _inject_overload(self, rec: TransformerRecord) -> None:
        factor = 1.3 + self.rng.uniform(0, 0.1)
        if rec.current_l1 is not None:
            rec.current_l1 = round(rec.current_l1 * factor, 2)
        if rec.current_l2 is not None:
            rec.current_l2 = round(rec.current_l2 * factor, 2)
        if rec.current_l3 is not None:
            rec.current_l3 = round(rec.current_l3 * factor, 2)
        if rec.active_power_total is not None:
            rec.active_power_total = round(rec.active_power_total * factor, 2)
        if rec.apparent_power_total is not None:
            rec.apparent_power_total = round(rec.apparent_power_total * factor, 2)

    def _inject_thermal_stress(self, rec: TransformerRecord) -> None:
        if rec.oil_temperature is not None:
            rec.oil_temperature = round(rec.oil_temperature + 25.0 + self.rng.normal(0, 2), 1)
        if rec.winding_temperature is not None:
            rec.winding_temperature = round(rec.winding_temperature + 30.0 + self.rng.normal(0, 2), 1)

    def _inject_rapid_temp_rise(self, rec: TransformerRecord) -> None:
        self._rapid_temp_counter += 1
        ramp = 5.0 * self._rapid_temp_counter
        if rec.oil_temperature is not None:
            rec.oil_temperature = round(rec.oil_temperature + ramp, 1)
        if rec.winding_temperature is not None:
            rec.winding_temperature = round(rec.winding_temperature + ramp + 3, 1)

    def _inject_current_imbalance(self, rec: TransformerRecord) -> None:
        if rec.current_l2 is not None:
            rec.current_l2 = round(rec.current_l2 * 0.4, 2)
        if rec.neutral_current is not None and rec.current_l1 is not None:
            rec.neutral_current = round(abs(rec.current_l1 - (rec.current_l2 or 0)) * 0.7, 2)

    def _inject_voltage_deviation(self, rec: TransformerRecord) -> None:
        if rec.phase_voltage_l3 is not None:
            rec.phase_voltage_l3 = round(rec.phase_voltage_l3 * 0.85, 2)

    def _inject_low_oil_level(self, rec: TransformerRecord) -> None:
        if rec.oil_level is not None:
            rec.oil_level = round(max(10.0, rec.oil_level - 40.0 + self.rng.normal(0, 1)), 1)
        rec.magnetic_oil_gauge_alarm = 1

    def _inject_alarm_trip(self, rec: TransformerRecord) -> None:
        rec.oil_temp_alarm = 1
        rec.oil_temp_trip = 1
        if rec.oil_temperature is not None:
            rec.oil_temperature = round(rec.oil_temperature + 35.0, 1)
        if rec.winding_temperature is not None:
            rec.winding_temperature = round(rec.winding_temperature + 40.0, 1)

    def _inject_sensor_anomaly(self, rec: TransformerRecord) -> None:
        if rec.oil_temperature is not None:
            if self.rng.random() < 0.5:
                # Spike
                rec.oil_temperature = round(rec.oil_temperature + self.rng.uniform(40, 80), 1)
            else:
                # Freeze to a constant
                rec.oil_temperature = round(rec.oil_temperature * 0.0 + 25.0, 1)


# Map scenario names → bound methods (populated after class body)
_INJECTION_FNS: dict[str, Callable[[FaultInjector, TransformerRecord], None]] = {
    "OVERLOAD":               FaultInjector._inject_overload,
    "THERMAL_STRESS":         FaultInjector._inject_thermal_stress,
    "RAPID_TEMPERATURE_RISE": FaultInjector._inject_rapid_temp_rise,
    "CURRENT_IMBALANCE":      FaultInjector._inject_current_imbalance,
    "VOLTAGE_DEVIATION":      FaultInjector._inject_voltage_deviation,
    "LOW_OIL_LEVEL":          FaultInjector._inject_low_oil_level,
    "ALARM_TRIP":             FaultInjector._inject_alarm_trip,
    "SENSOR_ANOMALY":         FaultInjector._inject_sensor_anomaly,
}
