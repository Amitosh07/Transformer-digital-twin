"""A causal, interpretable dynamic thermal baseline.

The twin consumes canonical telemetry and engineered features only.  Its
coefficients are required configuration rather than assumed transformer ratings
or engineering constants; callers must set them for their verified data units.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype


THERMAL_OUTPUT_COLUMNS: Final = (
    "thermal_model_temperature",
    "thermal_residual",
    "thermal_state",
)
REQUIRED_INPUT_COLUMNS: Final = (
    "transformer_id",
    "timestamp",
    "oil_temperature",
    "ambient_temperature",
    "active_power_demand",
)


class ThermalTwinError(ValueError):
    """Raised when thermal-twin inputs or configuration are invalid."""


@dataclass(frozen=True)
class ThermalTwinConfig:
    """Explicit unit-dependent parameters for the dynamic thermal baseline.

    ``load_gain`` converts the configured load signal (the feature
    ``active_power_demand``) to a temperature rise in the verified source unit.
    ``response_alpha`` is the fraction of the prior-to-equilibrium gap applied
    over each transformer's first valid observation interval.  Later updates
    scale that response by their actual elapsed-time ratio.  Residual
    thresholds are absolute values in the same temperature unit and determine
    NORMAL/ELEVATED/CRITICAL states.
    """

    load_gain: float
    response_alpha: float
    normal_residual_abs_max: float
    elevated_residual_abs_max: float

    def __post_init__(self) -> None:
        if not 0 < self.response_alpha <= 1:
            raise ThermalTwinError("response_alpha must be greater than 0 and no more than 1")
        if self.normal_residual_abs_max < 0:
            raise ThermalTwinError("normal_residual_abs_max must be non-negative")
        if self.elevated_residual_abs_max < self.normal_residual_abs_max:
            raise ThermalTwinError("elevated_residual_abs_max must be at least normal_residual_abs_max")
        if not all(np.isfinite(value) for value in (
            self.load_gain, self.response_alpha, self.normal_residual_abs_max, self.elevated_residual_abs_max,
        )):
            raise ThermalTwinError("ThermalTwinConfig values must be finite")


def _validate_inputs(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_INPUT_COLUMNS if column not in frame]
    if missing:
        raise ThermalTwinError(f"Thermal twin input is missing required columns: {missing}")
    if not is_datetime64_any_dtype(frame["timestamp"]):
        raise ThermalTwinError("Thermal twin timestamp must have a pandas datetime dtype")
    if getattr(frame["timestamp"].dt, "tz", None) is not None:
        raise ThermalTwinError("Thermal twin timestamp must be timezone-naive")
    if frame["timestamp"].isna().any():
        raise ThermalTwinError("Thermal twin input contains invalid timestamps")
    if frame["transformer_id"].isna().any() or (frame["transformer_id"].astype(str).str.strip() == "").any():
        raise ThermalTwinError("Thermal twin input requires a populated transformer_id")
    if frame.duplicated(["transformer_id", "timestamp"]).any():
        raise ThermalTwinError("Thermal twin input contains duplicate transformer_id/timestamp pairs")


def _state_from_residual(residual: float, config: ThermalTwinConfig) -> str:
    magnitude = abs(residual)
    if magnitude <= config.normal_residual_abs_max:
        return "NORMAL"
    if magnitude <= config.elevated_residual_abs_max:
        return "ELEVATED"
    return "CRITICAL"


def _run_asset_baseline(asset: pd.DataFrame, config: ThermalTwinConfig) -> pd.DataFrame:
    """Run one chronological asset state recurrence without looking ahead."""
    output = pd.DataFrame(index=asset.index, columns=THERMAL_OUTPUT_COLUMNS)
    previous_model: float | None = None
    previous_timestamp: pd.Timestamp | None = None
    reference_interval_seconds: float | None = None
    for index, row in asset.iterrows():
        observed = row["oil_temperature"]
        ambient = row["ambient_temperature"]
        load = row["active_power_demand"]
        if pd.isna(ambient) or pd.isna(load):
            continue
        equilibrium = float(ambient + config.load_gain * load)
        if previous_model is None:
            # Initialising from the first observed thermal state avoids inventing
            # an unverified initial temperature or transformer constant.
            if pd.isna(observed):
                continue
            model = float(observed)
        else:
            elapsed_seconds = (row["timestamp"] - previous_timestamp).total_seconds()
            if elapsed_seconds <= 0:
                raise ThermalTwinError("Thermal twin timestamps must increase within each transformer")
            if reference_interval_seconds is None:
                reference_interval_seconds = elapsed_seconds
            elapsed_response = 1 - (
                1 - config.response_alpha
            ) ** (elapsed_seconds / reference_interval_seconds)
            model = previous_model + elapsed_response * (equilibrium - previous_model)
        previous_model = model
        previous_timestamp = row["timestamp"]
        output.loc[index, "thermal_model_temperature"] = model
        if not pd.isna(observed):
            residual = float(observed - model)
            output.loc[index, "thermal_residual"] = residual
            output.loc[index, "thermal_state"] = _state_from_residual(residual, config)
    return output


def run_thermal_twin(features: pd.DataFrame, config: ThermalTwinConfig) -> pd.DataFrame:
    """Add causal thermal-twin outputs while preserving input row order.

    ``active_power_demand`` is the available canonical-derived loading signal;
    no ``loading_percent`` is fabricated without a configured nameplate rating.
    Missing canonical readings remain missing in the thermal output.  The model
    is dynamic because each estimate evolves from its previous estimate toward
    the current ambient-plus-load equilibrium.
    """
    result = features.copy()
    if not is_datetime64_any_dtype(result.get("timestamp")):
        result["timestamp"] = pd.to_datetime(result.get("timestamp"), errors="coerce")
    _validate_inputs(result)
    ordered = result.sort_values(["transformer_id", "timestamp"], kind="stable")
    model_temperature = pd.Series(np.nan, index=result.index, dtype="float64")
    residual = pd.Series(np.nan, index=result.index, dtype="float64")
    state = pd.Series(pd.NA, index=result.index, dtype="string")
    for _, asset in ordered.groupby("transformer_id", sort=False):
        output = _run_asset_baseline(asset, config)
        model_temperature.loc[asset.index] = pd.to_numeric(output["thermal_model_temperature"], errors="coerce")
        residual.loc[asset.index] = pd.to_numeric(output["thermal_residual"], errors="coerce")
        state.loc[asset.index] = output["thermal_state"].astype("string")
    result["thermal_model_temperature"] = model_temperature
    result["thermal_residual"] = residual
    result["thermal_state"] = state
    base_columns = [column for column in features.columns if column not in THERMAL_OUTPUT_COLUMNS]
    return result.loc[:, [*base_columns, *THERMAL_OUTPUT_COLUMNS]]
