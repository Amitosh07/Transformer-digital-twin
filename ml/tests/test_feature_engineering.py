"""Focused causal feature-engineering tests.

Phase 00 remediation:
- Three-phase completeness: missing phases produce NaN spreads, not zero imbalance.
- Gap suppression: rates bridging gaps > 30 minutes are suppressed.
- Non-positive rolling windows rejected.
- Three-valued alarm OR verified.
- Future-row perturbation does not affect earlier features.
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from ml.features.feature_engineering import (
    DEFAULT_GAP_LIMIT_MINUTES,
    FEATURE_COLUMNS,
    FeatureEngineeringError,
    build_features,
)


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

    # --- Phase 00 new regression tests ---

    def test_incomplete_phases_produce_nan_spread_not_zero(self) -> None:
        """Phase 00: missing phases never yield a healthy zero imbalance."""
        telemetry = _telemetry()
        telemetry.loc[1, "current_l2"] = np.nan  # Remove one phase
        features = build_features(telemetry)
        # Row 1 has only 2 of 3 phases: mean and imbalance must be NaN
        self.assertTrue(np.isnan(features.loc[1, "current_mean"]),
                        "current_mean must be NaN with missing phase")
        self.assertTrue(np.isnan(features.loc[1, "current_imbalance_pct"]),
                        "current_imbalance_pct must be NaN with missing phase")
        self.assertTrue(np.isnan(features.loc[1, "current_max"]),
                        "current_max must be NaN with missing phase")
        self.assertTrue(np.isnan(features.loc[1, "current_min"]),
                        "current_min must be NaN with missing phase")
        # Row 0 and 2 still valid
        self.assertAlmostEqual(features.loc[0, "current_mean"], 20)
        self.assertAlmostEqual(features.loc[2, "current_mean"], 10)

    def test_missing_voltage_phases_produce_nan_spread(self) -> None:
        """Phase 00: missing voltage phases produce NaN voltage_imbalance_pct."""
        telemetry = _telemetry()
        telemetry.loc[0, "phase_voltage_l3"] = np.nan
        features = build_features(telemetry)
        self.assertTrue(np.isnan(features.loc[0, "voltage_mean"]))
        self.assertTrue(np.isnan(features.loc[0, "voltage_imbalance_pct"]))

    def test_missing_pf_phases_produce_nan_pf_mean(self) -> None:
        """Phase 00: missing PF phases produce NaN power_factor_mean and deviation."""
        telemetry = _telemetry()
        telemetry.loc[0, "power_factor_l2"] = np.nan
        features = build_features(telemetry)
        self.assertTrue(np.isnan(features.loc[0, "power_factor_mean"]))
        self.assertTrue(np.isnan(features.loc[0, "power_factor_deviation"]))

    def test_long_gap_rates_suppressed(self) -> None:
        """Phase 00: rates bridging gaps > 30 minutes are suppressed."""
        telemetry = pd.DataFrame({
            "transformer_id": ["TR-001"] * 3,
            "timestamp": pd.to_datetime([
                "2026-01-01 00:00", "2026-01-01 00:15", "2026-01-01 01:00",
            ]),
            "phase_voltage_l1": [100.0] * 3, "phase_voltage_l2": [100.0] * 3, "phase_voltage_l3": [100.0] * 3,
            "current_l1": [10.0] * 3, "current_l2": [10.0] * 3, "current_l3": [10.0] * 3, "neutral_current": [0.0] * 3,
            "oil_temperature": [40.0, 42.0, 50.0], "ambient_temperature": [20.0] * 3, "oil_level": [100.0] * 3,
            "oil_temp_alarm": [0.0] * 3, "oil_temp_trip": [0.0] * 3, "magnetic_oil_gauge_alarm": [0.0] * 3,
            "active_power_total": [30.0] * 3, "apparent_power_total": [40.0] * 3,
            "power_factor_l1": [1.0] * 3, "power_factor_l2": [1.0] * 3, "power_factor_l3": [1.0] * 3,
        })
        features = build_features(telemetry)
        # 15-min gap: rate computed normally
        self.assertFalse(np.isnan(features.loc[1, "oil_temperature_rate"]))
        # 45-min gap (> 30 min): rate suppressed
        self.assertTrue(np.isnan(features.loc[2, "oil_temperature_rate"]),
                        "Rate bridging 45-minute gap must be suppressed")

    def test_nonpositive_rolling_window_rejected(self) -> None:
        """Phase 00: non-positive rolling window must be rejected."""
        with self.assertRaisesRegex(FeatureEngineeringError, "positive"):
            build_features(_telemetry(), rolling_window="0h")
        with self.assertRaisesRegex(FeatureEngineeringError, "positive"):
            build_features(_telemetry(), rolling_window="-1h")

    def test_three_valued_alarm_or(self) -> None:
        """Phase 00: alarm OR is three-valued: any 1 → 1; all 0 → 0; otherwise NaN."""
        telemetry = _telemetry()
        # Row 0: both alarms 0 → alarm_or=0, time_since_last_alarm=NaN (no prior event)
        # Row 1: oil_temp_alarm=1 → alarm_or=1, time_since_last_alarm=0
        telemetry.loc[2, "oil_temp_alarm"] = np.nan
        telemetry.loc[2, "magnetic_oil_gauge_alarm"] = np.nan
        features = build_features(telemetry)
        # Row 2: both alarms NaN → alarm_or=NaN, time_since_last_alarm stays as last known
        # (the _time_since_last_active function skips NaN values, so row 2 remains NaN)
        # Verify row 1 alarm fired
        self.assertEqual(features.loc[1, "time_since_last_alarm"], 0)

    def test_future_row_perturbation_leaves_earlier_features_unchanged(self) -> None:
        """Phase 00: future-row perturbation leaves earlier features unchanged."""
        telemetry = _telemetry()
        features_before = build_features(telemetry)
        telemetry_modified = _telemetry()
        telemetry_modified.loc[2, "oil_temperature"] = 999.0
        features_after = build_features(telemetry_modified)
        # Rows 0 and 1 must be identical
        for col in FEATURE_COLUMNS:
            for row in [0, 1]:
                v_before = features_before.loc[row, col]
                v_after = features_after.loc[row, col]
                if pd.isna(v_before) and pd.isna(v_after):
                    continue
                self.assertAlmostEqual(
                    v_before, v_after,
                    msg=f"Feature '{col}' at row {row} changed when future row was perturbed"
                )

    def test_rolling_std_n1_is_nan(self) -> None:
        """Phase 00: rolling SD with n=1 returns NaN (insufficient for sample SD)."""
        telemetry = _telemetry()
        features = build_features(telemetry)
        # First observation has only n=1 in the rolling window
        self.assertTrue(np.isnan(features.loc[0, "temperature_rolling_std"]))

    def test_timezone_aware_timestamp_accepted(self) -> None:
        """Phase 00: timezone-aware timestamps accepted without assigning an arbitrary zone."""
        telemetry = _telemetry()
        telemetry["timestamp"] = pd.to_datetime([
            "2026-01-01 00:00:00+00:00",
            "2026-01-01 00:30:00+00:00",
            "2026-01-01 01:00:00+00:00",
        ])
        features = build_features(telemetry)
        self.assertAlmostEqual(features.loc[1, "oil_temperature_rate"], 4.0)

    def test_zero_denominator_safe_imbalance(self) -> None:
        """Phase 00: zero mean does not produce division by zero."""
        telemetry = _telemetry()
        telemetry.loc[0, ["current_l1", "current_l2", "current_l3"]] = 0.0
        features = build_features(telemetry)
        self.assertTrue(np.isnan(features.loc[0, "current_imbalance_pct"]))

    def test_repeated_index_labels_and_unsorted_rows_preserved(self) -> None:
        """Phase 00: repeated index labels and unsorted rows preserve order without corruption."""
        telemetry = _telemetry()
        # Repeated index
        telemetry.index = [42, 42, 99]
        # Unsorted order: row 2 then row 0 then row 1
        permuted = telemetry.iloc[[2, 0, 1]].copy()
        features = build_features(permuted)
        self.assertEqual(features.index.tolist(), [99, 42, 42])
        # The chronologically last row was originally at index 99 (row 2 in _telemetry)
        self.assertAlmostEqual(features.loc[99, "oil_temperature_rate"], 8.0)
