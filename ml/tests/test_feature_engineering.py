"""Focused causal feature-engineering tests."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from ml.features.feature_engineering import FEATURE_COLUMNS, FeatureEngineeringError, build_features


def _telemetry() -> pd.DataFrame:
    return pd.DataFrame({
        "transformer_id": ["TR-001"] * 3,
        "timestamp": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:30", "2026-01-01 01:00"]),
        "phase_voltage_l1": [100.0, 100.0, 100.0], "phase_voltage_l2": [110.0, 100.0, 100.0], "phase_voltage_l3": [120.0, 100.0, 100.0],
        "current_l1": [10.0, 10.0, 10.0], "current_l2": [20.0, 10.0, 10.0], "current_l3": [30.0, 10.0, 10.0], "neutral_current": [-2.0, 3.0, np.nan],
        "oil_temperature": [40.0, 42.0, 46.0], "ambient_temperature": [20.0, 21.0, 22.0], "oil_level": [100.0, 98.0, 97.0],
        "oil_temp_alarm": [0.0, 1.0, 0.0], "oil_temp_trip": [0.0, 0.0, 1.0], "magnetic_oil_gauge_alarm": [0.0, 0.0, 0.0],
        "active_power_total": [30.0, 35.0, 40.0], "apparent_power_total": [40.0, 50.0, 60.0],
        "power_factor_l1": [0.9, 1.0, 1.0], "power_factor_l2": [0.9, 1.0, 1.0], "power_factor_l3": [0.9, 1.0, 1.0],
    })


class FeatureEngineeringTests(unittest.TestCase):
    def test_electrical_and_contract_features(self) -> None:
        features = build_features(_telemetry())
        self.assertAlmostEqual(features.loc[0, "current_mean"], 20)
        self.assertAlmostEqual(features.loc[0, "current_imbalance_pct"], 100)
        self.assertAlmostEqual(features.loc[0, "voltage_imbalance_pct"], 20 / 110 * 100)
        self.assertEqual(features.loc[0, "neutral_current_magnitude"], 2)
        self.assertAlmostEqual(features.loc[0, "power_factor_deviation"], 0.1)
        self.assertTrue(features["apparent_power_utilization"].isna().all())
        self.assertTrue(features["thermal_residual"].isna().all())
        self.assertTrue(set(FEATURE_COLUMNS).issubset(features.columns))

    def test_time_features_are_causal_and_rates_are_time_aware(self) -> None:
        features = build_features(_telemetry(), rolling_window="1h")
        self.assertTrue(np.isnan(features.loc[0, "oil_temperature_rate"]))
        self.assertAlmostEqual(features.loc[1, "oil_temperature_rate"], 4)
        self.assertAlmostEqual(features.loc[2, "oil_temperature_rate"], 8)
        self.assertAlmostEqual(features.loc[1, "temperature_rolling_mean"], 41)
        self.assertAlmostEqual(features.loc[2, "rolling_load_mean"], 55)
        self.assertTrue(np.isnan(features.loc[0, "oil_level_deviation"]))
        self.assertAlmostEqual(features.loc[1, "oil_level_deviation"], -2)
        self.assertEqual(features.loc[1, "time_since_last_alarm"], 0)
        self.assertAlmostEqual(features.loc[2, "time_since_last_alarm"], 0.5)
        self.assertEqual(features.loc[2, "time_since_last_trip"], 0)

    def test_oil_level_baseline_excludes_current_observation(self) -> None:
        telemetry = _telemetry()
        telemetry["timestamp"] = pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:30", "2026-01-01 00:45"])
        telemetry["oil_level"] = [10.0, 20.0, 999.0]
        features = build_features(telemetry, rolling_window="1h")
        self.assertAlmostEqual(features.loc[2, "oil_level_rolling_mean"], 15)
        self.assertAlmostEqual(features.loc[2, "oil_level_deviation"], 984)

    def test_input_order_is_preserved_while_history_uses_timestamp_order(self) -> None:
        telemetry = _telemetry().iloc[[2, 0, 1]].copy()
        features = build_features(telemetry)
        self.assertEqual(features.index.tolist(), telemetry.index.tolist())
        self.assertAlmostEqual(features.loc[2, "oil_temperature_rate"], 8)

    def test_missing_values_are_not_imputed(self) -> None:
        features = build_features(_telemetry())
        self.assertTrue(np.isnan(features.loc[2, "neutral_current_magnitude"]))

    def test_invalid_or_duplicate_canonical_timestamps_fail(self) -> None:
        duplicate = _telemetry()
        duplicate.loc[1, "timestamp"] = duplicate.loc[0, "timestamp"]
        with self.assertRaisesRegex(FeatureEngineeringError, "duplicate"):
            build_features(duplicate)
        invalid = _telemetry().drop(columns="oil_level")
        with self.assertRaisesRegex(FeatureEngineeringError, "missing required"):
            build_features(invalid)
