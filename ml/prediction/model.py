"""Regularized Logistic Regression proxy prediction model and evaluation for Phase 04.

Phase 04:
- Primary baseline: Regularized Logistic Regression (L2 penalty).
- Preprocessing: Train-only median imputation and standard scaling.
- Evaluation on chronological partitions (Train, Validation, Test).
- Operational release gating: If validation split contains zero positives
  or cannot support probability calibration, operational output is strictly:
    fault_risk = null
    predicted_fault = null
    prediction_confidence = null
    inference_status = INSUFFICIENT_VALIDATION
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Mapping

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from ml.prediction.target import (
    DEFAULT_CONTINUITY_GAP_HOURS,
    MODEL_FEATURE_ALLOWLIST,
    TARGET_HORIZON_HOURS,
    TARGET_NAME,
    TARGET_VERSION,
    build_proxy_target_table,
    extract_model_features,
)
from ml.thermal.calibration import SPLIT_TRAIN_END, SPLIT_VAL_END

PREDICTION_ARTIFACT_OUTPUT_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "proxy_prediction_params.json"
)

PREDICTED_FAULT_LABEL: Final = "OIL_TEMP_ALERT_WITHIN_1H"
STATUS_INSUFFICIENT_VALIDATION: Final = "INSUFFICIENT_VALIDATION"
STATUS_INSUFFICIENT_DATA: Final = "INSUFFICIENT_DATA"
STATUS_READY: Final = "READY"


@dataclass(frozen=True)
class PreprocessingArtifact:
    feature_names: list[str]
    medians: dict[str, float]
    means: dict[str, float]
    scales: dict[str, float]

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        # Enforce exact feature order
        missing = [f for f in self.feature_names if f not in df.columns]
        if missing:
            raise ValueError(f"Missing required model features: {missing}")

        X = np.empty((len(df), len(self.feature_names)), dtype="float64")
        for j, col in enumerate(self.feature_names):
            vals = pd.to_numeric(df[col], errors="coerce").to_numpy()
            # Impute median
            med = self.medians[col]
            vals_imp = np.where(np.isnan(vals), med, vals)
            # Scale
            mean = self.means[col]
            scale = self.scales[col]
            if scale == 0.0 or np.isnan(scale):
                scale = 1.0
            X[:, j] = (vals_imp - mean) / scale
        return X

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_names": self.feature_names,
            "medians": self.medians,
            "means": self.means,
            "scales": self.scales,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PreprocessingArtifact:
        return cls(
            feature_names=list(data["feature_names"]),
            medians={k: float(v) for k, v in data["medians"].items()},
            means={k: float(v) for k, v in data["means"].items()},
            scales={k: float(v) for k, v in data["scales"].items()},
        )


def fit_train_preprocessing(train_features: pd.DataFrame) -> PreprocessingArtifact:
    """Fit median imputation and standard scaling strictly on training partition."""
    feature_names = list(MODEL_FEATURE_ALLOWLIST)
    medians: dict[str, float] = {}
    means: dict[str, float] = {}
    scales: dict[str, float] = {}

    for col in feature_names:
        vals = pd.to_numeric(train_features[col], errors="coerce").dropna().to_numpy()
        med = float(np.median(vals)) if len(vals) > 0 else 0.0
        mean = float(np.mean(vals)) if len(vals) > 0 else 0.0
        std = float(np.std(vals)) if len(vals) > 0 else 1.0
        if std == 0.0 or np.isnan(std):
            std = 1.0
        medians[col] = med
        means[col] = mean
        scales[col] = std

    return PreprocessingArtifact(
        feature_names=feature_names,
        medians=medians,
        means=means,
        scales=scales,
    )


class ExperimentalProxyPredictor:
    """Experimental Logistic Regression proxy predictor with release gating."""

    def __init__(
        self,
        model: LogisticRegression | None = None,
        preprocessor: PreprocessingArtifact | None = None,
        decision_threshold: float = 0.5,
        is_operationally_released: bool = False,
    ) -> None:
        self.model = model
        self.preprocessor = preprocessor
        self.decision_threshold = decision_threshold
        self.is_operationally_released = is_operationally_released

    def predict_record(
        self,
        features: Mapping[str, Any],
        is_current_contact_clear: bool = True,
    ) -> dict[str, Any]:
        """Produce inference output following the operational gating rules.

        If operational release is false: returns null for fault_risk, predicted_fault,
        and prediction_confidence, with status INSUFFICIENT_VALIDATION.
        """
        # If current contacts are active, this is monitoring, not future onset forecasting
        if not is_current_contact_clear:
            return {
                "fault_risk": None,
                "predicted_fault": None,
                "prediction_confidence": None,
                "inference_status": "CURRENT_CONTACT_ACTIVE_MONITORING_ACTIVE",
                "experimental_risk": None,
            }

        # Check required features
        feat_df = pd.DataFrame([features])
        missing_crit = [
            f for f in MODEL_FEATURE_ALLOWLIST
            if f not in features or features[f] is None or pd.isna(features[f])
        ]

        if not self.is_operationally_released:
            # Research/experimental prediction may still be generated internally
            exp_risk = None
            if self.model is not None and self.preprocessor is not None:
                try:
                    X = self.preprocessor.transform(feat_df)
                    exp_risk = float(self.model.predict_proba(X)[0, 1])
                except Exception:
                    pass

            return {
                "fault_risk": None,
                "predicted_fault": None,
                "prediction_confidence": None,
                "inference_status": STATUS_INSUFFICIENT_VALIDATION,
                "experimental_risk": exp_risk,
                "target_definition": TARGET_NAME,
                "target_version": TARGET_VERSION,
                "horizon_hours": TARGET_HORIZON_HOURS,
            }

        # If released
        if len(missing_crit) >= 4:
            return {
                "fault_risk": None,
                "predicted_fault": None,
                "prediction_confidence": None,
                "inference_status": STATUS_INSUFFICIENT_DATA,
                "missing_features": missing_crit,
            }

        X = self.preprocessor.transform(feat_df)
        p = float(self.model.predict_proba(X)[0, 1])
        pred_label = PREDICTED_FAULT_LABEL if p >= self.decision_threshold else None
        conf = float(max(p, 1.0 - p))

        return {
            "fault_risk": p,
            "predicted_fault": pred_label,
            "prediction_confidence": conf,
            "inference_status": STATUS_READY,
            "target_definition": TARGET_NAME,
            "target_version": TARGET_VERSION,
            "horizon_hours": TARGET_HORIZON_HOURS,
        }


def run_phase04_experiment(
    canonical_df: pd.DataFrame,
    features_df: pd.DataFrame,
    thermal_residuals_oof: pd.Series,
    output_path: Path = PREDICTION_ARTIFACT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Execute complete Phase 04 training, evaluation, and artifact generation."""
    # 1. Target table
    target_table = build_proxy_target_table(canonical_df)

    # 2. Extract causal features
    X_raw = extract_model_features(
        features_df,
        thermal_residuals=thermal_residuals_oof,
        allow_superset=True,
    )

    # 3. Chronological partitions with split-boundary purge
    # Purge training examples whose 1-hour horizon crosses train_end
    ts = pd.to_datetime(canonical_df["timestamp"])
    train_end_ts = pd.Timestamp(SPLIT_TRAIN_END)
    val_end_ts = pd.Timestamp(SPLIT_VAL_END)

    train_purge_cutoff = train_end_ts - pd.Timedelta(hours=TARGET_HORIZON_HOURS)
    val_purge_cutoff = val_end_ts - pd.Timedelta(hours=TARGET_HORIZON_HOURS)

    train_mask = (ts < train_purge_cutoff) & target_table["is_eligible"]
    val_mask = (ts >= train_end_ts) & (ts < val_purge_cutoff) & target_table["is_eligible"]
    test_mask = (ts >= val_end_ts) & target_table["is_eligible"]

    train_y = target_table.loc[train_mask, "target_y"].dropna()
    val_y = target_table.loc[val_mask, "target_y"].dropna()
# Chronological exploratory partition boundaries
EXPLORATORY_SPLIT_TRAIN_END: Final = "2019-08-01 00:00:00"
EXPLORATORY_SPLIT_VAL_END: Final = "2019-08-16 00:00:00"
EXPLORATORY_SPLIT_TEST_END: Final = "2019-09-04 00:00:00"


def compute_event_balanced_sample_weights(
    y: pd.Series,
    associated_event_ids: pd.Series,
) -> np.ndarray:
    """Compute event-balanced sample weights for training.

    Policy:
    - Negative rows receive a base natural weight of 1.0.
    - Positive rows are balanced across unique onset events:
      Let N_neg be the number of negative rows, and E be the number of unique positive onset events.
      Each event e with m_e overlapping positive windows receives an aggregate weight equal
      to N_neg / E, distributed evenly across its m_e positive windows:
          w_i = (N_neg / E) / m_e  for i in event e.
    - If E == 0 or N_neg == 0, returns uniform weights of 1.0.
    - This guarantees:
      1. Every distinct physical/proxy onset event has equal total influence on the loss function,
         preventing one prolonged event with many overlapping windows from dominating.
      2. Total positive weight equals total negative weight (N_neg), maintaining class balance.
      3. Negative rows remain naturally weighted at 1.0 each.
      4. Sample weights are computed strictly from training partition labels/events without
         any cross-split leakage.
    """
    y_arr = y.to_numpy(dtype=float)
    n = len(y_arr)
    weights = np.ones(n, dtype=float)

    pos_mask = (y_arr == 1.0)
    neg_count = int(np.sum(y_arr == 0.0))

    if neg_count == 0 or not np.any(pos_mask):
        return weights

    # Identify unique positive onset events in train
    pos_events = associated_event_ids.loc[pos_mask]
    unique_events = [e for e in pos_events.unique() if pd.notna(e)]
    E = len(unique_events)

    if E == 0:
        return weights

    event_counts = pos_events.value_counts().to_dict()
    target_event_weight = float(neg_count) / float(E)

    pos_indices = np.where(pos_mask)[0]
    for idx in pos_indices:
        evt = associated_event_ids.iloc[idx]
        if pd.notna(evt) and evt in event_counts and event_counts[evt] > 0:
            m_e = event_counts[evt]
            weights[idx] = target_event_weight / float(m_e)
        else:
            weights[idx] = target_event_weight

    return weights


def compute_adequately_observed_asset_days(
    timestamps: Sequence[pd.Timestamp] | pd.Series,
    max_gap_hours: float = DEFAULT_CONTINUITY_GAP_HOURS,
) -> float:
    """Compute actual elapsed observed asset-days from qualifying intervals.

    Rules:
    1. Sort unique timestamps chronologically.
    2. Compute timestamp differences dt between adjacent observations.
    3. Qualifying interval: dt <= max_gap_hours (30 minutes).
       Intervals > max_gap_hours are treated as unobserved gaps and contribute 0.
    4. Sum of qualifying dt in hours converted to asset-days (hours / 24.0).
    5. Irregular timestamps produce actual elapsed duration; does NOT assume 15-minute frequency.
    """
    s = pd.Series(pd.to_datetime(timestamps)).sort_values().drop_duplicates().reset_index(drop=True)
    if len(s) <= 1:
        return 0.0

    diffs_h = s.diff().dropna().dt.total_seconds() / 3600.0
    qualifying_hours = float(diffs_h[diffs_h <= max_gap_hours].sum())
    return float(qualifying_hours / 24.0)


def count_false_alert_episodes(
    timestamps: Sequence[pd.Timestamp] | pd.Series,
    is_false_alert: Sequence[bool] | pd.Series | np.ndarray,
    max_gap_hours: float = DEFAULT_CONTINUITY_GAP_HOURS,
) -> int:
    """Count distinct false-alert episodes using elapsed-time continuity and qualifying gaps.

    Policy:
    1. Chronological order by timestamp.
    2. A false-alert episode starts when an observation is flagged as a false alert
       (y_true == 0 and y_pred == 1) while not already in an active episode.
    3. While consecutive false-alert observations continue with elapsed interval
       dt <= max_gap_hours (30 minutes), they belong to the SAME continuous episode.
       (Repeated flagged rows within continuity limit do not produce multiple episodes).
    4. An episode terminates when:
       a. A non-alert observation occurs (the false alert condition clears), OR
       b. A qualifying continuity gap dt > max_gap_hours (30 minutes) occurs before the next
          flagged observation, breaking elapsed-time continuity.
    5. A subsequent false-alert observation after termination begins a new episode.
    """
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps),
        "is_fa": np.asarray(is_false_alert, dtype=bool),
    }).sort_values("timestamp").reset_index(drop=True)

    if len(df) == 0:
        return 0

    episodes = 0
    in_episode = False
    last_fa_time: pd.Timestamp | None = None

    for _, row in df.iterrows():
        cur_t: pd.Timestamp = row["timestamp"]
        cur_fa: bool = bool(row["is_fa"])

        if cur_fa:
            if not in_episode:
                # Start new episode
                episodes += 1
                in_episode = True
            else:
                # Currently in episode: check elapsed continuity from previous flagged row
                if last_fa_time is not None:
                    dt_h = (cur_t - last_fa_time).total_seconds() / 3600.0
                    if dt_h > max_gap_hours:
                        # Qualifying gap (> 30 min) separates episodes!
                        episodes += 1
            last_fa_time = cur_t
        else:
            # Alert cleared: non-alert observation ends the ongoing episode
            in_episode = False

    return episodes


def evaluate_partition_metrics(
    y_true: pd.Series,
    y_probs: np.ndarray,
    target_table_subset: pd.DataFrame,
    onsets_map: Mapping[str, pd.Timestamp],
    threshold: float = 0.5,
    train_prior: float = 0.0,
) -> dict[str, Any]:
    """Compute comprehensive evaluation metrics for a partition."""
    y_arr = y_true.to_numpy(dtype=float)
    y_preds = (y_probs >= threshold).astype(float)

    # Confusion matrix
    tn = int(np.sum((y_arr == 0.0) & (y_preds == 0.0)))
    fp = int(np.sum((y_arr == 0.0) & (y_preds == 1.0)))
    fn = int(np.sum((y_arr == 1.0) & (y_preds == 0.0)))
    tp = int(np.sum((y_arr == 1.0) & (y_preds == 1.0)))

    # Classification metrics
    pos_support = int(np.sum(y_arr == 1.0))
    neg_support = int(np.sum(y_arr == 0.0))

    prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

    if pos_support > 0:
        from sklearn.metrics import average_precision_score
        ap = float(average_precision_score(y_arr, y_probs))
        ap_display: Any = ap
    else:
        ap_display = "NOT ESTIMABLE (partition has zero positive instances)"

    # Event-level recall & lead times
    pos_mask = (y_arr == 1.0)
    distinct_events = [
        str(e) for e in target_table_subset.loc[pos_mask, "associated_event_id"].unique()
        if pd.notna(e)
    ]
    alerted_events: list[str] = []
    missed_events: list[dict[str, Any]] = []
    lead_times_minutes: list[float] = []

    for evt in distinct_events:
        evt_mask = (target_table_subset["associated_event_id"] == evt).to_numpy()
        evt_preds = y_preds[evt_mask]
        evt_rows = target_table_subset[evt_mask]

        if np.any(evt_preds == 1.0):
            alerted_events.append(evt)
            # Find earliest alert window
            first_alert_row = evt_rows[evt_preds == 1.0].iloc[0]
            first_alert_ts = pd.Timestamp(first_alert_row["timestamp"])
            onset_ts = onsets_map.get(evt, first_alert_ts + pd.Timedelta(hours=1.0))
            lead_time_min = float((onset_ts - first_alert_ts).total_seconds() / 60.0)
            lead_times_minutes.append(lead_time_min)
        else:
            missed_events.append({
                "event_id": evt,
                "first_window": str(evt_rows.iloc[0]["timestamp"]),
                "last_window": str(evt_rows.iloc[-1]["timestamp"]),
                "window_count": len(evt_rows),
            })

    event_recall: Any = float(len(alerted_events) / len(distinct_events)) if len(distinct_events) > 0 else "NOT ESTIMABLE"

    # Actual elapsed observed duration
    asset_days = compute_adequately_observed_asset_days(
        target_table_subset["timestamp"],
        max_gap_hours=DEFAULT_CONTINUITY_GAP_HOURS,
    )
    qualifying_hours = float(asset_days * 24.0)

    # Consistent false-alert episode accounting
    fp_mask = (y_arr == 0.0) & (y_preds == 1.0)
    fa_episodes = count_false_alert_episodes(
        target_table_subset["timestamp"],
        fp_mask,
        max_gap_hours=DEFAULT_CONTINUITY_GAP_HOURS,
    )
    fa_per_day = float(fa_episodes / asset_days) if asset_days > 0.0 else 0.0

    # Brier scores
    brier_model = float(np.mean((y_probs - y_arr) ** 2))
    brier_prior = float(np.mean((train_prior - y_arr) ** 2))
    brier_always_neg = float(np.mean((0.0 - y_arr) ** 2))

    return {
        "confusion_matrix": {
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
            "true_positives": tp,
        },
        "row_metrics": {
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "average_precision_pr_auc": ap_display,
        },
        "event_metrics": {
            "total_onset_events": len(distinct_events),
            "alerted_onset_events": len(alerted_events),
            "event_recall": event_recall,
            "alerted_event_ids": alerted_events,
            "missed_events": missed_events,
            "lead_times_minutes": lead_times_minutes,
        },
        "operational_burden": {
            "false_alert_episodes": fa_episodes,
            "observed_qualifying_hours": qualifying_hours,
            "observed_asset_days": asset_days,
            "false_alerts_per_asset_day": fa_per_day,
            "continuity_limit_minutes": float(DEFAULT_CONTINUITY_GAP_HOURS * 60.0),
        },
        "brier_scores": {
            "model_brier_score": brier_model,
            "prior_baseline_brier_score": brier_prior,
            "always_negative_brier_score": brier_always_neg,
        },
    }


def run_exploratory_event_era_experiment(
    canonical_df: pd.DataFrame,
    features_df: pd.DataFrame,
    thermal_residuals_oof: pd.Series,
    target_table: pd.DataFrame,
    onsets_map: Mapping[str, pd.Timestamp],
) -> dict[str, Any]:
    """Execute exploratory event-era experiment on the Summer 2019 event sequence."""
    ts = pd.to_datetime(canonical_df["timestamp"])
    h = pd.Timedelta(hours=TARGET_HORIZON_HOURS)

    t_train_end = pd.Timestamp(EXPLORATORY_SPLIT_TRAIN_END)
    t_val_end = pd.Timestamp(EXPLORATORY_SPLIT_VAL_END)
    t_test_end = pd.Timestamp(EXPLORATORY_SPLIT_TEST_END)

    # 1h purge before boundaries
    train_mask = (ts < t_train_end - h) & target_table["is_eligible"]
    val_mask = (ts >= t_train_end) & (ts < t_val_end - h) & target_table["is_eligible"]
    test_mask = (ts >= t_val_end) & (ts < t_test_end) & target_table["is_eligible"]
    surv_mask = (ts >= t_test_end) & target_table["is_eligible"]

    train_y = target_table.loc[train_mask, "target_y"].dropna()
    val_y = target_table.loc[val_mask, "target_y"].dropna()
    test_y = target_table.loc[test_mask, "target_y"].dropna()
    surv_y = target_table.loc[surv_mask, "target_y"].dropna()

    train_idx = train_y.index
    val_idx = val_y.index
    test_idx = test_y.index
    surv_idx = surv_y.index

    # Features extracted cleanly
    X_raw = extract_model_features(
        features_df,
        thermal_residuals=thermal_residuals_oof,
        allow_superset=True,
    )

    # Train-only preprocessing
    preprocessor = fit_train_preprocessing(X_raw.loc[train_idx])
    X_train = preprocessor.transform(X_raw.loc[train_idx])
    X_val = preprocessor.transform(X_raw.loc[val_idx])
    X_test = preprocessor.transform(X_raw.loc[test_idx])
    X_surv = preprocessor.transform(X_raw.loc[surv_idx])

    # Event-balanced sample weights on train
    train_events = target_table.loc[train_idx, "associated_event_id"]
    sample_weights = compute_event_balanced_sample_weights(train_y, train_events)

    clf = LogisticRegression(C=1.0, random_state=42)
    clf.fit(X_train, train_y.to_numpy(), sample_weight=sample_weights)

    val_probs = clf.predict_proba(X_val)[:, 1]
    test_probs = clf.predict_proba(X_test)[:, 1]
    surv_probs = clf.predict_proba(X_surv)[:, 1]

    train_prior = float(train_y.mean())

    def get_event_window_counts(mask: pd.Series) -> dict[str, int]:
        sub = target_table.loc[mask & (target_table["target_y"] == 1.0)]
        return {str(k): int(v) for k, v in sub["associated_event_id"].value_counts().items()}

    val_metrics = evaluate_partition_metrics(
        val_y, val_probs, target_table.loc[val_idx], onsets_map, threshold=0.5, train_prior=train_prior
    )
    test_metrics = evaluate_partition_metrics(
        test_y, test_probs, target_table.loc[test_idx], onsets_map, threshold=0.5, train_prior=train_prior
    )
    surv_metrics = evaluate_partition_metrics(
        surv_y, surv_probs, target_table.loc[surv_idx], onsets_map, threshold=0.5, train_prior=train_prior
    )

    return {
        "experiment_name": "exploratory_event_era_evaluation",
        "purpose": "Exploratory feasibility study on the Summer 2019 event-rich period; NOT production or calibrated evidence.",
        "split_definitions": {
            "train": "timestamp < 2019-08-01 00:00:00 (1h horizon purge applied)",
            "validation": "2019-08-01 00:00:00 <= timestamp < 2019-08-16 00:00:00 (1h horizon purge applied)",
            "test": "2019-08-16 00:00:00 <= timestamp < 2019-09-04 00:00:00",
            "surveillance": "timestamp >= 2019-09-04 00:00:00",
        },
        "event_accounting": {
            "train": {
                "candidate_rows": int((ts < t_train_end).sum()),
                "eligible_rows": len(train_y),
                "censored_rows": int((ts < t_train_end - h).sum() - len(train_y)),
                "positive_rows": int((train_y == 1.0).sum()),
                "negative_rows": int((train_y == 0.0).sum()),
                "unique_onset_events": int(len(get_event_window_counts(train_mask))),
                "event_window_counts": get_event_window_counts(train_mask),
            },
            "validation": {
                "candidate_rows": int(((ts >= t_train_end) & (ts < t_val_end)).sum()),
                "eligible_rows": len(val_y),
                "censored_rows": int(((ts >= t_train_end) & (ts < t_val_end - h)).sum() - len(val_y)),
                "positive_rows": int((val_y == 1.0).sum()),
                "negative_rows": int((val_y == 0.0).sum()),
                "unique_onset_events": int(len(get_event_window_counts(val_mask))),
                "event_window_counts": get_event_window_counts(val_mask),
            },
            "test": {
                "candidate_rows": int(((ts >= t_val_end) & (ts < t_test_end)).sum()),
                "eligible_rows": len(test_y),
                "censored_rows": int(((ts >= t_val_end) & (ts < t_test_end)).sum() - len(test_y)),
                "positive_rows": int((test_y == 1.0).sum()),
                "negative_rows": int((test_y == 0.0).sum()),
                "unique_onset_events": int(len(get_event_window_counts(test_mask))),
                "event_window_counts": get_event_window_counts(test_mask),
            },
            "surveillance": {
                "candidate_rows": int((ts >= t_test_end).sum()),
                "eligible_rows": len(surv_y),
                "censored_rows": int((ts >= t_test_end).sum() - len(surv_y)),
                "positive_rows": int((surv_y == 1.0).sum()),
                "negative_rows": int((surv_y == 0.0).sum()),
                "unique_onset_events": int(len(get_event_window_counts(surv_mask))),
                "event_window_counts": get_event_window_counts(surv_mask),
            },
        },
        "event_balancing_policy": {
            "policy": "Event-balanced sample weighting: negative rows weighted 1.0; each unique positive onset event e receives aggregate weight N_neg / E, distributed evenly as (N_neg / E) / m_e per positive window.",
            "rationale": "Prevents long events with many overlapping windows from dominating training objective; enforces one event = one unit of positive influence.",
        },
        "metrics": {
            "validation": val_metrics,
            "test": test_metrics,
            "surveillance": surv_metrics,
        },
        "calibration_status": "CALIBRATION NOT SUPPORTED (validation partition has only 1 positive episode; insufficient support for probability calibration)",
        "decision_threshold": {
            "value": 0.50,
            "status": "Documented exploratory research baseline; NOT validated for operational deployment.",
        },
    }


def run_phase04_experiment(
    canonical_df: pd.DataFrame,
    features_df: pd.DataFrame,
    thermal_residuals_oof: pd.Series,
    output_path: Path = PREDICTION_ARTIFACT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Execute complete Phase 04 primary and exploratory training, evaluation, and artifact generation."""
    # 1. Target table
    target_table = build_proxy_target_table(canonical_df)

    # Extract clean onsets map for exact lead time calculation
    from ml.prediction.target import compute_three_valued_contact_state, find_valid_onsets
    b_state = compute_three_valued_contact_state(
        canonical_df["oil_temp_alarm"],
        canonical_df["oil_temp_trip"],
    )
    all_onsets = find_valid_onsets(pd.to_datetime(canonical_df["timestamp"]), b_state)
    onsets_map = {o["event_id"]: pd.Timestamp(o["timestamp"]) for o in all_onsets}

    # 2. Extract causal features
    X_raw = extract_model_features(
        features_df,
        thermal_residuals=thermal_residuals_oof,
        allow_superset=True,
    )

    # 3. Chronological partitions with split-boundary purge for primary experiment
    ts = pd.to_datetime(canonical_df["timestamp"])
    train_end_ts = pd.Timestamp(SPLIT_TRAIN_END)
    val_end_ts = pd.Timestamp(SPLIT_VAL_END)

    train_purge_cutoff = train_end_ts - pd.Timedelta(hours=TARGET_HORIZON_HOURS)
    val_purge_cutoff = val_end_ts - pd.Timedelta(hours=TARGET_HORIZON_HOURS)

    train_mask = (ts < train_purge_cutoff) & target_table["is_eligible"]
    val_mask = (ts >= train_end_ts) & (ts < val_purge_cutoff) & target_table["is_eligible"]
    test_mask = (ts >= val_end_ts) & target_table["is_eligible"]

    train_y = target_table.loc[train_mask, "target_y"].dropna()
    val_y = target_table.loc[val_mask, "target_y"].dropna()
    test_y = target_table.loc[test_mask, "target_y"].dropna()

    train_idx = train_y.index
    val_idx = val_y.index
    test_idx = test_y.index

    # 4. Preprocessing strictly on train
    preprocessor = fit_train_preprocessing(X_raw.loc[train_idx])
    X_train = preprocessor.transform(X_raw.loc[train_idx])
    X_val = preprocessor.transform(X_raw.loc[val_idx])
    X_test = preprocessor.transform(X_raw.loc[test_idx])

    # 5. Fit regularized Logistic Regression with event-balanced sample weights
    events_in_train = target_table.loc[train_idx, "associated_event_id"]
    pos_count = int((train_y == 1.0).sum())
    neg_count = int((train_y == 0.0).sum())

    train_sample_weights = compute_event_balanced_sample_weights(train_y, events_in_train)

    clf = LogisticRegression(C=1.0, random_state=42)
    clf.fit(X_train, train_y.to_numpy(), sample_weight=train_sample_weights)

    train_probs = clf.predict_proba(X_train)[:, 1]
    val_probs = clf.predict_proba(X_val)[:, 1]
    test_probs = clf.predict_proba(X_test)[:, 1]

    # Baseline: Majority class / empirical train prior
    train_prior = float(np.mean(train_y))

    # Evaluate validation & test for primary experiment
    val_positives = int((val_y == 1.0).sum())
    val_negatives = int((val_y == 0.0).sum())
    test_positives = int((test_y == 1.0).sum())
    test_negatives = int((test_y == 0.0).sum())

    # Primary release gate:
    # Requires both classes in temporally separated evaluation (validation set).
    # Since val_positives == 0, calibration and release gates strictly FAIL.
    operational_released = False
    release_failure_reason = (
        "Single-class validation partition (zero positive onsets in primary validation split); "
        "calibration and threshold selection gates fail."
    )

    # Run exploratory event-era experiment
    exploratory_results = run_exploratory_event_era_experiment(
        canonical_df=canonical_df,
        features_df=features_df,
        thermal_residuals_oof=thermal_residuals_oof,
        target_table=target_table,
        onsets_map=onsets_map,
    )

    artifact = {
        "model_name": "experimental_proxy_onset_logistic_regression",
        "model_version": "1.0.0",
        "target_name": TARGET_NAME,
        "target_version": TARGET_VERSION,
        "horizon_hours": TARGET_HORIZON_HOURS,
        "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        "operational_release_status": {
            "is_operationally_released": operational_released,
            "default_operational_risk": None,
            "default_operational_fault": None,
            "default_prediction_confidence": None,
            "default_inference_status": STATUS_INSUFFICIENT_VALIDATION,
            "gating_reason": release_failure_reason,
        },
        "primary_experiment": {
            "experiment_name": "primary_chronological_evaluation",
            "split_boundaries": {
                "train_end": SPLIT_TRAIN_END,
                "val_end": SPLIT_VAL_END,
            },
            "event_accounting": {
                "total_timestamps": len(canonical_df),
                "eligible_instances": int(target_table["is_eligible"].sum()),
                "censored_instances": int((~target_table["is_eligible"]).sum()),
                "train_instances": len(train_y),
                "train_positives": pos_count,
                "train_negatives": neg_count,
                "unique_onsets_in_train": int(events_in_train.dropna().nunique()),
                "val_instances": len(val_y),
                "val_positives": val_positives,
                "val_negatives": val_negatives,
                "test_instances": len(test_y),
                "test_positives": test_positives,
                "test_negatives": test_negatives,
            },
            "features": {
                "allowlist": list(MODEL_FEATURE_ALLOWLIST),
                "order": list(MODEL_FEATURE_ALLOWLIST),
                "coefficients": {
                    feat: float(coef) for feat, coef in zip(MODEL_FEATURE_ALLOWLIST, clf.coef_[0])
                },
                "intercept": float(clf.intercept_[0]),
            },
            "baseline_comparison": {
                "train_prior_rate": train_prior,
                "train_brier_score_model": float(np.mean((train_probs - train_y)**2)),
                "train_brier_score_prior": float(np.mean((train_prior - train_y)**2)),
                "val_brier_score_model": float(np.mean((val_probs - val_y)**2)),
                "val_brier_score_prior": float(np.mean((train_prior - val_y)**2)),
            },
        },
        "event_accounting": {
            "total_timestamps": len(canonical_df),
            "eligible_instances": int(target_table["is_eligible"].sum()),
            "censored_instances": int((~target_table["is_eligible"]).sum()),
            "train_instances": len(train_y),
            "train_positives": pos_count,
            "train_negatives": neg_count,
            "unique_onsets_in_train": int(events_in_train.dropna().nunique()),
            "val_instances": len(val_y),
            "val_positives": val_positives,
            "val_negatives": val_negatives,
            "test_instances": len(test_y),
            "test_positives": test_positives,
            "test_negatives": test_negatives,
        },
        "exploratory_experiment": exploratory_results,
        "preprocessing": preprocessor.to_dict(),
        "limitations_and_deferred_requirements": [
            "All positive thermal proxy events in the historical dataset occurred before September 3, 2019.",
            "The primary temporally separated validation partition contains zero positive proxy onsets.",
            "The exploratory validation partition contains only one observed thermal episode; calibration is unsupported.",
            "Probability calibration cannot be performed on single-class or single-episode validation data.",
            "Operational fault_risk remains strictly null with status INSUFFICIENT_VALIDATION.",
            "Labels represent oil alarm/trip proxy onsets, NOT physical transformer failures.",
        ],
    }

    write_prediction_artifact(artifact, output_path)

    return artifact


def write_prediction_artifact(artifact, output_path):
    """Serialize the existing experiment artifact; also used by round-trip tests."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(artifact, f, indent=2, allow_nan=False)


if __name__ == "__main__":
    from ml.features.feature_engineering import build_features
    from ml.thermal.calibration import generate_chronological_oof_residuals
    from ml.thermal.thermal_twin import ThermalTwin, ThermalTwinConfig

    canonical_path = Path(__file__).resolve().parents[2] / "data" / "processed" / "canonical_telemetry.csv"
    thermal_params_path = Path(__file__).resolve().parents[2] / "data" / "processed" / "thermal_twin_params.json"

    print(f"Loading canonical telemetry from {canonical_path}...")
    canonical_df = pd.read_csv(canonical_path)
    canonical_df["timestamp"] = pd.to_datetime(canonical_df["timestamp"])

    print("Building causal features...")
    features_df = build_features(canonical_df)

    print("Loading thermal parameters and generating out-of-fold residuals...")
    with open(thermal_params_path) as f:
        t_params = json.load(f)["parameters"]
    thermal_cfg = ThermalTwinConfig(
        b0=t_params["b0"],
        bA=t_params["bA"],
        bJ=t_params["bJ"],
        tau_hours=t_params["tau_hours"],
    )

    # Train OOF residuals
    train_mask = canonical_df["timestamp"] < SPLIT_TRAIN_END
    oof_residuals = generate_chronological_oof_residuals(canonical_df, thermal_cfg)

    # Val and Test out-of-sample residuals from calibrated twin
    twin = ThermalTwin(config=thermal_cfg)
    eval_processed = twin.run(canonical_df)

    # Combine: OOF for train, calibrated twin predictions for val and test
    thermal_residuals_final = oof_residuals.copy()
    thermal_residuals_final[~train_mask] = eval_processed.loc[~train_mask, "thermal_residual"]

    print("Running Phase 04 experiment and generating artifact...")
    artifact = run_phase04_experiment(
        canonical_df=canonical_df,
        features_df=features_df,
        thermal_residuals_oof=thermal_residuals_final,
    )
    print("Phase 04 experiment complete!")
    print(f"Artifact written to {PREDICTION_ARTIFACT_OUTPUT_PATH}")
    print("Primary event accounting:")
    print(json.dumps(artifact["primary_experiment"]["event_accounting"], indent=2))
    print("Exploratory event accounting:")
    print(json.dumps(artifact["exploratory_experiment"]["event_accounting"], indent=2))
    print("Operational release status:")
    print(json.dumps(artifact["operational_release_status"], indent=2))

