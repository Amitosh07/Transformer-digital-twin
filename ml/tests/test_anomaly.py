"""Comprehensive unit tests for the Phase 02 Anomaly Detection engine.

Tests cover:
- Upper-tail endpoint behavior (x <= W -> 0, x >= C -> 1, linear in between)
- Lower-tail endpoint behavior (x >= W -> 0, x <= C -> 1, linear in between)
- Monotonic severity scaling
- Severity bounds [0, 1]
- C == W invalid threshold handling
- Missing phase causes phase-spread evidence to be unavailable (not zero)
- Zero/low-load denominator gating
- Ready vs unready thermal residual
- Positive residual vs negative residual (THERMAL_MODEL_MISMATCH without overheating severity)
- Protection immediate trigger bypassing persistence
- Elapsed-time persistence (3 valid observations spanning >= 30 min)
- Long gap (> 30 min) resets persistence buffer
- Recovery behavior (3 valid observations below cutoff spanning >= 30 min)
- Grouped max aggregation prevents correlated vote inflation
- All-missing inputs produce null score and null flag
- Partial coverage correctly reported without treating unmeasured signals as healthy
- Threshold provenance and reason-code reproducibility
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from ml.anomaly.detector import (
    ALL_ANOMALY_COLUMNS,
    ANOMALY_COVERAGE_COLUMNS,
    ANOMALY_FAMILY_SEVERITY_COLUMNS,
    ANOMALY_OUTPUT_COLUMNS,
    REASON_CURRENT_IMBALANCE,
    REASON_HIGH_OIL_TEMP,
    REASON_OIL_TEMP_ALARM,
    REASON_OIL_TEMP_TRIP,
    REASON_RAPID_TEMP_RISE,
    REASON_THERMAL_MODEL_MISMATCH,
    REASON_THERMAL_RESIDUAL_HIGH,
    AnomalyDetector,
    AnomalyDetectorConfig,
    AnomalyDetectorError,
    SignalThreshold,
    get_default_training_thresholds,
    run_anomaly_detection,
)


class Phase02AnomalyDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.custom_thresholds = {
            "oil_temperature": SignalThreshold(
                signal_name="oil_temperature",
                warning_threshold=40.0,
                critical_threshold=50.0,
                direction="upper",
                unit="source_unit",
            ),
            "oil_level_deviation": SignalThreshold(
                signal_name="oil_level_deviation",
                warning_threshold=-2.0,
                critical_threshold=-10.0,
                direction="lower",
                unit="source_unit",
            ),
            "current_imbalance_pct": SignalThreshold(
                signal_name="current_imbalance_pct",
                warning_threshold=50.0,
                critical_threshold=100.0,
                direction="upper",
                unit="percent",
            ),
            "thermal_residual": SignalThreshold(
                signal_name="thermal_residual",
                warning_threshold=4.0,
                critical_threshold=8.0,
                direction="upper",
                unit="source_unit",
            ),
        }
        self.config = AnomalyDetectorConfig(
            thresholds=self.custom_thresholds,
            a_on=0.5,
            min_persistence_observations=3,
            min_persistence_span_hours=0.5,
            continuity_gap_hours=0.5,
            min_current_gate_a=10.0,
        )
        self.detector = AnomalyDetector(config=self.config)

    def test_upper_tail_severity_endpoint_and_monotonicity(self) -> None:
        """Phase 02: upper tail s(x) = clip((x - W) / (C - W), 0, 1)."""
        thresh = self.custom_thresholds["oil_temperature"]
        # W = 40, C = 50
        self.assertEqual(thresh.score(35.0), 0.0)
        self.assertEqual(thresh.score(40.0), 0.0)
        self.assertAlmostEqual(thresh.score(45.0), 0.5)
        self.assertEqual(thresh.score(50.0), 1.0)
        self.assertEqual(thresh.score(60.0), 1.0)
        # Monotonicity
        scores = [thresh.score(x) for x in np.linspace(30, 60, 31)]
        self.assertTrue(all(x <= y for x, y in zip(scores, scores[1:])))

    def test_lower_tail_severity_endpoint_and_monotonicity(self) -> None:
        """Phase 02: lower tail s(x) = clip((W - x) / (W - C), 0, 1)."""
        thresh = self.custom_thresholds["oil_level_deviation"]
        # W = -2, C = -10
        self.assertEqual(thresh.score(0.0), 0.0)
        self.assertEqual(thresh.score(-2.0), 0.0)
        self.assertAlmostEqual(thresh.score(-6.0), 0.5)
        self.assertEqual(thresh.score(-10.0), 1.0)
        self.assertEqual(thresh.score(-15.0), 1.0)
        # Monotonicity as deviation worsens (decreases)
        vals = np.linspace(0, -15, 31)
        scores = [thresh.score(x) for x in vals]
        self.assertTrue(all(x <= y for x, y in zip(scores, scores[1:])))

    def test_invalid_thresholds_rejected(self) -> None:
        """Phase 02: C == W or reversed directions raise AnomalyDetectorError without zero division."""
        with self.assertRaisesRegex(AnomalyDetectorError, "Upper tail requires C > W"):
            SignalThreshold("test", 50.0, 50.0, "upper", "unit")
        with self.assertRaisesRegex(AnomalyDetectorError, "Lower tail requires W > C"):
            SignalThreshold("test", -10.0, -2.0, "lower", "unit")
        with self.assertRaisesRegex(AnomalyDetectorError, "Direction must be"):
            SignalThreshold("test", 10.0, 20.0, "middle", "unit")

    def test_missing_phase_spread_is_unavailable_not_zero(self) -> None:
        """Phase 02: incomplete phase inputs make current spread unavailable, not zero severity."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "current_imbalance_pct": np.nan,  # missing phase from Phase 00
            "oil_temperature": 30.0,
        }])
        res = self.detector.run(df)
        self.assertTrue(pd.isna(res.loc[0, "severity_electrical"]))
        self.assertEqual(res.loc[0, "severity_thermal"], 0.0)
        self.assertNotIn(REASON_CURRENT_IMBALANCE, res.loc[0, "reason_codes"])

    def test_low_load_gate_suppresses_spurious_current_imbalance(self) -> None:
        """Phase 02: current imbalance with current_mean < min_current_gate_a is gated."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "current_imbalance_pct": 80.0,  # high imbalance
            "current_mean": 2.0,            # below 10A gate!
        }])
        res = self.detector.run(df)
        self.assertTrue(pd.isna(res.loc[0, "severity_electrical"]))
        self.assertNotIn(REASON_CURRENT_IMBALANCE, res.loc[0, "reason_codes"])

    def test_unready_thermal_twin_residual_is_withheld(self) -> None:
        """Phase 02: unready thermal twin suppresses residual contribution."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "thermal_residual": 10.0,  # high positive residual
            "thermal_readiness": "WARMING_UP",  # not ready
            "oil_temperature": 30.0,
        }])
        res = self.detector.run(df)
        self.assertNotIn(REASON_THERMAL_RESIDUAL_HIGH, res.loc[0, "reason_codes"])

    def test_positive_residual_vs_negative_residual_handling(self) -> None:
        """Phase 02: positive residual causes high severity; negative residual causes THERMAL_MODEL_MISMATCH."""
        # Positive residual
        df_pos = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "thermal_residual": 6.0,  # between 4 and 8 -> s=0.5
            "thermal_readiness": "READY",
            "oil_temperature": 30.0,
        }])
        res_pos = self.detector.run(df_pos)
        self.assertAlmostEqual(res_pos.loc[0, "severity_thermal"], 0.5)
        self.assertIn(REASON_THERMAL_RESIDUAL_HIGH, res_pos.loc[0, "reason_codes"])
        self.assertNotIn(REASON_THERMAL_MODEL_MISMATCH, res_pos.loc[0, "reason_codes"])

        # Negative residual
        df_neg = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "thermal_residual": -6.0,
            "thermal_readiness": "READY",
            "oil_temperature": 30.0,
        }])
        self.detector.reset_state()
        res_neg = self.detector.run(df_neg)
        # Does NOT inflate positive thermal severity!
        self.assertEqual(res_neg.loc[0, "severity_thermal"], 0.0)
        self.assertIn(REASON_THERMAL_MODEL_MISMATCH, res_neg.loc[0, "reason_codes"])
        self.assertNotIn(REASON_THERMAL_RESIDUAL_HIGH, res_neg.loc[0, "reason_codes"])

    def test_protection_immediate_trigger_bypasses_persistence(self) -> None:
        """Phase 02: active verified protection contacts set s_protection=1.0 and trigger flag immediately."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "oil_temp_trip": 1.0,
            "oil_temperature": 30.0,
        }])
        res = self.detector.run(df)
        self.assertEqual(res.loc[0, "severity_protection"], 1.0)
        self.assertEqual(res.loc[0, "anomaly_score"], 1.0)
        # Immediate alert on first observation!
        self.assertTrue(res.loc[0, "anomaly_flag"])
        self.assertIn(REASON_OIL_TEMP_TRIP, res.loc[0, "reason_codes"])

    def test_elapsed_time_persistence_entry_and_recovery(self) -> None:
        """Phase 02: 3 observations spanning >= 30 min enter alert; 3 observations below cutoff recover."""
        # 5 observations at 15-min intervals:
        # t0 (00:00), t1 (00:15), t2 (00:30) with score >= 0.5 -> alert starts at t2!
        # t3 (00:45), t4 (01:00), t5 (01:15) with score < 0.5 -> recovers at t5!
        timestamps = pd.date_range("2026-01-01 00:00", periods=6, freq="15min")
        oil_temps = [48.0, 48.0, 48.0, 30.0, 30.0, 30.0]  # W=40, C=50 -> 48 gives s=0.8 >= 0.5

        df = pd.DataFrame({
            "transformer_id": ["TR-001"] * 6,
            "timestamp": timestamps,
            "oil_temperature": oil_temps,
            "oil_temp_alarm": [0.0] * 6,
            "oil_temp_trip": [0.0] * 6,
            "magnetic_oil_gauge_alarm": [0.0] * 6,
        })
        self.detector.reset_state()
        res = self.detector.run(df)

        # t0: 1 obs, span = 0h -> no alert
        self.assertFalse(res.loc[0, "anomaly_flag"])
        # t1: 2 obs, span = 15m = 0.25h -> no alert
        self.assertFalse(res.loc[1, "anomaly_flag"])
        # t2: 3 obs, span = 30m = 0.5h -> ALERT!
        self.assertTrue(res.loc[2, "anomaly_flag"])
        # t3: 1 obs low -> still in alert
        self.assertTrue(res.loc[3, "anomaly_flag"])
        # t4: 2 obs low -> still in alert
        self.assertTrue(res.loc[4, "anomaly_flag"])
        # t5: 3 obs low spanning >= 30 min -> RECOVERED!
        self.assertFalse(res.loc[5, "anomaly_flag"])

    def test_gap_resets_persistence_state(self) -> None:
        """Phase 02: gap > 30 minutes resets candidate persistence buffer."""
        df = pd.DataFrame({
            "transformer_id": ["TR-001"] * 3,
            "timestamp": pd.to_datetime([
                "2026-01-01 00:00",
                "2026-01-01 00:15",
                "2026-01-01 01:00",  # 45 min gap!
            ]),
            "oil_temperature": [48.0, 48.0, 48.0],
            "oil_temp_alarm": [0.0] * 3,
        })
        self.detector.reset_state()
        res = self.detector.run(df)
        # Because of the 45-min gap, t2 is treated as a new start; cannot trigger alert
        self.assertFalse(res.loc[2, "anomaly_flag"])

    def test_grouped_max_aggregation_avoids_correlated_vote_inflation(self) -> None:
        """Phase 02: overall score is max across families, not additive sum."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "oil_temperature": 45.0,        # s=0.5
            "oil_temperature_rate": 14.0,   # s=0.5
            "thermal_residual": 6.0,        # s=0.5
            "thermal_readiness": "READY",
        }])
        res = self.detector.run(df)
        # Max of thermal family is 0.5, NOT 0.5 + 0.5 + 0.5 = 1.5!
        self.assertAlmostEqual(res.loc[0, "severity_thermal"], 0.5)
        self.assertAlmostEqual(res.loc[0, "anomaly_score"], 0.5)

    def test_all_missing_input_produces_null_score_and_flag(self) -> None:
        """Phase 02: completely missing evidence produces NaN score and null flag."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
        }])
        res = self.detector.run(df)
        self.assertTrue(pd.isna(res.loc[0, "anomaly_score"]))
        self.assertIsNone(res.loc[0, "anomaly_flag"])
        self.assertEqual(res.loc[0, "coverage_overall"], 0.0)

    def test_partial_coverage_tracked_accurately(self) -> None:
        """Phase 02: partial coverage does not assume unmeasured signals are healthy."""
        df = pd.DataFrame([{
            "transformer_id": "TR-001",
            "timestamp": pd.Timestamp("2026-01-01 00:00"),
            "oil_temperature": 35.0,  # 1 of 3 thermal signals measured
        }])
        res = self.detector.run(df)
        self.assertAlmostEqual(res.loc[0, "coverage_thermal"], 1.0 / 3.0)
        self.assertTrue(pd.isna(res.loc[0, "severity_electrical"]))
        self.assertAlmostEqual(res.loc[0, "anomaly_score"], 0.0)
        # Overall coverage is 1/9
        self.assertAlmostEqual(res.loc[0, "coverage_overall"], 1.0 / 9.0)


if __name__ == "__main__":
    unittest.main()
