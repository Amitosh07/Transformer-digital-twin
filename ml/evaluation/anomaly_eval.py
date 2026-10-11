"""Anomaly detection and false-alert burden evaluation on held-out chronological partitions.

Phase 06 — Time-Aware Evaluation:
- Count actual false-alert episodes, merging consecutive alert rows within continuity gap (<= 30 min).
- Compute observed asset-days using actual elapsed time, excluding long gaps > 30 min.
- False alert rate = false_alert_episodes / observed_asset_days.
- Initial heuristic alert budget check: <= 1 episode / 7 observed asset-days.
- Reason code distribution and coverage tracking.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from ml.evaluation.splits import compute_adequately_observed_asset_days


def count_flagged_episodes(
    timestamps: Sequence[pd.Timestamp] | pd.Series,
    flag_series: Sequence[bool] | pd.Series,
    max_gap_hours: float = 0.5,
) -> int:
    """Count alert episodes by merging contiguous flagged observations.

    Adjacent flagged rows with dt <= max_gap_hours belong to the same episode.
    """
    ts = pd.Series(pd.to_datetime(timestamps)).reset_index(drop=True)
    flags = pd.Series(flag_series).fillna(False).astype(bool).reset_index(drop=True)

    flagged_indices = flags[flags].index.tolist()
    if not flagged_indices:
        return 0

    episodes = 0
    in_episode = False
    last_flagged_ts: pd.Timestamp | None = None

    for idx in flagged_indices:
        cur_ts = ts.iloc[idx]
        if not in_episode:
            episodes += 1
            in_episode = True
        else:
            if last_flagged_ts is not None:
                dt_hours = (cur_ts - last_flagged_ts).total_seconds() / 3600.0
                if dt_hours > max_gap_hours:
                    # New distinct episode after continuity gap
                    episodes += 1
        last_flagged_ts = cur_ts

    return episodes


def evaluate_anomaly_on_partition(
    partition_df: pd.DataFrame,
    max_gap_hours: float = 0.5,
) -> dict[str, Any]:
    """Evaluate anomaly detector outputs and alert burden on a held-out chronological partition."""
    df = partition_df.copy().sort_values("timestamp").reset_index(drop=True)

    total_rows = len(df)
    if total_rows == 0:
        return {
            "total_rows": 0,
            "coverage_ratio": 0.0,
            "flagged_rows": 0,
            "flagged_episodes": 0,
            "observed_asset_days": 0.0,
            "false_alert_rate_per_asset_day": "NOT ESTIMABLE",
            "heuristic_reference_budget_per_asset_day": 1.0 / 7.0,
            "heuristic_reference_budget_met": "NOT ESTIMABLE",
            "operational_acceptance_threshold": "NEEDS CONFIRMATION / CONFIGURATION REQUIRED",
            "reasons_breakdown": {},
        }

    # Coverage: valid anomaly score
    score_col = df.get("anomaly_score")
    if score_col is not None:
        valid_scores = score_col.notna().sum()
        cov = float(valid_scores / total_rows)
    else:
        cov = 0.0

    flag_col = df.get("anomaly_flag", pd.Series([False] * total_rows)).fillna(False).astype(bool)
    flagged_rows = int(flag_col.sum())

    # Episode counting
    episodes = count_flagged_episodes(df["timestamp"], flag_col, max_gap_hours=max_gap_hours)

    # Observed asset-days exposure
    asset_days = compute_adequately_observed_asset_days(df["timestamp"], max_gap_hours=max_gap_hours)

    fa_rate = float(episodes / asset_days) if asset_days > 0.0 else "NOT ESTIMABLE"
    budget_ok: Any = "NOT ESTIMABLE"
    if isinstance(fa_rate, float):
        budget_limit = 1.0 / 7.0  # 1 episode per 7 asset-days (~0.1429)
        budget_ok = bool(fa_rate <= budget_limit)

    # Breakdown of reasons
    reasons_breakdown: dict[str, int] = {}
    if "reason_codes" in df.columns:
        for r_list in df.loc[flag_col, "reason_codes"]:
            if isinstance(r_list, (list, tuple)):
                for r in r_list:
                    reasons_breakdown[str(r)] = reasons_breakdown.get(str(r), 0) + 1

    return {
        "total_rows": total_rows,
        "coverage_ratio": cov,
        "flagged_rows": flagged_rows,
        "flagged_row_ratio": float(flagged_rows / total_rows) if total_rows > 0 else 0.0,
        "flagged_episodes": episodes,
        "observed_asset_days": asset_days,
        "observed_qualifying_hours": float(asset_days * 24.0),
        "false_alert_rate_per_asset_day": fa_rate,
        "heuristic_reference_budget_per_asset_day": 1.0 / 7.0,
        "heuristic_reference_budget_met": budget_ok,
        "operational_acceptance_threshold": "NEEDS CONFIRMATION / CONFIGURATION REQUIRED",
        "reasons_breakdown": reasons_breakdown,
    }
