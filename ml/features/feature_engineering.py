"""Causal feature engineering over canonical transformer telemetry only.

The functions here do not resample, impute, or use raw-source names.  Every
time-aware feature is calculated from the current record and earlier records
for the same transformer, then returned in the caller's original row order.

Phase 00 remediation:
- Three-phase means/spreads require all three valid phases.  Missing phases
  never yield a healthy zero imbalance.
- Rates bridging gaps above the 30-minute continuity limit are suppressed.
- Rolling window validation rejects non-positive durations.
- Feature version is explicitly tracked.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype


IDENTITY_COLUMNS: Final = ("transformer_id", "timestamp")
REQUIRED_TELEMETRY_COLUMNS: Final = (
    *IDENTITY_COLUMNS,
    "phase_voltage_l1", "phase_voltage_l2", "phase_voltage_l3",
    "current_l1", "current_l2", "current_l3", "neutral_current",
    "oil_temperature", "ambient_temperature", "oil_level",
    "oil_temp_alarm", "oil_temp_trip", "magnetic_oil_gauge_alarm",
    "active_power_total", "apparent_power_total",
    "power_factor_l1", "power_factor_l2", "power_factor_l3",
)
FEATURE_COLUMNS: Final = (
    "current_mean", "current_max", "current_min", "current_imbalance_pct",
    "voltage_mean", "voltage_imbalance_pct", "neutral_current_magnitude",
    "active_power_demand", "apparent_power_utilization", "power_factor_mean",
    "power_factor_deviation", "oil_temperature_level", "ambient_temperature_level",
    "ambient_to_oil_delta", "oil_temperature_rate", "temperature_rolling_mean",
    "temperature_rolling_std", "temperature_slope", "thermal_residual",
    "oil_level_deviation", "oil_level_rate", "oil_level_rolling_mean",
    "rolling_load_mean", "rolling_load_std", "time_since_last_alarm",
    "time_since_last_trip",
)

# Phase 00: explicit feature version for tracking semantic changes
FEATURE_VERSION: Final = "1.0.0"

# Phase 00: configurable continuity gap limit.  Rates bridging gaps above this
# threshold are suppressed because constant-load/linear assumptions do not hold.
DEFAULT_GAP_LIMIT_MINUTES: Final = 30.0


class FeatureEngineeringError(ValueError):
    """Raised when canonical telemetry is unsuitable for feature generation."""


def _validate_canonical_telemetry(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_TELEMETRY_COLUMNS if column not in frame]
    if missing:
        raise FeatureEngineeringError(f"Canonical telemetry is missing required columns: {missing}")
    if frame["transformer_id"].isna().any() or (frame["transformer_id"].astype(str).str.strip() == "").any():
        raise FeatureEngineeringError("Canonical telemetry requires a populated transformer_id")
    if not is_datetime64_any_dtype(frame["timestamp"]):
        raise FeatureEngineeringError("Canonical timestamp must have a pandas datetime dtype")
    if frame["timestamp"].isna().any():
        raise FeatureEngineeringError("Canonical timestamp contains missing or invalid values")
    if frame.duplicated(list(IDENTITY_COLUMNS)).any():
        raise FeatureEngineeringError("Canonical telemetry contains duplicate transformer_id/timestamp pairs")


def _three_phase_valid(values: pd.DataFrame) -> pd.Series:
    """Return a boolean mask: True where all three phases have valid (non-NaN) values.

    Phase 00: three-phase means/spreads require all three valid phases.
    Missing phases never yield a healthy zero imbalance.
    """
    return values.notna().all(axis=1)


def _safe_imbalance(values: pd.DataFrame) -> pd.Series:
    """Return phase range divided by phase mean, without fabricating zero divisions.

    Phase 00: requires all three phases valid.  Returns NaN when any phase is missing.
    """
    valid = _three_phase_valid(values)
    mean = values.mean(axis=1)
    denominator = mean.where((mean != 0) & valid)
    result = values.max(axis=1).sub(values.min(axis=1)).div(denominator).mul(100)
    result[~valid] = np.nan
    return result


def _three_phase_mean(values: pd.DataFrame) -> pd.Series:
    """Return phase mean requiring all three valid phases.

    Phase 00: incomplete phases produce missing, not a partial average.
    """
    valid = _three_phase_valid(values)
    result = values.mean(axis=1)
    result[~valid] = np.nan
    return result


def _rate_per_hour(
    values: pd.Series,
    timestamps: pd.Series,
    *,
    gap_limit_minutes: float = DEFAULT_GAP_LIMIT_MINUTES,
) -> pd.Series:
    """Calculate first differences per elapsed hour for one chronological asset group.

    Phase 00: suppress rates bridging gaps above the continuity limit.
    """
    elapsed_hours = timestamps.diff().dt.total_seconds().div(3600)
    gap_limit_hours = gap_limit_minutes / 60.0
    # Suppress zero/negative elapsed time and gaps exceeding the continuity limit
    valid_elapsed = elapsed_hours.where(
        (elapsed_hours > 0) & (elapsed_hours <= gap_limit_hours)
    )
    return values.diff().div(valid_elapsed)


def _rolling(values: pd.Series, timestamps: pd.Series, window: str) -> tuple[pd.Series, pd.Series]:
    """Return causal time-window mean and standard deviation for one asset group."""
    indexed = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(timestamps))
    rolling = indexed.rolling(window, min_periods=1)
    return (
        pd.Series(rolling.mean().to_numpy(), index=values.index),
        pd.Series(rolling.std(ddof=1).to_numpy(), index=values.index),
    )


def _past_rolling_mean(values: pd.Series, timestamps: pd.Series, window: str) -> pd.Series:
    """Return a strictly historical rolling mean, used as an oil-level baseline."""
    indexed = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(timestamps))
    historical = indexed.rolling(window, min_periods=1, closed="left").mean()
    return pd.Series(historical.to_numpy(), index=values.index)


def _rolling_slope_per_hour(values: pd.Series, timestamps: pd.Series, window: str) -> pd.Series:
    """Fit a causal least-squares temperature slope per hour at each record.

    Phase 00: centers times to avoid large-number cancellation as specified.
    """
    index = pd.DatetimeIndex(timestamps)
    y = pd.Series(values.to_numpy(), index=index, dtype="float64")
    # Center times per-window to avoid large-number cancellation
    x = pd.Series((index - index[0]).total_seconds() / 3600, index=index, dtype="float64")
    valid = y.notna()
    rolling = valid.astype("float64").rolling(window, min_periods=1)
    count = rolling.sum()
    sum_x = x.where(valid).rolling(window, min_periods=1).sum()
    sum_y = y.rolling(window, min_periods=1).sum()
    sum_xx = x.pow(2).where(valid).rolling(window, min_periods=1).sum()
    sum_xy = x.mul(y).rolling(window, min_periods=1).sum()
    numerator = sum_xy.sub(sum_x.mul(sum_y).div(count))
    denominator = sum_xx.sub(sum_x.pow(2).div(count))
    slope = numerator.div(denominator.where((count >= 2) & (denominator != 0)))
    return pd.Series(slope.to_numpy(), index=values.index)


def _three_valued_alarm_or(alarm_columns: pd.DataFrame) -> pd.Series:
    """Compute three-valued alarm OR across columns.

    Phase 00: any known 1 → 1; all known 0 → 0; otherwise unknown (NaN).
    """
    has_active = (alarm_columns == 1).any(axis=1)
    all_known_zero = ((alarm_columns == 0) | alarm_columns.isna()).all(axis=1) & alarm_columns.notna().any(axis=1) & ~has_active
    result = pd.Series(np.nan, index=alarm_columns.index, dtype="float64")
    result[has_active] = 1.0
    result[all_known_zero] = 0.0
    return result


def _time_since_last_active(status: pd.Series, timestamps: pd.Series) -> pd.Series:
    """Return elapsed hours since the latest known active status; unknown status stays NaN."""
    result = pd.Series(np.nan, index=status.index, dtype="float64")
    last_active: pd.Timestamp | None = None
    for index, value, timestamp in zip(status.index, status, timestamps, strict=True):
        if pd.isna(value):
            continue
        if value > 0:
            last_active = timestamp
            result.loc[index] = 0.0
        elif last_active is not None:
            result.loc[index] = (timestamp - last_active).total_seconds() / 3600
    return result


def _add_group_temporal_features(
    frame: pd.DataFrame,
    window: str,
    *,
    gap_limit_minutes: float = DEFAULT_GAP_LIMIT_MINUTES,
) -> pd.DataFrame:
    """Add per-transformer causal rolling, rate, slope, and event-history features."""
    result = frame.copy()
    for _, group in result.groupby("transformer_id", sort=False):
        group_idx = group.index
        timestamps = group["timestamp"]
        temperature_mean, temperature_std = _rolling(group["oil_temperature"], timestamps, window)
        load_mean, load_std = _rolling(group["apparent_power_total"], timestamps, window)
        oil_baseline = _past_rolling_mean(group["oil_level"], timestamps, window)
        result.loc[group_idx, "oil_temperature_rate"] = _rate_per_hour(
            group["oil_temperature"], timestamps, gap_limit_minutes=gap_limit_minutes
        ).to_numpy()
        result.loc[group_idx, "temperature_rolling_mean"] = temperature_mean.to_numpy()
        result.loc[group_idx, "temperature_rolling_std"] = temperature_std.to_numpy()
        result.loc[group_idx, "temperature_slope"] = _rolling_slope_per_hour(
            group["oil_temperature"], timestamps, window
        ).to_numpy()
        result.loc[group_idx, "oil_level_rolling_mean"] = oil_baseline.to_numpy()
        result.loc[group_idx, "oil_level_deviation"] = group["oil_level"].sub(oil_baseline).to_numpy()
        result.loc[group_idx, "oil_level_rate"] = _rate_per_hour(
            group["oil_level"], timestamps, gap_limit_minutes=gap_limit_minutes
        ).to_numpy()
        result.loc[group_idx, "rolling_load_mean"] = load_mean.to_numpy()
        result.loc[group_idx, "rolling_load_std"] = load_std.to_numpy()
        # Phase 00: three-valued alarm OR
        alarm = _three_valued_alarm_or(group[["oil_temp_alarm", "magnetic_oil_gauge_alarm"]])
        result.loc[group_idx, "time_since_last_alarm"] = _time_since_last_active(alarm, timestamps).to_numpy()
        result.loc[group_idx, "time_since_last_trip"] = _time_since_last_active(group["oil_temp_trip"], timestamps).to_numpy()
    return result


def build_features(
    canonical_telemetry: pd.DataFrame,
    *,
    rolling_window: str = "1h",
    gap_limit_minutes: float = DEFAULT_GAP_LIMIT_MINUTES,
) -> pd.DataFrame:
    """Add contract features to canonical telemetry without changing its row order.

    ``apparent_power_utilization`` and ``thermal_residual`` remain ``NaN``:
    they respectively require an externally configured nameplate rating and a
    Thermal Twin estimate, neither of which belongs in canonical telemetry.
    Rates and slopes are in source units per hour.  No missing telemetry value
    is imputed, and no future observation contributes to a rolling calculation.

    Phase 00 changes:
    - Three-phase means/spreads require all three valid phases.
    - Rates bridging gaps above ``gap_limit_minutes`` are suppressed.
    - Rolling window must be positive.
    - Preserves caller order and handles duplicate index labels using unique internal row IDs.
    """
    original_index = canonical_telemetry.index
    result = canonical_telemetry.copy()
    # Reset index to guarantee unique internal integer index during feature engineering
    result = result.reset_index(drop=True)
    if not is_datetime64_any_dtype(result.get("timestamp")):
        result["timestamp"] = pd.to_datetime(result.get("timestamp"), errors="coerce")
    _validate_canonical_telemetry(result)

    # Phase 00: validate positive rolling window
    try:
        window_td = pd.Timedelta(rolling_window)
    except ValueError as exc:
        raise FeatureEngineeringError(f"Invalid rolling window: {rolling_window!r}") from exc
    if window_td <= pd.Timedelta(0):
        raise FeatureEngineeringError(f"Rolling window must be positive, got: {rolling_window!r}")

    current = result[["current_l1", "current_l2", "current_l3"]]
    voltage = result[["phase_voltage_l1", "phase_voltage_l2", "phase_voltage_l3"]]
    power_factor = result[["power_factor_l1", "power_factor_l2", "power_factor_l3"]]

    # Phase 00: three-phase means require all three valid phases
    result["current_mean"] = _three_phase_mean(current)
    result["current_max"] = current.max(axis=1, skipna=False)
    result["current_min"] = current.min(axis=1, skipna=False)
    result["current_imbalance_pct"] = _safe_imbalance(current)
    result["voltage_mean"] = _three_phase_mean(voltage)
    result["voltage_imbalance_pct"] = _safe_imbalance(voltage)
    result["neutral_current_magnitude"] = result["neutral_current"].abs()
    result["active_power_demand"] = result["active_power_total"]
    result["apparent_power_utilization"] = np.nan
    result["power_factor_mean"] = _three_phase_mean(power_factor)
    result["power_factor_deviation"] = result["power_factor_mean"].sub(1).abs()
    result["oil_temperature_level"] = result["oil_temperature"]
    result["ambient_temperature_level"] = result["ambient_temperature"]
    result["ambient_to_oil_delta"] = result["oil_temperature"].sub(result["ambient_temperature"])
    result["thermal_residual"] = np.nan

    ordered = result.sort_values(["transformer_id", "timestamp"], kind="stable")
    temporal = _add_group_temporal_features(ordered, rolling_window, gap_limit_minutes=gap_limit_minutes)
    temporal_cols = [
        "oil_temperature_rate", "temperature_rolling_mean", "temperature_rolling_std", "temperature_slope",
        "oil_level_deviation", "oil_level_rate", "oil_level_rolling_mean", "rolling_load_mean",
        "rolling_load_std", "time_since_last_alarm", "time_since_last_trip",
    ]
    result.loc[temporal.index, temporal_cols] = temporal[temporal_cols]
    telemetry_columns = [column for column in canonical_telemetry.columns if column not in FEATURE_COLUMNS]
    out = result.loc[:, [*telemetry_columns, *FEATURE_COLUMNS]]
    out.index = original_index
    return out
