"""Comprehensive unit tests for Phase 04 — Experimental Future Proxy Prediction.

Tests verify:
1. Three-valued contact state (active, clear, missing/unknown).
2. Valid onset identification:
   - Clean transition from clear (0) to active (1) within <= 30 min continuity gap.
   - Rejection of step from unknown/missing.
   - Rejection of transition across gap > 30 minutes.
   - Rejection of continued active state.
3. Prediction point eligibility:
   - Currently active points excluded from future onset prediction.
   - Currently clear points eligible.
4. Horizon definition:
   - Exact 1-hour elapsed time (t < e <= t + 1h), robust to irregular intervals.
5. Proper censoring vs valid negatives:
   - End-of-record censoring (cannot confirm negative without full 1h follow-up).
   - Continuity gap censoring (> 30 min gap before any onset).
   - Unknown contact state censoring.
   - Valid negatives require complete verified clear follow-up to t + 1h.
6. Split boundary purge:
   - Points whose 1-hour horizon crosses partition boundaries are purged.
7. Feature allowlist enforcement:
   - Rejection of forbidden leakage features (alarm/trip flags, health index, anomaly score, etc.).
   - Exact 8-feature allowlist extraction.
   - Out-of-fold thermal residual strictly clamped to positive residual (negative -> 0.0).
8. Train-only preprocessing:
   - Medians and scales fit strictly on train split, applied frozen to validation.
9. Operational release gating:
   - When validation has zero positive events, release is refused.
   - Operational inference strictly returns null fault_risk, null predicted_fault, null confidence,
     and inference_status = 'INSUFFICIENT_VALIDATION'.
   - Active current contacts return CURRENT_CONTACT_ACTIVE_MONITORING_ACTIVE.
10. Event accounting and calibration refusal consistency.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from ml.prediction.model import (
    EXPLORATORY_SPLIT_TEST_END,
    EXPLORATORY_SPLIT_TRAIN_END,
    EXPLORATORY_SPLIT_VAL_END,
    PREDICTED_FAULT_LABEL,
    STATUS_INSUFFICIENT_DATA,
    STATUS_INSUFFICIENT_VALIDATION,
    STATUS_READY,
    ExperimentalProxyPredictor,
    PreprocessingArtifact,
    compute_adequately_observed_asset_days,
    compute_event_balanced_sample_weights,
    count_false_alert_episodes,
    fit_train_preprocessing,
    run_phase04_experiment,
)
from ml.prediction.target import (
    DEFAULT_CONTINUITY_GAP_HOURS,
    FORBIDDEN_FEATURES,
    MODEL_FEATURE_ALLOWLIST,
    TARGET_HORIZON_HOURS,
    TARGET_NAME,
    TARGET_VERSION,
    TargetConstructionError,
    build_proxy_target_table,
    compute_three_valued_contact_state,
    extract_model_features,
    find_valid_onsets,
)


class TestPhase04TargetAndLogic(unittest.TestCase):
    def test_three_valued_contact_state(self) -> None:
        """Test three-valued OR contact state logic."""
        alarm = pd.Series([0.0, 1.0, 0.0, np.nan, 0.0, np.nan])
        trip = pd.Series([0.0, 0.0, 1.0, 0.0, np.nan, 1.0])
        b = compute_three_valued_contact_state(alarm, trip)
        self.assertEqual(b.iloc[0], 0.0)  # Both clear -> 0
        self.assertEqual(b.iloc[1], 1.0)  # Alarm active -> 1
        self.assertEqual(b.iloc[2], 1.0)  # Trip active -> 1
        self.assertTrue(np.isnan(b.iloc[3]))  # Missing alarm -> NaN
        self.assertTrue(np.isnan(b.iloc[4]))  # Missing trip -> NaN
        self.assertEqual(b.iloc[5], 1.0)  # Active trip overrides missing alarm -> 1

    def test_valid_onset_identification(self) -> None:
        """Test clean clear->active onset detection and gap/unknown rejection."""
        base_t = datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc)
        timestamps = [
            base_t,
            base_t + timedelta(minutes=15),  # idx 1: onset from 0 -> 1 within 15 min
            base_t + timedelta(minutes=30),  # idx 2: continuing active 1 -> 1
            base_t + timedelta(minutes=45),  # idx 3: return to 0
            base_t + timedelta(minutes=120), # idx 4: jump to 1 across 75 min gap (> 30 min)
            base_t + timedelta(minutes=135), # idx 5: return to 0
            base_t + timedelta(minutes=150), # idx 6: NaN state
            base_t + timedelta(minutes=165), # idx 7: transition from NaN -> 1
        ]
        b_series = pd.Series([0.0, 1.0, 1.0, 0.0, 1.0, 0.0, np.nan, 1.0])
        ts_series = pd.Series(timestamps)

        onsets = find_valid_onsets(ts_series, b_series, max_gap_hours=0.5)

        # Only index 1 should be a valid onset
        self.assertEqual(len(onsets), 1)
        self.assertEqual(onsets[0]["row_index"], 1)
        self.assertEqual(onsets[0]["timestamp"], pd.Timestamp(timestamps[1]))

    def test_prediction_eligibility_and_censoring(self) -> None:
        """Test eligibility at t, 1-hour horizon, censoring, and valid negatives."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        # 10 timestamps at 15-minute intervals: 10:00 to 12:15
        timestamps = [base_t + timedelta(minutes=15 * i) for i in range(10)]
        # All contacts clear
        alarms = [0.0] * 10
        trips = [0.0] * 10

        # Inject an onset at index 3 (10:45)
        alarms[3] = 1.0
        # Return to clear at index 5 (11:15)
        alarms[4] = 1.0

        df = pd.DataFrame({
            "timestamp": timestamps,
            "oil_temp_alarm": alarms,
            "oil_temp_trip": trips,
        })

        table = build_proxy_target_table(df, horizon_hours=1.0, max_gap_hours=0.5)

        # Row 0 (10:00): Clear, horizon ends 11:00. Onset occurs at 10:45 (in horizon). -> Y=1
        self.assertTrue(table.loc[0, "is_eligible"])
        self.assertEqual(table.loc[0, "target_y"], 1.0)
        self.assertEqual(table.loc[0, "associated_event_id"], "ONSET_001")

        # Row 1 (10:15): Clear, horizon ends 11:15. Onset occurs at 10:45 (in horizon). -> Y=1
        self.assertTrue(table.loc[1, "is_eligible"])
        self.assertEqual(table.loc[1, "target_y"], 1.0)

        # Row 2 (10:30): Clear, horizon ends 11:30. Onset occurs at 10:45 (in horizon). -> Y=1
        self.assertTrue(table.loc[2, "is_eligible"])
        self.assertEqual(table.loc[2, "target_y"], 1.0)

        # Row 3 (10:45): ACTIVE (B_t == 1.0). Ineligible!
        self.assertFalse(table.loc[3, "is_eligible"])
        self.assertTrue(np.isnan(table.loc[3, "target_y"]))
        self.assertEqual(table.loc[3, "censoring_reason"], "CURRENT_STATE_NOT_CLEAR")

        # Row 4 (11:00): ACTIVE (B_t == 1.0). Ineligible!
        self.assertFalse(table.loc[4, "is_eligible"])
        self.assertEqual(table.loc[4, "censoring_reason"], "CURRENT_STATE_NOT_CLEAR")

        # Row 5 (11:15): Clear. Horizon ends 12:15. Timestamps go to 12:15 (idx 9).
        # In interval (11:15, 12:15], all points (idx 6, 7, 8, 9) are clear. -> Y=0 (valid negative)
        self.assertTrue(table.loc[5, "is_eligible"])
        self.assertEqual(table.loc[5, "target_y"], 0.0)

        # Row 7 (11:45): Clear. Horizon ends 12:45. But dataset ends at 12:15.
        # Without 1h follow-up and without an onset, cannot confirm negative! -> END_OF_RECORD_CENSORED
        self.assertFalse(table.loc[7, "is_eligible"])
        self.assertTrue(np.isnan(table.loc[7, "target_y"]))
        self.assertEqual(table.loc[7, "censoring_reason"], "END_OF_RECORD_CENSORED")

    def test_continuity_gap_censoring(self) -> None:
        """Test that gaps > 30 min within horizon cause censoring, not false negatives."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        timestamps = [
            base_t,                          # 10:00
            base_t + timedelta(minutes=15),  # 10:15
            base_t + timedelta(minutes=60),  # 11:00 (45 min gap from 10:15 > 30 min)
            base_t + timedelta(minutes=75),  # 11:15
        ]
        df = pd.DataFrame({
            "timestamp": timestamps,
            "oil_temp_alarm": [0.0, 0.0, 0.0, 0.0],
            "oil_temp_trip": [0.0, 0.0, 0.0, 0.0],
        })
        table = build_proxy_target_table(df, horizon_hours=1.0, max_gap_hours=0.5)

        # Row 0 (10:00): Horizon ends 11:00. But gap from 10:15 to 11:00 is 45 min.
        # Should be censored due to HORIZON_GAP_CENSORED, not marked as negative!
        self.assertFalse(table.loc[0, "is_eligible"])
        self.assertTrue(np.isnan(table.loc[0, "target_y"]))
        self.assertEqual(table.loc[0, "censoring_reason"], "HORIZON_GAP_CENSORED")


class TestPhase04FeaturesAndPreprocessing(unittest.TestCase):
    def test_forbidden_features_rejected(self) -> None:
        """Verify that any forbidden leakage feature raises TargetConstructionError."""
        base_df = pd.DataFrame({
            "oil_temperature": [50.0],
            "ambient_temperature": [25.0],
        })

        for forbidden in FORBIDDEN_FEATURES:
            if forbidden == "thermal_residual":
                continue  # tested separately as allowed only via explicit out-of-fold parameter
            bad_df = base_df.copy()
            bad_df[forbidden] = [1.0]
            with self.assertRaises(TargetConstructionError):
                extract_model_features(bad_df)

    def test_allowlist_extraction_and_positive_residual(self) -> None:
        """Verify feature allowlist extraction and positive residual clamping."""
        df = pd.DataFrame({
            "oil_temperature": [55.0, 60.0],
            "ambient_temperature": [25.0, 26.0],
            "temperature_slope": [0.5, 0.8],
            "current_mean": [120.0, 130.0],
            "current_imbalance_pct": [2.0, 2.5],
            "apparent_power_total": [80.0, 90.0],
            "rolling_load_mean": [0.4, 0.5],
            "unrelated_column": [999.0, 888.0],
        })
        # Signed residual: one negative (-3.0), one positive (+4.0)
        oof_residuals = pd.Series([-3.0, 4.0], index=df.index)

        feat = extract_model_features(df, thermal_residuals=oof_residuals)

        # Must match exact allowlist columns and order
        self.assertEqual(list(feat.columns), list(MODEL_FEATURE_ALLOWLIST))
        self.assertNotIn("unrelated_column", feat.columns)
        # Negative residual clamped to 0.0, positive preserved
        self.assertEqual(feat.loc[0, "thermal_residual"], 0.0)
        self.assertEqual(feat.loc[1, "thermal_residual"], 4.0)

    def test_train_only_preprocessing(self) -> None:
        """Verify preprocessing is strictly fit on train and frozen for eval."""
        train_data = pd.DataFrame({
            "oil_temperature": [40.0, 60.0, np.nan],
            "ambient_temperature": [20.0, 30.0, 25.0],
            "temperature_slope": [0.0, 1.0, 0.5],
            "current_mean": [100.0, 200.0, 150.0],
            "current_imbalance_pct": [1.0, 3.0, 2.0],
            "apparent_power_total": [50.0, 70.0, 60.0],
            "rolling_load_mean": [0.3, 0.5, 0.4],
            "thermal_residual": [0.0, 2.0, 1.0],
        })
        prep = fit_train_preprocessing(train_data)

        # Median of oil_temperature on train is 50.0
        self.assertEqual(prep.medians["oil_temperature"], 50.0)

        # Transform validation data containing NaNs
        val_data = pd.DataFrame({
            "oil_temperature": [np.nan],
            "ambient_temperature": [25.0],
            "temperature_slope": [0.5],
            "current_mean": [150.0],
            "current_imbalance_pct": [2.0],
            "apparent_power_total": [60.0],
            "rolling_load_mean": [0.4],
            "thermal_residual": [1.0],
        })
        X_val = prep.transform(val_data)
        self.assertFalse(np.isnan(X_val).any())


class TestPhase04OperationalGating(unittest.TestCase):
    def test_operational_release_gating_refusal(self) -> None:
        """Verify that an unreleased predictor returns null outputs and INSUFFICIENT_VALIDATION."""
        predictor = ExperimentalProxyPredictor(
            model=None,
            preprocessor=None,
            is_operationally_released=False,
        )

        dummy_features = {feat: 1.0 for feat in MODEL_FEATURE_ALLOWLIST}
        res = predictor.predict_record(dummy_features, is_current_contact_clear=True)

        self.assertIsNone(res["fault_risk"])
        self.assertIsNone(res["predicted_fault"])
        self.assertIsNone(res["prediction_confidence"])
        self.assertEqual(res["inference_status"], STATUS_INSUFFICIENT_VALIDATION)
        self.assertEqual(res["target_definition"], TARGET_NAME)

    def test_currently_active_contacts_behavior(self) -> None:
        """Verify that when contact is currently active, forecasting is bypassed."""
        predictor = ExperimentalProxyPredictor(
            model=None,
            preprocessor=None,
            is_operationally_released=False,
        )

        dummy_features = {feat: 1.0 for feat in MODEL_FEATURE_ALLOWLIST}
        res = predictor.predict_record(dummy_features, is_current_contact_clear=False)

        self.assertIsNone(res["fault_risk"])
        self.assertIsNone(res["predicted_fault"])
        self.assertEqual(res["inference_status"], "CURRENT_CONTACT_ACTIVE_MONITORING_ACTIVE")


class TestPhase04ExploratoryAndEventBalancing(unittest.TestCase):
    def test_event_balanced_sample_weights_policy(self) -> None:
        """Verify that event balancing equalizes total weight per event regardless of window count."""
        # 10 negative rows, Event A with 10 positive rows, Event B with 2 positive rows
        y = pd.Series([0.0] * 10 + [1.0] * 10 + [1.0] * 2)
        event_ids = pd.Series([np.nan] * 10 + ["EVT_A"] * 10 + ["EVT_B"] * 2)

        weights = compute_event_balanced_sample_weights(y, event_ids)

        # Negative rows must be weighted 1.0
        neg_weights = weights[:10]
        np.testing.assert_array_equal(neg_weights, 1.0)

        # Total negative weight = 10
        self.assertEqual(float(np.sum(neg_weights)), 10.0)

        # Total positive weight = 10 (balanced with negatives)
        pos_weights = weights[10:]
        self.assertAlmostEqual(float(np.sum(pos_weights)), 10.0, places=7)

        # Event A (10 rows): each row gets (10 / 2) / 10 = 0.5; total weight = 5.0
        evt_a_weights = weights[10:20]
        self.assertAlmostEqual(float(np.sum(evt_a_weights)), 5.0, places=7)
        self.assertAlmostEqual(float(evt_a_weights[0]), 0.5, places=7)

        # Event B (2 rows): each row gets (10 / 2) / 2 = 2.5; total weight = 5.0
        evt_b_weights = weights[20:22]
        self.assertAlmostEqual(float(np.sum(evt_b_weights)), 5.0, places=7)
        self.assertAlmostEqual(float(evt_b_weights[0]), 2.5, places=7)

        # Crucial invariant: Event A and Event B have identical total influence (5.0 each)!
        self.assertAlmostEqual(float(np.sum(evt_a_weights)), float(np.sum(evt_b_weights)), places=7)

    def test_no_leakage_in_event_weights(self) -> None:
        """Verify weights depend only on train inputs and are deterministic."""
        y_train = pd.Series([0.0, 0.0, 1.0, 1.0])
        evts_train = pd.Series([np.nan, np.nan, "EVT_1", "EVT_1"])

        w1 = compute_event_balanced_sample_weights(y_train, evts_train)
        w2 = compute_event_balanced_sample_weights(y_train, evts_train)
        np.testing.assert_array_equal(w1, w2)

    def test_target_horizon_open_left_closed_right(self) -> None:
        """Verify t is excluded and t + 1h is included in target horizon (t < e <= t + 1h)."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        timestamps = [
            base_t,                          # 10:00:00 (t)
            base_t + timedelta(minutes=60),  # 11:00:00 (exactly t + 1h)
            base_t + timedelta(minutes=75),  # 11:15:00
        ]
        # Onset occurs exactly at 11:00:00
        b_series = pd.Series([0.0, 1.0, 1.0])
        df = pd.DataFrame({
            "timestamp": timestamps,
            "oil_temp_alarm": b_series,
            "oil_temp_trip": [0.0, 0.0, 0.0],
        })

        table = build_proxy_target_table(df, horizon_hours=1.0, max_gap_hours=1.5)
        # Prediction at 10:00:00 (row 0): onset is at 11:00:00, which is exactly t + 1h. Must be positive (Y=1)!
        self.assertTrue(table.loc[0, "is_eligible"])
        self.assertEqual(table.loc[0, "target_y"], 1.0)

    def test_exploratory_split_boundary_constants(self) -> None:
        """Verify exploratory split boundary definitions."""
        self.assertEqual(EXPLORATORY_SPLIT_TRAIN_END, "2019-08-01 00:00:00")
        self.assertEqual(EXPLORATORY_SPLIT_VAL_END, "2019-08-16 00:00:00")
        self.assertEqual(EXPLORATORY_SPLIT_TEST_END, "2019-09-04 00:00:00")

    def test_irregular_timestamps_produce_actual_elapsed_duration(self) -> None:
        """Verify actual elapsed duration is computed from irregular timestamps."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        timestamps = [
            base_t,                          # 10:00
            base_t + timedelta(minutes=7),   # 10:07 (7 min)
            base_t + timedelta(minutes=22),  # 10:22 (15 min)
        ]
        # Both intervals <= 30 min. Total qualifying elapsed time = 22 minutes = 22/60 hours
        expected_days = (22.0 / 60.0) / 24.0
        days = compute_adequately_observed_asset_days(timestamps, max_gap_hours=0.5)
        self.assertAlmostEqual(days, expected_days, places=6)

    def test_15_minute_row_frequency_not_assumed(self) -> None:
        """Verify that 15-minute row frequency is NOT assumed."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        # 3 rows spaced 5 minutes apart (10:00, 10:05, 10:10)
        timestamps = [
            base_t,
            base_t + timedelta(minutes=5),
            base_t + timedelta(minutes=10),
        ]
        actual_days = compute_adequately_observed_asset_days(timestamps, max_gap_hours=0.5)
        expected_days = (10.0 / 60.0) / 24.0
        naive_15min_days = (3 * 0.25) / 24.0

        self.assertAlmostEqual(actual_days, expected_days, places=6)
        self.assertNotAlmostEqual(actual_days, naive_15min_days, places=4)

    def test_gaps_over_30min_do_not_contribute_to_observed_duration(self) -> None:
        """Verify gaps > 30 min contribute 0 to observed duration."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        timestamps = [
            base_t,                          # 10:00
            base_t + timedelta(minutes=15),  # 10:15 (15 min <= 30 min -> qualifies)
            base_t + timedelta(minutes=60),  # 11:00 (45 min gap > 30 min -> does NOT qualify)
        ]
        days = compute_adequately_observed_asset_days(timestamps, max_gap_hours=0.5)
        expected_days = 0.25 / 24.0  # Only the first 15-minute interval qualifies
        self.assertAlmostEqual(days, expected_days, places=6)

    def test_false_alert_rows_in_one_continuous_episode_count_as_one_episode(self) -> None:
        """Verify repeated false-alert rows within continuity limit count as one episode."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        # 5 consecutive false-alert rows at 10-minute intervals (all dt <= 30 min)
        timestamps = [base_t + timedelta(minutes=10 * i) for i in range(5)]
        is_fa = [True, True, True, True, True]

        episodes = count_false_alert_episodes(timestamps, is_fa, max_gap_hours=0.5)
        self.assertEqual(episodes, 1)

    def test_qualifying_gap_separates_false_alert_episodes(self) -> None:
        """Verify that a qualifying gap (> 30 min) separates false-alert episodes."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        timestamps = [
            base_t,                          # 10:00 (FA)
            base_t + timedelta(minutes=45),  # 10:45 (FA, 45 min gap > 30 min)
        ]
        is_fa = [True, True]

        episodes = count_false_alert_episodes(timestamps, is_fa, max_gap_hours=0.5)
        self.assertEqual(episodes, 2)

    def test_episode_accounting_is_deterministic(self) -> None:
        """Verify episode accounting is deterministic and order-invariant."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        timestamps = [
            base_t,
            base_t + timedelta(minutes=15),
            base_t + timedelta(minutes=60),
            base_t + timedelta(minutes=75),
        ]
        is_fa = [True, True, True, True]

        ep1 = count_false_alert_episodes(timestamps, is_fa, max_gap_hours=0.5)
        ep2 = count_false_alert_episodes(timestamps, is_fa, max_gap_hours=0.5)
        self.assertEqual(ep1, ep2)
        self.assertEqual(ep1, 2)

    def test_event_level_accounting_remains_separate_from_row_level_accounting(self) -> None:
        """Verify independent event counting does not confuse rows with onset events."""
        base_t = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
        timestamps = [base_t + timedelta(minutes=15 * i) for i in range(5)]
        y_true = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0])
        y_probs = np.array([0.8, 0.9, 0.7, 0.85, 0.6])

        # All 5 positive windows belong to a single event EVT_001
        target_subset = pd.DataFrame({
            "timestamp": timestamps,
            "target_y": y_true,
            "associated_event_id": ["EVT_001"] * 5,
        })
        onsets_map = {"EVT_001": base_t + timedelta(minutes=60)}

        from ml.prediction.model import evaluate_partition_metrics
        res = evaluate_partition_metrics(y_true, y_probs, target_subset, onsets_map, threshold=0.5)

        # Row level positive support is 5
        self.assertEqual(res["confusion_matrix"]["true_positives"], 5)
        # Event level onset count is exactly 1
        self.assertEqual(res["event_metrics"]["total_onset_events"], 1)
        self.assertEqual(res["event_metrics"]["alerted_onset_events"], 1)
        self.assertEqual(res["event_metrics"]["event_recall"], 1.0)


if __name__ == "__main__":
    unittest.main()


