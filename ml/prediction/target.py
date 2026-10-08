"""Target definition, eligibility, censoring, and feature extraction for Phase 04.

Phase 04 — Experimental Future Proxy Prediction:
Target:
    Will a NEW oil-temperature alarm OR trip occur within the next 1 hour (t < e <= t + 1h),
    given that both are known clear at prediction time t?

Three-valued contact state B_t:
    - 1 if oil_temp_alarm == 1 or oil_temp_trip == 1
    - 0 if oil_temp_alarm == 0 and oil_temp_trip == 0
    - NaN otherwise (unknown)

Eligibility at t:
    - Current contact state B_t is known clear (0).
    - Continuity from previous observation <= 30 minutes.
    - Future horizon (t + 1 hour) has adequate observation follow-up.

Censoring:
    - Examples ending before t + 1h without an onset are censored (Y = NaN).
    - Examples with a continuity gap > 30 minutes within (t, t + 1h] before an onset are censored.
    - Examples with unknown contact states within (t, t + 1h] before an onset are censored.

Predeclared Causal Feature Allowlist:
    - oil_temperature
    - ambient_temperature
    - temperature_slope
    - current_mean
    - current_imbalance_pct
    - apparent_power_total
    - rolling_load_mean
    - thermal_residual_positive (Phase 01 out-of-fold positive residual only)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Final, Sequence

import numpy as np
import pandas as pd


TARGET_HORIZON_HOURS: Final = 1.0
DEFAULT_CONTINUITY_GAP_HOURS: Final = 0.5
TARGET_NAME: Final = "new_oil_alert_within_1h"
TARGET_VERSION: Final = "1.0.0"

# Strict allowlist of causal model features
MODEL_FEATURE_ALLOWLIST: Final[tuple[str, ...]] = (
    "oil_temperature",
    "ambient_temperature",
    "temperature_slope",
    "current_mean",
    "current_imbalance_pct",
    "apparent_power_total",
    "rolling_load_mean",
    "thermal_residual",
)

# Forbidden feature names to guard against leakage
FORBIDDEN_FEATURES: Final[frozenset[str]] = frozenset({
    "oil_temp_alarm",
    "oil_temp_trip",
    "magnetic_oil_gauge_alarm",
    "time_since_last_alarm",
    "time_since_last_trip",
    "winding_temperature",
    "health_index",
    "health_components",
    "health_reason_codes",
    "anomaly_score",
    "anomaly_flag",
    "energy_kwh",
    "timestamp",
    "transformer_id",
    "event_id",
})


class TargetConstructionError(ValueError):
    """Raised when target construction or feature allowlist validation fails."""


def compute_three_valued_contact_state(
    oil_alarm: pd.Series,
    oil_trip: pd.Series,
) -> pd.Series:
    """Compute three-valued current contact state: 1 (any active), 0 (both clear), NaN (unknown)."""
    b = pd.Series(np.nan, index=oil_alarm.index, dtype="float64")
    active_mask = (oil_alarm == 1.0) | (oil_trip == 1.0)
    clear_mask = (oil_alarm == 0.0) & (oil_trip == 0.0)
    b[active_mask] = 1.0
    b[clear_mask] = 0.0
    return b


def find_valid_onsets(
    timestamps: pd.Series,
    b_state: pd.Series,
    max_gap_hours: float = DEFAULT_CONTINUITY_GAP_HOURS,
) -> list[dict[str, Any]]:
    """Identify valid clear-to-active transitions within continuity gap."""
    onsets: list[dict[str, Any]] = []
    ts = timestamps.to_numpy()
    b = b_state.to_numpy()
    n = len(ts)

    for i in range(1, n):
        if b[i] == 1.0 and b[i - 1] == 0.0:
            dt_h = (pd.Timestamp(ts[i]) - pd.Timestamp(ts[i - 1])).total_seconds() / 3600.0
            if dt_h <= max_gap_hours:
                onsets.append({
                    "event_id": f"ONSET_{len(onsets) + 1:03d}",
                    "row_index": i,
                    "timestamp": pd.Timestamp(ts[i]),
                    "dt_from_prev_hours": dt_h,
                })
    return onsets


def build_proxy_target_table(
    df: pd.DataFrame,
    horizon_hours: float = TARGET_HORIZON_HOURS,
    max_gap_hours: float = DEFAULT_CONTINUITY_GAP_HOURS,
) -> pd.DataFrame:
    """Construct leakage-safe next-hour proxy onset target, eligibility, and censoring table.

    Returns DataFrame with columns:
        - target_y: 1.0 (positive), 0.0 (negative), NaN (censored or ineligible)
        - is_eligible: bool
        - censoring_reason: str or None
        - associated_event_id: str or None
    """
    ordered = df.sort_values("timestamp").reset_index(drop=True)
    timestamps = pd.to_datetime(ordered["timestamp"])
    b_state = compute_three_valued_contact_state(
        ordered["oil_temp_alarm"],
        ordered["oil_temp_trip"],
    )

    onsets = find_valid_onsets(timestamps, b_state, max_gap_hours=max_gap_hours)
    onset_timestamps = [o["timestamp"] for o in onsets]
    onset_event_ids = [o["event_id"] for o in onsets]

    n = len(ordered)
    target_y = np.full(n, np.nan, dtype="float64")
    is_eligible = np.zeros(n, dtype=bool)
    censoring_reason: list[str | None] = [None] * n
    associated_event_id: list[str | None] = [None] * n

    ts_arr = timestamps.to_numpy()
    b_arr = b_state.to_numpy()

    for i in range(n):
        cur_t = pd.Timestamp(ts_arr[i])
        cur_b = b_arr[i]

        # 1. Eligibility at t: current state must be known clear (0)
        if cur_b != 0.0 or np.isnan(cur_b):
            censoring_reason[i] = "CURRENT_STATE_NOT_CLEAR"
            continue

        # Check prior continuity: if previous observation exists, gap must be <= max_gap_hours
        if i > 0:
            dt_prior = (cur_t - pd.Timestamp(ts_arr[i - 1])).total_seconds() / 3600.0
            if dt_prior > max_gap_hours:
                censoring_reason[i] = "PRIOR_CONTINUITY_GAP"
                continue

        horizon_end = cur_t + pd.Timedelta(hours=horizon_hours)

        # 2. Check for positive onset in (cur_t, horizon_end]
        # Open on left, closed on right: cur_t < e <= horizon_end
        matched_onsets = [
            (ot, eid) for ot, eid in zip(onset_timestamps, onset_event_ids)
            if cur_t < ot <= horizon_end
        ]

        if matched_onsets:
            # Positive instance!
            is_eligible[i] = True
            target_y[i] = 1.0
            associated_event_id[i] = matched_onsets[0][1]
            continue

        # 3. If no onset, verify complete, gap-free observation through horizon_end to label negative
        # Scan forward from i+1
        j = i + 1
        valid_negative = True
        last_forward_t = cur_t

        while j < n:
            forward_t = pd.Timestamp(ts_arr[j])
            forward_b = b_arr[j]
            dt_step = (forward_t - last_forward_t).total_seconds() / 3600.0

            if dt_step > max_gap_hours:
                # Gap before horizon end
                valid_negative = False
                censoring_reason[i] = "HORIZON_GAP_CENSORED"
                break

            if np.isnan(forward_b):
                # Unknown contact state during horizon
                valid_negative = False
                censoring_reason[i] = "UNKNOWN_CONTACT_STATE_CENSORED"
                break

            if forward_b == 1.0 and forward_t <= horizon_end:
                # Active contact found that wasn't a clean onset (e.g., across an unverified gap)
                valid_negative = False
                censoring_reason[i] = "AMBIGUOUS_CONTACT_CENSORED"
                break

            last_forward_t = forward_t
            if forward_t >= horizon_end:
                break
            j += 1

        if j >= n and last_forward_t < horizon_end:
            # End of dataset reached before horizon end
            valid_negative = False
            censoring_reason[i] = "END_OF_RECORD_CENSORED"

        if valid_negative:
            is_eligible[i] = True
            target_y[i] = 0.0

    result = pd.DataFrame({
        "timestamp": timestamps,
        "current_b_state": b_state,
        "is_eligible": is_eligible,
        "target_y": target_y,
        "censoring_reason": censoring_reason,
        "associated_event_id": associated_event_id,
    }, index=ordered.index)

    return result


def extract_model_features(
    df: pd.DataFrame,
    thermal_residuals: pd.Series | None = None,
    allow_superset: bool = False,
) -> pd.DataFrame:
    """Extract and validate the predeclared causal model feature vector.

    Enforces allowlist and strictly rejects forbidden leakage features.
    If allow_superset is False (default), raises TargetConstructionError if any forbidden feature is in df.
    If allow_superset is True, extracts only allowlisted features from df and verifies the result
    contains zero forbidden features.
    """
    if not allow_superset:
        for forbidden in FORBIDDEN_FEATURES:
            if forbidden in df.columns:
                # Note: thermal_residual is allowed only as out-of-sample thermal feature
                if forbidden == "thermal_residual" and thermal_residuals is not None:
                    continue
                raise TargetConstructionError(f"Forbidden feature detected: {forbidden}")

    feat = pd.DataFrame(index=df.index)

    for col in MODEL_FEATURE_ALLOWLIST:
        if col == "thermal_residual":
            if thermal_residuals is not None:
                # Use only positive out-of-sample residual; clamp negative to 0.0
                r = pd.to_numeric(thermal_residuals, errors="coerce")
                feat["thermal_residual"] = np.where(r > 0, r, 0.0)
            elif "thermal_residual" in df.columns:
                r = pd.to_numeric(df["thermal_residual"], errors="coerce")
                feat["thermal_residual"] = np.where(r > 0, r, 0.0)
            else:
                feat["thermal_residual"] = np.nan
        else:
            if col in df.columns:
                feat[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                feat[col] = np.nan

    out = feat.loc[:, list(MODEL_FEATURE_ALLOWLIST)]
    for forbidden in FORBIDDEN_FEATURES:
        if forbidden in out.columns and forbidden != "thermal_residual":
            raise TargetConstructionError(f"Forbidden leakage feature leaked into output: {forbidden}")

    return out
