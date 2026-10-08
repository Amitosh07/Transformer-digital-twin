"""Focused tests for the configuration-driven Thermal Twin."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from ml.features.feature_engineering import build_features
from ml.thermal.thermal_twin import ThermalTwinConfig, ThermalTwinError, run_thermal_twin


def _thermal_features() -> pd.DataFrame:
    telemetry = pd.DataFrame({
        "transformer_id": ["TR-001"] * 3,
        "timestamp": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:30", "2026-01-01 01:00"]),
        "phase_voltage_l1": [100.0] * 3, "phase_voltage_l2": [100.0] * 3, "phase_voltage_l3": [100.0] * 3,
        "current_l1": [10.0] * 3, "current_l2": [10.0] * 3, "current_l3": [10.0] * 3, "neutral_current": [0.0] * 3,
        "oil_temperature": [30.0, 32.0, 40.0], "ambient_temperature": [20.0] * 3, "oil_level": [10.0] * 3,
        "oil_temp_alarm": [0.0] * 3, "oil_temp_trip": [0.0] * 3, "magnetic_oil_gauge_alarm": [0.0] * 3,
        "active_power_total": [100.0, 100.0, 200.0], "apparent_power_total": [100.0, 100.0, 200.0],
        "power_factor_l1": [1.0] * 3, "power_factor_l2": [1.0] * 3, "power_factor_l3": [1.0] * 3,
    })
    return build_features(telemetry)


class ThermalTwinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ThermalTwinConfig(
            load_gain=0.1,
            response_alpha=0.5,
            normal_residual_abs_max=1.0,
            elevated_residual_abs_max=3.0,
        )

    def test_dynamic_baseline_residual_and_state(self) -> None:
        result = run_thermal_twin(_thermal_features(), self.config)
        self.assertAlmostEqual(result.loc[0, "thermal_model_temperature"], 30)
        self.assertAlmostEqual(result.loc[1, "thermal_model_temperature"], 30)
        self.assertAlmostEqual(result.loc[2, "thermal_model_temperature"], 35)
        self.assertAlmostEqual(result.loc[1, "thermal_residual"], 2)
        self.assertAlmostEqual(result.loc[2, "thermal_residual"], 5)
        self.assertEqual(result.loc[0, "thermal_state"], "NORMAL")
        self.assertEqual(result.loc[1, "thermal_state"], "ELEVATED")
        self.assertEqual(result.loc[2, "thermal_state"], "CRITICAL")

    def test_future_observations_do_not_change_prior_model_output(self) -> None:
        features = _thermal_features()
        baseline = run_thermal_twin(features, self.config)
        features.loc[2, "oil_temperature"] = 999.0
        altered = run_thermal_twin(features, self.config)
        self.assertEqual(baseline.loc[0, "thermal_model_temperature"], altered.loc[0, "thermal_model_temperature"])
        self.assertEqual(baseline.loc[1, "thermal_model_temperature"], altered.loc[1, "thermal_model_temperature"])

    def test_missing_readings_are_not_imputed_and_invalid_config_fails(self) -> None:
        features = _thermal_features()
        features.loc[1, "ambient_temperature"] = np.nan
        features.loc[2, "active_power_demand"] = np.nan
        result = run_thermal_twin(features, self.config)
        self.assertTrue(pd.isna(result.loc[1, "thermal_model_temperature"]))
        self.assertTrue(pd.isna(result.loc[1, "thermal_residual"]))
        self.assertTrue(pd.isna(result.loc[1, "thermal_state"]))
        self.assertTrue(pd.isna(result.loc[2, "thermal_model_temperature"]))
        self.assertTrue(pd.isna(result.loc[2, "thermal_residual"]))
        self.assertTrue(pd.isna(result.loc[2, "thermal_state"]))
        with self.assertRaisesRegex(ThermalTwinError, "response_alpha"):
            ThermalTwinConfig(0.1, 0.0, 1.0, 3.0)

    def test_longer_elapsed_time_produces_stronger_state_response(self) -> None:
        features = pd.DataFrame({
            "transformer_id": ["TR-001"] * 3,
            "timestamp": pd.to_datetime([
                "2026-01-01 00:00", "2026-01-01 00:01", "2026-01-01 00:16",
            ]),
            "oil_temperature": [20.0, 20.0, 20.0],
            "ambient_temperature": [20.0] * 3,
            "active_power_demand": [0.0, 100.0, 200.0],
        })
        result = run_thermal_twin(features, self.config)

        short_gap_response = result.loc[1, "thermal_model_temperature"] - 20.0
        long_gap_response = result.loc[2, "thermal_model_temperature"] - result.loc[1, "thermal_model_temperature"]
        self.assertGreater(long_gap_response, short_gap_response)

    def test_transformers_are_processed_independently(self) -> None:
        features = pd.DataFrame({
            "transformer_id": ["TR-002", "TR-001", "TR-002", "TR-001"],
            "timestamp": pd.to_datetime([
                "2026-01-01 00:00", "2026-01-01 00:00",
                "2026-01-01 00:01", "2026-01-01 00:16",
            ]),
            "oil_temperature": [20.0, 30.0, 20.0, 30.0],
            "ambient_temperature": [20.0] * 4,
            "active_power_demand": [0.0, 0.0, 100.0, 200.0],
        })
        result = run_thermal_twin(features, self.config)

        self.assertAlmostEqual(result.loc[2, "thermal_model_temperature"], 25.0)
        self.assertAlmostEqual(result.loc[3, "thermal_model_temperature"], 35.0)
