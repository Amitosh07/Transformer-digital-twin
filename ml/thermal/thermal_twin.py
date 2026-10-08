"""A causal, interpretable dynamic thermal baseline.

Phase 01 — Thermal Twin Finalization:
- First-order oil-indicator baseline with continuous-time exponential dynamics
  using physical hours (exp(-dt / tau)), completely independent of the first
  observed interval or batch length.
- Heating forcing driven by three-phase current-squared J_t = (I1^2 + I2^2 + I3^2)/3.
- Equilibrium: T_inf = b0 + bA * A + bJ * J.
- Previous-forcing hold u_(t-1) integrated across valid elapsed interval:
  T_hat_t = u_(t-1) + (T_hat_(t-1) - u_(t-1)) * exp(-dt / tau).
- Pure causal sequencing: current oil observation is NOT assimilated before
  scoring its own residual; r_t = T_t - T_hat_t (signed).
- Persistent state management across batches/streaming calls with warm-up tracking
  (t_warm >= -tau * ln(eps) ~ 3*tau for eps=0.05).
- Gap/reset behavior: gaps > continuity limit (30 min) or invalid elapsed time
  reset state and trigger warm-up suppression.
- Distinct model modes: PUBLIC_EMPIRICAL, VERIFIED_UNIT_EMPIRICAL, and
  STANDARDS_INSPIRED_ELIGIBLE.
- Explicit readiness status: INITIALIZING, WARMING_UP, READY, GAP_RESET,
  INSUFFICIENT_FORCING.
- Strict rejection of non-finite inputs and preservation of unknown units.
- WTI is never used as continuous temperature input.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Final, Mapping

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype


THERMAL_OUTPUT_COLUMNS: Final = (
    "thermal_model_temperature",
    "thermal_residual",
    "thermal_state",
)

# Metadata columns added for explicit contract/readiness reporting
THERMAL_METADATA_COLUMNS: Final = (
    "thermal_readiness",
    "thermal_model_mode",
    "thermal_temperature_unit",
)

ALL_THERMAL_COLUMNS: Final = (*THERMAL_OUTPUT_COLUMNS, *THERMAL_METADATA_COLUMNS)

REQUIRED_INPUT_COLUMNS: Final = (
    "transformer_id",
    "timestamp",
    "oil_temperature",
    "ambient_temperature",
)

# Current inputs required for J forcing calculation (if J is not pre-computed)
CURRENT_COLUMNS: Final = ("current_l1", "current_l2", "current_l3")

# Default heuristic parameters from Phase 01 spec
DEFAULT_CONTINUITY_GAP_HOURS: Final = 0.5  # 30 minutes
DEFAULT_WARMUP_EPSILON: Final = 0.05      # ~3*tau
DEFAULT_PARAMETER_VERSION: Final = "1.0.0"


class ThermalModelMode(str, enum.Enum):
    """Documented operational modes for the thermal model."""
    PUBLIC_EMPIRICAL = "PUBLIC_EMPIRICAL"
    VERIFIED_UNIT_EMPIRICAL = "VERIFIED_UNIT_EMPIRICAL"
    STANDARDS_INSPIRED_ELIGIBLE = "STANDARDS_INSPIRED_ELIGIBLE"


class ThermalReadinessStatus(str, enum.Enum):
    """Status indicating model validity, warm-up state, or reason for suppression."""
    INITIALIZING = "INITIALIZING"
    WARMING_UP = "WARMING_UP"
    READY = "READY"
    GAP_RESET = "GAP_RESET"
    INSUFFICIENT_FORCING = "INSUFFICIENT_FORCING"
    UNINITIALIZED = "UNINITIALIZED"


class ThermalTwinError(ValueError):
    """Raised when thermal-twin inputs, state, or configuration are invalid."""


@dataclass(frozen=True)
class ThermalTwinConfig:
    """Explicit parameters and operational mode for the first-order thermal baseline.

    Equations:
        J_t = (I1^2 + I2^2 + I3^2) / 3
        T_inf,t = b0 + bA * A_t + bJ * J_t
        T_hat_t = u_(t-1) + (T_hat_(t-1) - u_(t-1)) * exp(-dt / tau)
        r_t = T_t - T_hat_t

    Constraints:
        bA >= 0, bJ >= 0, tau > 0 (tau in hours).
    """

    b0: float = -2.1073
    bA: float = 1.1284
    bJ: float = 8.065e-5
    tau_hours: float = 0.240  # hours (~14.4 minutes)

    mode: ThermalModelMode = ThermalModelMode.PUBLIC_EMPIRICAL
    temperature_unit: str = "SOURCE_UNVERIFIED"

    continuity_gap_hours: float = DEFAULT_CONTINUITY_GAP_HOURS
    warmup_epsilon: float = DEFAULT_WARMUP_EPSILON
    parameter_version: str = DEFAULT_PARAMETER_VERSION

    # Optional verified physical limits for thermal_state assessment.
    # Phase 02 owns learned statistical severity; here we only assess verified limits.
    # None means thermal_state remains null/unassessed.
    verified_warning_temperature: float | None = None
    verified_critical_temperature: float | None = None

    def __post_init__(self) -> None:
        if self.tau_hours <= 0:
            raise ThermalTwinError("tau_hours must be strictly positive")
        if self.bA < 0:
            raise ThermalTwinError("bA must be non-negative")
        if self.bJ < 0:
            raise ThermalTwinError("bJ must be non-negative")
        if self.continuity_gap_hours <= 0:
            raise ThermalTwinError("continuity_gap_hours must be strictly positive")
        if not (0 < self.warmup_epsilon < 1):
            raise ThermalTwinError("warmup_epsilon must be strictly between 0 and 1")
        for val in (self.b0, self.bA, self.bJ, self.tau_hours, self.continuity_gap_hours, self.warmup_epsilon):
            if not np.isfinite(val):
                raise ThermalTwinError("All numeric parameters must be finite")

    @property
    def warmup_duration_hours(self) -> float:
        """Required continuous valid history duration to exit warm-up."""
        return -self.tau_hours * np.log(self.warmup_epsilon)

    def to_dict(self) -> dict[str, Any]:
        return {
            "b0": self.b0,
            "bA": self.bA,
            "bJ": self.bJ,
            "tau_hours": self.tau_hours,
            "mode": self.mode.value,
            "temperature_unit": self.temperature_unit,
            "continuity_gap_hours": self.continuity_gap_hours,
            "warmup_epsilon": self.warmup_epsilon,
            "parameter_version": self.parameter_version,
            "warmup_duration_hours": self.warmup_duration_hours,
            "verified_warning_temperature": self.verified_warning_temperature,
            "verified_critical_temperature": self.verified_critical_temperature,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ThermalTwinConfig:
        return cls(
            b0=float(data["b0"]),
            bA=float(data["bA"]),
            bJ=float(data["bJ"]),
            tau_hours=float(data["tau_hours"]),
            mode=ThermalModelMode(data.get("mode", ThermalModelMode.PUBLIC_EMPIRICAL.value)),
            temperature_unit=str(data.get("temperature_unit", "SOURCE_UNVERIFIED")),
            continuity_gap_hours=float(data.get("continuity_gap_hours", DEFAULT_CONTINUITY_GAP_HOURS)),
            warmup_epsilon=float(data.get("warmup_epsilon", DEFAULT_WARMUP_EPSILON)),
            parameter_version=str(data.get("parameter_version", DEFAULT_PARAMETER_VERSION)),
            verified_warning_temperature=data.get("verified_warning_temperature"),
            verified_critical_temperature=data.get("verified_critical_temperature"),
        )


@dataclass
class TransformerThermalState:
    """Persistent state tracked across observations for a single transformer.

    Enables stateful continuous integration across batches and streaming calls.
    """

    transformer_id: str
    last_timestamp: pd.Timestamp | None = None
    last_model_temperature: float | None = None
    last_forcing: float | None = None
    warmup_elapsed_hours: float = 0.0
    is_initialized: bool = False
    parameter_version: str = DEFAULT_PARAMETER_VERSION

    def reset(self) -> None:
        """Reset state upon long gap or corruption."""
        self.last_timestamp = None
        self.last_model_temperature = None
        self.last_forcing = None
        self.warmup_elapsed_hours = 0.0
        self.is_initialized = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "transformer_id": self.transformer_id,
            "last_timestamp": self.last_timestamp.isoformat() if self.last_timestamp is not None else None,
            "last_model_temperature": self.last_model_temperature,
            "last_forcing": self.last_forcing,
            "warmup_elapsed_hours": self.warmup_elapsed_hours,
            "is_initialized": self.is_initialized,
            "parameter_version": self.parameter_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TransformerThermalState:
        ts_val = data.get("last_timestamp")
        return cls(
            transformer_id=str(data["transformer_id"]),
            last_timestamp=pd.to_datetime(ts_val) if ts_val is not None else None,
            last_model_temperature=data.get("last_model_temperature"),
            last_forcing=data.get("last_forcing"),
            warmup_elapsed_hours=float(data.get("warmup_elapsed_hours", 0.0)),
            is_initialized=bool(data.get("is_initialized", False)),
            parameter_version=str(data.get("parameter_version", DEFAULT_PARAMETER_VERSION)),
        )


def compute_current_forcing(frame: pd.DataFrame) -> pd.Series:
    """Calculate current-squared heating driver J_t = (I1^2 + I2^2 + I3^2) / 3.

    Requires all three phases to be valid. Returns NaN if any phase is missing or non-finite.
    """
    if "J" in frame.columns:
        return pd.to_numeric(frame["J"], errors="coerce")

    missing = [c for c in CURRENT_COLUMNS if c not in frame.columns]
    if missing:
        # Fallback to active_power_demand if current is unavailable
        if "active_power_demand" in frame.columns:
            return pd.to_numeric(frame["active_power_demand"], errors="coerce")
        return pd.Series(np.nan, index=frame.index, dtype="float64")

    c1 = pd.to_numeric(frame["current_l1"], errors="coerce")
    c2 = pd.to_numeric(frame["current_l2"], errors="coerce")
    c3 = pd.to_numeric(frame["current_l3"], errors="coerce")

    valid = c1.notna() & c2.notna() & c3.notna()
    j = (c1.pow(2) + c2.pow(2) + c3.pow(2)) / 3.0
    j[~valid] = np.nan
    return j


def _validate_inputs(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_INPUT_COLUMNS if column not in frame]
    if missing:
        raise ThermalTwinError(f"Thermal twin input is missing required columns: {missing}")
    if not is_datetime64_any_dtype(frame["timestamp"]):
        raise ThermalTwinError("Thermal twin timestamp must have a pandas datetime dtype")
    if frame["timestamp"].isna().any():
        raise ThermalTwinError("Thermal twin input contains invalid or missing timestamps")
    if frame["transformer_id"].isna().any() or (frame["transformer_id"].astype(str).str.strip() == "").any():
        raise ThermalTwinError("Thermal twin input requires a populated transformer_id")
    if frame.duplicated(["transformer_id", "timestamp"]).any():
        raise ThermalTwinError("Thermal twin input contains duplicate transformer_id/timestamp pairs")


def _assess_thermal_state(
    observed_temp: float,
    config: ThermalTwinConfig,
) -> str | None:
    """Assess thermal state according to verified physical limits.

    Phase 01 rule: Do not invent residual cutoffs.
    If verified physical limits are configured, assess them; otherwise return None.
    """
    if np.isnan(observed_temp):
        return None
    if config.verified_critical_temperature is not None and observed_temp >= config.verified_critical_temperature:
        return "CRITICAL"
    if config.verified_warning_temperature is not None and observed_temp >= config.verified_warning_temperature:
        return "ELEVATED"
    if config.verified_warning_temperature is not None:
        return "NORMAL"
    return None


class ThermalTwin:
    """Stateful, causal thermal twin orchestrator.

    Maintains per-transformer state across sequential calls or processes full datasets.
    """

    def __init__(self, config: ThermalTwinConfig | None = None) -> None:
        self.config = config or ThermalTwinConfig()
        self._states: dict[str, TransformerThermalState] = {}

    def get_state(self, transformer_id: str) -> TransformerThermalState:
        if transformer_id not in self._states:
            self._states[transformer_id] = TransformerThermalState(transformer_id=transformer_id)
        return self._states[transformer_id]

    def set_state(self, state: TransformerThermalState) -> None:
        self._states[state.transformer_id] = state

    def reset_state(self, transformer_id: str | None = None) -> None:
        if transformer_id is not None:
            if transformer_id in self._states:
                self._states[transformer_id].reset()
        else:
            self._states.clear()

    def process_asset(
        self,
        asset_df: pd.DataFrame,
        state: TransformerThermalState,
    ) -> pd.DataFrame:
        """Process one transformer's chronological telemetry sequence updating state."""
        n = len(asset_df)
        model_temp = np.full(n, np.nan, dtype="float64")
        residuals = np.full(n, np.nan, dtype="float64")
        states = [None] * n
        readiness = [ThermalReadinessStatus.UNINITIALIZED.value] * n

        T_obs = pd.to_numeric(asset_df["oil_temperature"], errors="coerce").to_numpy()
        A_obs = pd.to_numeric(asset_df["ambient_temperature"], errors="coerce").to_numpy()
        J_obs = compute_current_forcing(asset_df).to_numpy()
        timestamps = asset_df["timestamp"].to_numpy()

        warmup_required = self.config.warmup_duration_hours

        for i in range(n):
            cur_ts = pd.Timestamp(timestamps[i])
            cur_T = T_obs[i]
            cur_A = A_obs[i]
            cur_J = J_obs[i]

            # Non-finite check on inputs
            if np.isinf(cur_T) or np.isinf(cur_A) or np.isinf(cur_J):
                raise ThermalTwinError(f"Non-finite input encountered at timestamp {cur_ts}")

            # Calculate current equilibrium forcing if current A and J are valid
            has_cur_forcing = not np.isnan(cur_A) and not np.isnan(cur_J)
            cur_forcing = (
                float(self.config.b0 + self.config.bA * cur_A + self.config.bJ * cur_J)
                if has_cur_forcing else None
            )

            # Check if this is the start of tracking or elapsed time
            if state.last_timestamp is None:
                # Cold start: need valid observed T and valid forcing to initialize
                if not np.isnan(cur_T) and has_cur_forcing:
                    state.last_model_temperature = float(cur_T)
                    state.last_forcing = cur_forcing
                    state.last_timestamp = cur_ts
                    state.warmup_elapsed_hours = 0.0
                    state.is_initialized = True

                    model_temp[i] = float(cur_T)
                    # Residual is suppressed at initialization
                    readiness[i] = ThermalReadinessStatus.INITIALIZING.value
                else:
                    readiness[i] = ThermalReadinessStatus.INSUFFICIENT_FORCING.value
                continue

            # Calculate elapsed time in hours
            dt_hours = (cur_ts - state.last_timestamp).total_seconds() / 3600.0

            if dt_hours <= 0:
                raise ThermalTwinError(
                    f"Timestamps must strictly increase within each transformer. "
                    f"Prior: {state.last_timestamp}, Current: {cur_ts}"
                )

            # Gap check: if dt > continuity limit, trigger gap reset
            if dt_hours > self.config.continuity_gap_hours:
                state.reset()
                # Re-initialize on this record if valid
                if not np.isnan(cur_T) and has_cur_forcing:
                    state.last_model_temperature = float(cur_T)
                    state.last_forcing = cur_forcing
                    state.last_timestamp = cur_ts
                    state.warmup_elapsed_hours = 0.0
                    state.is_initialized = True

                    model_temp[i] = float(cur_T)
                    readiness[i] = ThermalReadinessStatus.GAP_RESET.value
                else:
                    readiness[i] = ThermalReadinessStatus.GAP_RESET.value
                continue

            # Valid contiguous interval: integrate previous forcing over dt
            u_prev = state.last_forcing
            T_prev = state.last_model_temperature

            if u_prev is None or T_prev is None:
                # Previous forcing was missing; cannot integrate
                state.reset()
                readiness[i] = ThermalReadinessStatus.INSUFFICIENT_FORCING.value
                continue

            # Exact analytical first-order integration under constant previous forcing
            decay = np.exp(-dt_hours / self.config.tau_hours)
            T_hat = float(u_prev + (T_prev - u_prev) * decay)
            model_temp[i] = T_hat

            # Accumulate warm-up time
            state.warmup_elapsed_hours += dt_hours

            # Evaluate readiness
            is_ready = state.warmup_elapsed_hours >= warmup_required

            # Causal residual: current oil T is compared ONLY AFTER T_hat is generated
            if is_ready:
                readiness[i] = ThermalReadinessStatus.READY.value
                if not np.isnan(cur_T):
                    residuals[i] = float(cur_T - T_hat)
            else:
                readiness[i] = ThermalReadinessStatus.WARMING_UP.value

            # Thermal state assessment (if verified limits configured)
            if not np.isnan(cur_T):
                states[i] = _assess_thermal_state(float(cur_T), self.config)

            # State update for the NEXT step
            state.last_model_temperature = T_hat
            state.last_timestamp = cur_ts
            if has_cur_forcing:
                state.last_forcing = cur_forcing
            else:
                state.last_forcing = None

        out_df = pd.DataFrame(index=asset_df.index)
        out_df["thermal_model_temperature"] = model_temp
        out_df["thermal_residual"] = residuals
        out_df["thermal_state"] = pd.Series(states, index=asset_df.index, dtype="string")
        out_df["thermal_readiness"] = pd.Series(readiness, index=asset_df.index, dtype="string")
        out_df["thermal_model_mode"] = self.config.mode.value
        out_df["thermal_temperature_unit"] = self.config.temperature_unit

        return out_df

    def run(self, features: pd.DataFrame) -> pd.DataFrame:
        """Run thermal twin on canonical telemetry or features, preserving caller order."""
        result = features.copy()
        if not is_datetime64_any_dtype(result.get("timestamp")):
            result["timestamp"] = pd.to_datetime(result.get("timestamp"), errors="coerce")
        _validate_inputs(result)

        original_index = features.index
        # Internal unique integer indexing to handle permuted or duplicate index labels
        temp_df = result.reset_index(drop=True)
        ordered = temp_df.sort_values(["transformer_id", "timestamp"], kind="stable")

        out_pieces = []
        for transformer_id, asset_df in ordered.groupby("transformer_id", sort=False):
            state = self.get_state(str(transformer_id))
            processed = self.process_asset(asset_df, state)
            out_pieces.append(processed)

        all_processed = pd.concat(out_pieces, axis=0).sort_index()

        for col in ALL_THERMAL_COLUMNS:
            temp_df[col] = all_processed[col]

        temp_df.index = original_index
        base_columns = [c for c in features.columns if c not in ALL_THERMAL_COLUMNS]
        return temp_df.loc[:, [*base_columns, *ALL_THERMAL_COLUMNS]]


def run_thermal_twin(
    features: pd.DataFrame,
    config: ThermalTwinConfig | None = None,
) -> pd.DataFrame:
    """Functional interface matching existing repository convention."""
    twin = ThermalTwin(config=config)
    return twin.run(features)
