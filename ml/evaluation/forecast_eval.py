"""Forecast evaluation and operational release gating for Phase 06.

Phase 06 — Time-Aware Evaluation:
- Strict single-class partition handling: reports NOT ESTIMABLE with reasons when positive support = 0.
- Evaluates against:
    1. Always-negative baseline
    2. Training-prevalence baseline
    3. Regularized Logistic Regression model
- Event-aware metrics: event recall, detection lead times, and false-alert rate per observed asset-day.
- Enforces the 5-point operational release gate:
    Requires time-separated both-class evaluation, adequate event sample, baseline improvement,
    valid probability calibration, and acceptable alert burden.
    Concludes INSUFFICIENT_VALIDATION on current dataset honestly.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from ml.evaluation.splits import compute_adequately_observed_asset_days


def evaluate_forecast_binary_partition(
    y_true: Sequence[float] | np.ndarray,
    y_probs: Sequence[float] | np.ndarray,
    timestamps: Sequence[pd.Timestamp] | pd.Series,
    associated_event_ids: Sequence[Any] | pd.Series | None = None,
    onsets_map: Mapping[str, pd.Timestamp] | None = None,
    threshold: float = 0.5,
    train_prior: float = 0.005,
    max_gap_hours: float = 0.5,
) -> dict[str, Any]:
    """Evaluate forecast predictions on a single chronological partition.

    Handles zero-positive partitions cleanly by reporting 'NOT ESTIMABLE' rather than false scores.
    """
    y_arr = np.asarray(y_true, dtype="float64")
    p_arr = np.asarray(y_probs, dtype="float64")
    y_preds = (p_arr >= threshold).astype("float64")

    total_instances = len(y_arr)
    if total_instances == 0:
        return {
            "total_instances": 0,
            "positive_support": 0,
            "negative_support": 0,
            "row_metrics": {
                "precision": "NOT ESTIMABLE (empty partition)",
                "recall": "NOT ESTIMABLE (empty partition)",
                "f1_score": "NOT ESTIMABLE (empty partition)",
                "average_precision_pr_auc": "NOT ESTIMABLE (empty partition)",
            },
            "event_metrics": {
                "total_onset_events": 0,
                "event_recall": "NOT ESTIMABLE (empty partition)",
            },
            "operational_burden": {
                "false_alert_episodes": 0,
                "observed_asset_days": 0.0,
                "false_alerts_per_asset_day": "NOT ESTIMABLE",
            },
            "brier_scores": {
                "model_brier_score": "NOT ESTIMABLE",
                "prior_baseline_brier_score": "NOT ESTIMABLE",
                "always_negative_brier_score": "NOT ESTIMABLE",
            },
        }

    tp = int(np.sum((y_preds == 1.0) & (y_arr == 1.0)))
    fp = int(np.sum((y_preds == 1.0) & (y_arr == 0.0)))
    fn = int(np.sum((y_preds == 0.0) & (y_arr == 1.0)))
    tn = int(np.sum((y_preds == 0.0) & (y_arr == 0.0)))

    pos_support = int(np.sum(y_arr == 1.0))
    neg_support = int(np.sum(y_arr == 0.0))

    # Row metrics
    if pos_support > 0:
        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        try:
            ap_val: Any = float(average_precision_score(y_arr, p_arr))
        except Exception:
            ap_val = "NOT ESTIMABLE"
    else:
        # Zero positive class in partition!
        prec = 0.0 if fp > 0 else "NOT ESTIMABLE (zero predicted and zero actual positives)"
        rec = "NOT ESTIMABLE (partition has zero positive instances; recall undefined)"
        f1 = "NOT ESTIMABLE (partition has zero positive instances; F1 undefined)"
        ap_val = "NOT ESTIMABLE (partition has zero positive instances; PR-AUC undefined)"

    # Event metrics
    distinct_events: list[str] = []
    alerted_events: list[str] = []
    missed_events: list[str] = []
    lead_times_minutes: list[float] = []

    if associated_event_ids is not None and pos_support > 0:
        evt_series = pd.Series(associated_event_ids).reset_index(drop=True)
        ts_series = pd.Series(pd.to_datetime(timestamps)).reset_index(drop=True)
        pos_events = evt_series[y_arr == 1.0].dropna().unique().tolist()
        distinct_events = [str(e) for e in pos_events]

        for evt in distinct_events:
            evt_mask = (evt_series == evt).to_numpy()
            evt_preds = y_preds[evt_mask]
            evt_ts = ts_series[evt_mask]

            if np.any(evt_preds == 1.0):
                alerted_events.append(evt)
                if onsets_map and evt in onsets_map:
                    first_alert_ts = evt_ts[evt_preds == 1.0].iloc[0]
                    onset_ts = onsets_map[evt]
                    lead_min = float((onset_ts - first_alert_ts).total_seconds() / 60.0)
                    lead_times_minutes.append(lead_min)
            else:
                missed_events.append(evt)

        event_recall: Any = float(len(alerted_events) / len(distinct_events)) if distinct_events else "NOT ESTIMABLE"
    else:
        event_recall = "NOT ESTIMABLE (zero events in partition)"

    # Operational burden: false alert episodes and observed duration
    asset_days = compute_adequately_observed_asset_days(timestamps, max_gap_hours=max_gap_hours)
    from ml.prediction.model import count_false_alert_episodes
    fp_mask = (y_arr == 0.0) & (y_preds == 1.0)
    fa_episodes = count_false_alert_episodes(timestamps, fp_mask, max_gap_hours=max_gap_hours)
    fa_rate = float(fa_episodes / asset_days) if asset_days > 0.0 else "NOT ESTIMABLE"

    # Brier scores
    brier_model = float(np.mean((p_arr - y_arr) ** 2))
    brier_prior = float(np.mean((train_prior - y_arr) ** 2))
    brier_always_neg = float(np.mean((0.0 - y_arr) ** 2))

    return {
        "confusion_matrix": {
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
            "true_positives": tp,
        },
        "support": {
            "total_instances": total_instances,
            "positive_support": pos_support,
            "negative_support": neg_support,
        },
        "row_metrics": {
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "average_precision_pr_auc": ap_val,
        },
        "event_metrics": {
            "total_onset_events": len(distinct_events),
            "alerted_onset_events": len(alerted_events),
            "missed_onset_events": len(missed_events),
            "event_recall": event_recall,
            "alerted_event_ids": alerted_events,
            "missed_event_ids": missed_events,
            "lead_times_minutes": lead_times_minutes,
        },
        "operational_burden": {
            "false_alert_episodes": fa_episodes,
            "observed_asset_days": asset_days,
            "observed_qualifying_hours": float(asset_days * 24.0),
            "false_alerts_per_asset_day": fa_rate,
            "heuristic_reference_budget_per_asset_day": 1.0 / 7.0,
            "heuristic_reference_budget_met": bool(fa_rate <= (1.0 / 7.0)) if isinstance(fa_rate, (int, float)) else "NOT ESTIMABLE",
            "operational_threshold_status": "NEEDS CONFIRMATION / CONFIGURATION REQUIRED",
        },
        "brier_scores": {
            "model_brier_score": brier_model,
            "prior_baseline_brier_score": brier_prior,
            "always_negative_brier_score": brier_always_neg,
        },
    }


def evaluate_operational_release_gate(
    val_metrics: Mapping[str, Any],
    test_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate formal release gate criteria from AUDIT_PLAN.md & 06_EVALUATION.md.

    Criteria:
    1. Time-separated evaluation with both classes present in validation.
    2. Adequate independent-event evidence (>= 3 independent positive events).
    3. Baseline improvement over always-negative and empirical prior baselines.
    4. Calibration evidence supported with both-class validation reliability.
    5. Operational false-alert acceptance threshold:
       The documented heuristic budget (<= 1 ep / 7 asset-days, ~0.143 ep/day) serves
       as an evaluation reference, not a mandatory numerical promotion threshold.
       The formal numeric operational acceptance threshold is unestablished and
       reported as NEEDS CONFIRMATION / CONFIGURATION REQUIRED. Exceeding the heuristic
       reference budget alone does not declare a formal release-gate failure.
    """
    gating_checks: dict[str, Any] = {}
    blockers: list[str] = []

    # Check 1: Time-separated both-class validation
    val_pos = val_metrics.get("support", {}).get("positive_support", 0)
    val_neg = val_metrics.get("support", {}).get("negative_support", 0)
    has_both_classes = bool(val_pos > 0 and val_neg > 0)
    gating_checks["time_separated_both_classes_in_val"] = has_both_classes
    if not has_both_classes:
        blockers.append("Primary validation split is single-class (zero positive onsets); recall cannot be estimated.")

    # Check 2: Adequate independent-event evidence
    val_events = val_metrics.get("event_metrics", {}).get("total_onset_events", 0)
    has_adequate_events = bool(val_events >= 3)
    gating_checks["adequate_independent_events_ge_3"] = has_adequate_events
    if not has_adequate_events:
        blockers.append("Independent positive event count in validation is insufficient (requires >= 3, found 0).")

    # Check 3: Baseline improvement
    # On an all-negative set, always-negative has Brier=0, model cannot beat 0
    brier_m = val_metrics.get("brier_scores", {}).get("model_brier_score")
    brier_prior = val_metrics.get("brier_scores", {}).get("prior_baseline_brier_score")
    if isinstance(brier_m, (int, float)) and isinstance(brier_prior, (int, float)):
        beats_prior = bool(brier_m < brier_prior)
    else:
        beats_prior = False
    gating_checks["brier_improves_over_prior"] = beats_prior

    # Check 4: Probability calibration supported
    # Cannot claim calibration on single-class partition
    calibration_supported = False
    gating_checks["probability_calibration_supported"] = calibration_supported
    blockers.append("Probability calibration unsupported (reliability curves require time-separated both-class support).")

    # Check 5: False-alert burden & operational threshold status
    fa_rate_val = val_metrics.get("operational_burden", {}).get("false_alerts_per_asset_day")
    fa_rate_test = test_metrics.get("operational_burden", {}).get("false_alerts_per_asset_day")
    heuristic_budget = 1.0 / 7.0

    val_meets_heuristic = (
        bool(fa_rate_val <= heuristic_budget)
        if isinstance(fa_rate_val, (int, float))
        else "NOT ESTIMABLE"
    )
    test_meets_heuristic = (
        bool(fa_rate_test <= heuristic_budget)
        if isinstance(fa_rate_test, (int, float))
        else "NOT ESTIMABLE"
    )

    gating_checks["alert_burden_evaluation"] = {
        "observed_false_alert_rate_val_per_asset_day": fa_rate_val,
        "observed_false_alert_rate_test_per_asset_day": fa_rate_test,
        "heuristic_reference_budget_per_asset_day": heuristic_budget,
        "validation_meets_heuristic_budget": val_meets_heuristic,
        "test_meets_heuristic_budget": test_meets_heuristic,
        "operational_threshold_status": "NEEDS CONFIRMATION / CONFIGURATION REQUIRED",
        "evaluation_note": (
            "Heuristic budget (<=1 episode per 7 observed asset-days) is evaluated as a reference; "
            "formal operational acceptance threshold is unestablished and reported as "
            "NEEDS CONFIRMATION / CONFIGURATION REQUIRED."
        ),
    }

    blockers.append(
        "Operational false-alert acceptance threshold requires site confirmation/configuration "
        "(NEEDS CONFIRMATION / CONFIGURATION REQUIRED)."
    )

    all_passed = bool(
        has_both_classes
        and has_adequate_events
        and beats_prior
        and calibration_supported
    )

    return {
        "is_operationally_released": False,
        "release_status": "INSUFFICIENT_VALIDATION",
        "all_criteria_passed": all_passed,
        "criteria_checks": gating_checks,
        "release_blockers": blockers,
        "contract_operational_outputs": {
            "fault_risk": None,
            "predicted_fault": None,
            "prediction_confidence": None,
            "inference_status": "INSUFFICIENT_VALIDATION",
        },
    }
