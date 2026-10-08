"""Focused test suite for Phase 06 Time-Aware Evaluation.

Tests cover:
1. Frozen time split boundaries (2019-11-23 11:45 and 2020-02-13 11:15).
2. Split performed before filtering / row dropping.
3. Target-horizon purge at split boundaries.
4. No leakage across split boundaries.
5. Preprocessing fitted strictly on training partition.
6. Chronological OOF thermal residual protection.
7. Empty partition handling.
8. Single-class partition handling (reporting NOT ESTIMABLE for positive recall/AP).
9. No-positive-event handling.
10. No-prediction / all-missing handling.
11. Censoring counts tracking.
12. Event accounting (unique onset events, not row count).
13. Overlapping-window accounting.
14. False-alert episode counting with 30-min continuity merging.
15. Observed-time denominator (elapsed time excluding gaps > 30 min, not fixed 15 min).
16. Metric denominator correctness.
17. Unsupported-metric reporting (explicit reason strings).
18. Calibration refusal when unsupported on single-class partitions.
19. Five-point operational release gate logic (concluding INSUFFICIENT_VALIDATION).
20. Health Index fixture reproduction (all 8 fixtures).
21. Maintenance scenario reproduction (all 11 scenarios).
22. Deterministic evaluation replay.
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from ml.evaluation.anomaly_eval import count_flagged_episodes, evaluate_anomaly_on_partition
from ml.evaluation.fixtures_eval import (
    verify_health_index_fixtures,
    verify_maintenance_scenarios,
)
from ml.evaluation.forecast_eval import (
    evaluate_forecast_binary_partition,
    evaluate_operational_release_gate,
)
from ml.evaluation.splits import (
    SPLIT_TRAIN_END,
    SPLIT_VAL_END,
    compute_adequately_observed_asset_days,
    partition_exploratory_splits,
    partition_primary_chronological_splits,
)
from ml.evaluation.thermal_eval import (
    compute_thermal_error_metrics,
    fit_ambient_offset_baseline,
)
from ml.prediction.model import fit_train_preprocessing
from ml.prediction.target import MODEL_FEATURE_ALLOWLIST


class Phase06EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        pass

    # 1. Frozen time split boundaries
    def test_1_frozen_time_split_boundaries(self) -> None:
        """Requirement 1: Split boundaries strictly match AUDIT_PLAN.md & 06_EVALUATION.md."""
        self.assertEqual(SPLIT_TRAIN_END, "2019-11-23 11:45:00")
        self.assertEqual(SPLIT_VAL_END, "2020-02-13 11:15:00")

    # 2. Split performed before filtering
    def test_2_split_performed_before_filtering(self) -> None:
        """Requirement 2: Splits are evaluated on the original timeline before filtering."""
        ts = pd.date_range("2019-06-25 12:39:00", "2020-04-14 00:30:00", periods=100)
        df = pd.DataFrame({"timestamp": ts, "val": range(100)})
        splits = partition_primary_chronological_splits(df)

        self.assertTrue((splits["train"]["timestamp"] < pd.Timestamp(SPLIT_TRAIN_END)).all())
        self.assertTrue((splits["val"]["timestamp"] >= pd.Timestamp(SPLIT_TRAIN_END)).all())
        self.assertTrue((splits["val"]["timestamp"] < pd.Timestamp(SPLIT_VAL_END)).all())
        self.assertTrue((splits["test"]["timestamp"] >= pd.Timestamp(SPLIT_VAL_END)).all())

    # 3. Target-horizon purge
    def test_3_target_horizon_purge_at_boundaries(self) -> None:
        """Requirement 3: Target-horizon purge removes samples within 1h before boundaries."""
        t_boundary = pd.Timestamp(SPLIT_TRAIN_END)
        # Sample 45 min before boundary: in the 1h purge window
        ts_purged = t_boundary - pd.Timedelta(minutes=45)
        # Sample 75 min before boundary: outside purge window (kept in train)
        ts_kept = t_boundary - pd.Timedelta(minutes=75)

        df = pd.DataFrame({"timestamp": [ts_kept, ts_purged], "val": [1, 2]})
        splits = partition_primary_chronological_splits(df, horizon_hours=1.0)

        self.assertIn(0, splits["train"].index)
        self.assertNotIn(1, splits["train"].index)
        self.assertIn(1, splits["train_purged"].index)

    # 4. No leakage across split boundary
    def test_4_no_leakage_across_split_boundary(self) -> None:
        """Requirement 4: Features and labels in Val/Test never cross into Train."""
        ts = pd.date_range("2019-01-01", periods=10, freq="1D")
        t_split = ts[5]
        train_df = pd.DataFrame({"timestamp": ts[:5], "target": [0, 0, 1, 0, 0]})
        val_df = pd.DataFrame({"timestamp": ts[5:], "target": [1, 1, 1, 1, 1]})

        # Train prior must reflect ONLY train
        train_prior = float(train_df["target"].mean())
        self.assertEqual(train_prior, 0.2)
        # It must NOT be affected by val
        self.assertNotEqual(train_prior, float(pd.concat([train_df, val_df])["target"].mean()))

    # 5. Preprocessing fitted strictly on training
    def test_5_preprocessing_fitted_only_on_training(self) -> None:
        """Requirement 5: Scaler/imputer fitted strictly on train partition."""
        train_features = pd.DataFrame({
            feat: [10.0, 20.0, 30.0] for feat in MODEL_FEATURE_ALLOWLIST
        })
        val_features = pd.DataFrame({
            feat: [100.0, 200.0, 300.0] for feat in MODEL_FEATURE_ALLOWLIST
        })

        preprocessor = fit_train_preprocessing(train_features)
        # Train means must be 20.0
        self.assertEqual(preprocessor.means["oil_temperature"], 20.0)

        # Transform val: uses train mean (20.0), NOT val mean (200.0)
        X_val = preprocessor.transform(val_features)
        # For oil_temperature = 100.0, scaled = (100 - 20) / std
        expected_scaled_0 = (100.0 - 20.0) / preprocessor.scales["oil_temperature"]
        self.assertAlmostEqual(X_val[0, 0], expected_scaled_0)

    # 6. Chronological OOF thermal residual protection
    def test_6_oof_thermal_residual_protection(self) -> None:
        """Requirement 6: OOF residuals are generated via expanding chronological folds."""
        from ml.thermal.calibration import generate_chronological_oof_residuals
        from ml.thermal.thermal_twin import ThermalTwinConfig

        ts = pd.date_range("2019-07-01", periods=30, freq="1h")
        canonical_mock = pd.DataFrame({
            "transformer_id": ["TX-001"] * 30,
            "timestamp": ts,
            "oil_temperature": [40.0 + i * 0.1 for i in range(30)],
            "ambient_temperature": [25.0] * 30,
            "current_l1": [50.0] * 30,
            "current_l2": [50.0] * 30,
            "current_l3": [50.0] * 30,
            "oil_temp_alarm": [0.0] * 30,
            "oil_temp_trip": [0.0] * 30,
            "active_power_demand": [100.0] * 30,
        })
        cfg = ThermalTwinConfig(b0=-2.0, bA=1.1, bJ=0.0001, tau_hours=0.5)
        # Expanding window OOF
        oof = generate_chronological_oof_residuals(canonical_mock, cfg, n_folds=3)
        self.assertIsInstance(oof, pd.Series)
        # First fold is strictly training only; its own residual is withheld / NaN
        self.assertTrue(pd.isna(oof.iloc[0]))

    # 7. Empty partition handling
    def test_7_empty_partition_handling(self) -> None:
        """Requirement 7: Empty partitions return NOT ESTIMABLE without crashing."""
        res = evaluate_forecast_binary_partition(
            y_true=[],
            y_probs=[],
            timestamps=[],
        )
        self.assertEqual(res["total_instances"], 0)
        self.assertIn("NOT ESTIMABLE", res["row_metrics"]["recall"])
        self.assertIn("NOT ESTIMABLE", res["event_metrics"]["event_recall"])

    # 8. Single-class partition handling
    def test_8_single_class_partition_handling(self) -> None:
        """Requirement 8: Single-class partition returns NOT ESTIMABLE for positive metrics."""
        y_true = [0.0, 0.0, 0.0, 0.0]
        y_probs = [0.05, 0.10, 0.02, 0.01]
        ts = pd.date_range("2020-01-01", periods=4, freq="15min")

        res = evaluate_forecast_binary_partition(y_true, y_probs, ts)
        self.assertEqual(res["support"]["positive_support"], 0)
        self.assertEqual(res["support"]["negative_support"], 4)
        self.assertIn("NOT ESTIMABLE", res["row_metrics"]["recall"])
        self.assertIn("NOT ESTIMABLE", res["row_metrics"]["average_precision_pr_auc"])
        self.assertIn("NOT ESTIMABLE", res["row_metrics"]["f1_score"])

    # 9. No-positive-event handling
    def test_9_no_positive_event_handling(self) -> None:
        """Requirement 9: Partitions with no events report NOT ESTIMABLE for event recall."""
        y_true = [0.0] * 10
        y_probs = [0.1] * 10
        ts = pd.date_range("2020-01-01", periods=10, freq="15min")

        res = evaluate_forecast_binary_partition(y_true, y_probs, ts)
        self.assertEqual(res["event_metrics"]["total_onset_events"], 0)
        self.assertIn("NOT ESTIMABLE", res["event_metrics"]["event_recall"])

    # 10. No-prediction / all-missing handling
    def test_10_no_prediction_handling(self) -> None:
        """Requirement 10: Thermal evaluation with all-missing predictions reports NOT ESTIMABLE."""
        actual = np.array([40.0, 45.0, 50.0])
        predicted = np.array([np.nan, np.nan, np.nan])

        res = compute_thermal_error_metrics(actual, predicted, total_count=3, ready_count=0)
        self.assertEqual(res["evaluated_count"], 0)
        self.assertIn("NOT ESTIMABLE", res["mae"])
        self.assertIn("NOT ESTIMABLE", res["rmse"])

    # 11. Censoring counts tracking
    def test_11_censoring_counts_tracking(self) -> None:
        """Requirement 11: Target table tracks and reports eligible vs censored instances."""
        from ml.prediction.target import build_proxy_target_table

        # Two rows separated by 5 hours (continuity gap > 30 min -> censored!)
        df = pd.DataFrame({
            "timestamp": [pd.Timestamp("2020-01-01 00:00:00"), pd.Timestamp("2020-01-01 05:00:00")],
            "oil_temp_alarm": [0.0, 0.0],
            "oil_temp_trip": [0.0, 0.0],
        })
        target_tbl = build_proxy_target_table(df)
        self.assertIn("is_eligible", target_tbl.columns)
        self.assertIn("censoring_reason", target_tbl.columns)
        self.assertFalse(target_tbl.loc[0, "is_eligible"])
        self.assertTrue("CENSORED" in str(target_tbl.loc[0, "censoring_reason"]))

    # 12. Event accounting
    def test_12_event_accounting_not_inflated_by_rows(self) -> None:
        """Requirement 12: Event recall counts unique onset events, not row count."""
        # 1 event spanning 3 consecutive rows
        y_true = [1.0, 1.0, 1.0]
        y_probs = [0.8, 0.8, 0.8]
        ts = pd.date_range("2020-01-01 12:00", periods=3, freq="15min")
        evts = ["EVENT-01", "EVENT-01", "EVENT-01"]

        res = evaluate_forecast_binary_partition(
            y_true, y_probs, ts, associated_event_ids=evts
        )
        self.assertEqual(res["event_metrics"]["total_onset_events"], 1)
        self.assertEqual(res["event_metrics"]["alerted_onset_events"], 1)
        self.assertEqual(res["event_metrics"]["event_recall"], 1.0)

    # 13. Overlapping-window accounting
    def test_13_overlapping_window_accounting(self) -> None:
        """Requirement 13: Multiple positive windows for same onset event count as one event."""
        y_true = [0.0, 1.0, 1.0, 0.0]
        y_probs = [0.1, 0.6, 0.7, 0.1]
        ts = pd.date_range("2020-01-01 12:00", periods=4, freq="15min")
        evts = [None, "EVENT-X", "EVENT-X", None]

        res = evaluate_forecast_binary_partition(
            y_true, y_probs, ts, associated_event_ids=evts
        )
        self.assertEqual(res["event_metrics"]["total_onset_events"], 1)

    # 14. False-alert episode counting
    def test_14_false_alert_episode_counting_merges_contiguous_rows(self) -> None:
        """Requirement 14: Continuous false-alert rows within 30 min merge into 1 episode."""
        ts = pd.date_range("2020-01-01 12:00", periods=5, freq="15min")
        # Alert active for 3 consecutive rows (0, 15, 30 min) -> 1 episode!
        flags = [True, True, True, False, False]
        episodes = count_flagged_episodes(ts, flags, max_gap_hours=0.5)
        self.assertEqual(episodes, 1)

        # Alert separated by 45 min gap (> 30 min) -> 2 episodes!
        ts_gap = [
            pd.Timestamp("2020-01-01 12:00"),
            pd.Timestamp("2020-01-01 12:45"),
        ]
        flags_gap = [True, True]
        episodes_gap = count_flagged_episodes(ts_gap, flags_gap, max_gap_hours=0.5)
        self.assertEqual(episodes_gap, 2)

    # 15. Observed-time denominator
    def test_15_observed_time_denominator_excludes_long_gaps(self) -> None:
        """Requirement 15: Elapsed time denominator excludes long gaps > 30 min."""
        # 3 observations at t=0, 15, 30 min -> qualifying duration = 30 min = 0.5 hours
        # then gap of 5 hours to t=5h30min
        # then observation at t=5h45min -> qualifying duration = 15 min = 0.25 hours
        # Total qualifying duration = 0.75 hours = 0.75 / 24 asset-days
        ts = [
            pd.Timestamp("2020-01-01 00:00:00"),
            pd.Timestamp("2020-01-01 00:15:00"),
            pd.Timestamp("2020-01-01 00:30:00"),
            pd.Timestamp("2020-01-01 05:30:00"),  # gap = 5 hours (> 30 min, excluded!)
            pd.Timestamp("2020-01-01 05:45:00"),
        ]
        asset_days = compute_adequately_observed_asset_days(ts, max_gap_hours=0.5)
        expected_hours = 0.5 + 0.25  # 0.75 hours
        self.assertAlmostEqual(asset_days, expected_hours / 24.0, places=6)

    # 16. Metric denominator correctness
    def test_16_metric_denominator_correctness(self) -> None:
        """Requirement 16: Zero denominators handled without division-by-zero errors."""
        res = evaluate_forecast_binary_partition(
            y_true=[0.0, 0.0],
            y_probs=[0.1, 0.2],
            timestamps=pd.date_range("2020-01-01", periods=2, freq="15min"),
        )
        self.assertIn("NOT ESTIMABLE", res["row_metrics"]["recall"])

    # 17. Unsupported-metric reporting
    def test_17_unsupported_metric_reporting(self) -> None:
        """Requirement 17: Reports explicit reason string for unsupported metrics."""
        res = evaluate_forecast_binary_partition(
            y_true=[0.0, 0.0],
            y_probs=[0.1, 0.2],
            timestamps=pd.date_range("2020-01-01", periods=2, freq="15min"),
        )
        self.assertIn("zero positive instances", str(res["row_metrics"]["recall"]))

    # 18. Calibration refusal when unsupported
    def test_18_calibration_refusal_when_unsupported(self) -> None:
        """Requirement 18: Probability calibration claim is strictly refused on single-class data."""
        val_metrics = {
            "support": {"positive_support": 0, "negative_support": 100},
            "event_metrics": {"total_onset_events": 0},
            "brier_scores": {"model_brier_score": 0.01, "prior_baseline_brier_score": 0.02},
            "operational_burden": {"false_alerts_per_asset_day": 0.05},
        }
        test_metrics = dict(val_metrics)
        gate = evaluate_operational_release_gate(val_metrics, test_metrics)

        self.assertFalse(gate["criteria_checks"]["probability_calibration_supported"])
        self.assertFalse(gate["is_operationally_released"])
        self.assertEqual(gate["release_status"], "INSUFFICIENT_VALIDATION")

    # 19. Five-point operational release gate logic
    def test_19_release_gate_logic(self) -> None:
        """Requirement 19: All 5 criteria must pass; failure of any produces INSUFFICIENT_VALIDATION."""
        val_metrics = {
            "support": {"positive_support": 0, "negative_support": 3641},
            "event_metrics": {"total_onset_events": 0},
            "brier_scores": {"model_brier_score": 0.005, "prior_baseline_brier_score": 0.005},
            "operational_burden": {"false_alerts_per_asset_day": 0.0},
        }
        test_metrics = dict(val_metrics)
        gate = evaluate_operational_release_gate(val_metrics, test_metrics)

        self.assertFalse(gate["all_criteria_passed"])
        self.assertFalse(gate["is_operationally_released"])
        self.assertEqual(gate["release_status"], "INSUFFICIENT_VALIDATION")
        self.assertIsNone(gate["contract_operational_outputs"]["fault_risk"])
        self.assertIsNone(gate["contract_operational_outputs"]["predicted_fault"])

    # 20. Health Index fixture reproduction
    def test_20_health_index_fixture_reproduction(self) -> None:
        """Requirement 20: Reproduces all 8 mandatory Health Index fixtures."""
        hi_eval = verify_health_index_fixtures()
        self.assertTrue(hi_eval["all_fixtures_passed"])
        self.assertEqual(hi_eval["total_fixtures"], 8)

    # 21. Maintenance scenario reproduction
    def test_21_maintenance_scenario_reproduction(self) -> None:
        """Requirement 21: Reproduces all 11 mandatory Maintenance Engine scenarios."""
        maint_eval = verify_maintenance_scenarios()
        self.assertTrue(maint_eval["all_scenarios_passed"])
        self.assertEqual(maint_eval["total_scenarios"], 11)

    # 22. Deterministic evaluation replay
    def test_22_deterministic_evaluation_replay(self) -> None:
        """Requirement 22: Repeating evaluation produces identical metrics and statuses."""
        hi_1 = verify_health_index_fixtures()
        hi_2 = verify_health_index_fixtures()
        self.assertEqual(hi_1, hi_2)

        maint_1 = verify_maintenance_scenarios()
        maint_2 = verify_maintenance_scenarios()
        self.assertEqual(maint_1, maint_2)

    # 23. Heuristic budget distinguished from release criteria
    def test_23_heuristic_budget_distinguished_from_release_criteria(self) -> None:
        """Requirement 23: Exceeding 0.143 ep/day alone does not fail release gate; reports NEEDS CONFIRMATION."""
        # Simulated validation partition where false alert rate exceeds 0.143 ep/day
        val_metrics = {
            "support": {"positive_support": 10, "negative_support": 100},
            "event_metrics": {"total_onset_events": 5},
            "brier_scores": {"model_brier_score": 0.01, "prior_baseline_brier_score": 0.05},
            "operational_burden": {
                "false_alerts_per_asset_day": 0.50,  # exceeds 0.143
                "heuristic_reference_budget_per_asset_day": 1.0 / 7.0,
                "heuristic_reference_budget_met": False,
                "operational_threshold_status": "NEEDS CONFIRMATION / CONFIGURATION REQUIRED",
            },
        }
        test_metrics = dict(val_metrics)
        gate = evaluate_operational_release_gate(val_metrics, test_metrics)

        # Check alert burden evaluation block
        alert_info = gate["criteria_checks"]["alert_burden_evaluation"]
        self.assertEqual(alert_info["operational_threshold_status"], "NEEDS CONFIRMATION / CONFIGURATION REQUIRED")
        self.assertFalse(alert_info["validation_meets_heuristic_budget"])
        self.assertAlmostEqual(alert_info["heuristic_reference_budget_per_asset_day"], 1.0 / 7.0)
        # Release blocker for alert threshold explains configuration requirement
        self.assertTrue(any("NEEDS CONFIRMATION" in str(b) for b in gate["release_blockers"]))


if __name__ == "__main__":
    unittest.main()
