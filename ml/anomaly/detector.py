"""Hybrid statistical and engineering anomaly detector for transformer digital twin.

Phase 02 — Anomaly Detection:
- Explainable anomaly_score in [0, 1] or null.
- anomaly_flag as Boolean or null based on validation-selected threshold a_on
  and elapsed-time persistence (3 valid observations spanning >= 30 min, gap <= 30 min).
- Grouped evidence families: thermal (s_T), electrical (s_E), loading (s_L),
  oil (s_O), and protection (s_protection).
- Directional signal severity formulas:
    Upper tail: s_j(x) = clip((x - W_j) / (C_j - W_j), 0, 1)
    Lower tail: s_j(x) = clip((W_j - x) / (W_j - C_j), 0, 1)
- Positive thermal residual contributes to s_T. Negative residual produces
  THERMAL_MODEL_MISMATCH (model/condition mismatch, not overheating).
- Protection override: active verified protection contacts (oil alarm, trip, MOG)
  set s_protection = 1.0 and trigger immediately, bypassing statistical persistence.
- Complete reason code diagnostics with triggering signal value, threshold, and unit.
- Explicit coverage tracking: missing signals do not become 0 or normal.
- All-missing inputs produce null score and null flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Final, Mapping

import numpy as np
import pandas as pd


ANOMALY_OUTPUT_COLUMNS: Final = (
    "anomaly_score",
    "anomaly_flag",
    "reason_codes",
)

ANOMALY_FAMILY_SEVERITY_COLUMNS: Final = (
    "severity_thermal",
    "severity_electrical",
    "severity_loading",
    "severity_oil",
    "severity_protection",
)

ANOMALY_COVERAGE_COLUMNS: Final = (
    "coverage_thermal",
    "coverage_electrical",
    "coverage_loading",
    "coverage_oil",
    "coverage_overall",
)

ALL_ANOMALY_COLUMNS: Final = (
    *ANOMALY_OUTPUT_COLUMNS,
    *ANOMALY_FAMILY_SEVERITY_COLUMNS,
    *ANOMALY_COVERAGE_COLUMNS,
)

# Standard reason codes specified in Phase 02
REASON_HIGH_OIL_TEMP: Final = "HIGH_OIL_TEMP"
REASON_RAPID_TEMP_RISE: Final = "RAPID_TEMP_RISE"
REASON_CURRENT_IMBALANCE: Final = "CURRENT_IMBALANCE"
REASON_VOLTAGE_IMBALANCE: Final = "VOLTAGE_IMBALANCE"
REASON_HIGH_LOADING: Final = "HIGH_LOADING"
REASON_OVERLOAD: Final = "OVERLOAD"
REASON_THERMAL_RESIDUAL_HIGH: Final = "THERMAL_RESIDUAL_HIGH"
REASON_THERMAL_MODEL_MISMATCH: Final = "THERMAL_MODEL_MISMATCH"
REASON_LOW_OIL_LEVEL: Final = "LOW_OIL_LEVEL"
REASON_OIL_LEVEL_DECREASING: Final = "OIL_LEVEL_DECREASING"
REASON_OIL_TEMP_ALARM: Final = "OIL_TEMP_ALARM"
REASON_OIL_TEMP_TRIP: Final = "OIL_TEMP_TRIP"
REASON_MOG_ALARM: Final = "MOG_ALARM"
REASON_ANOMALOUS_PATTERN: Final = "ANOMALOUS_PATTERN"
REASON_DATA_QUALITY_ISSUE: Final = "DATA_QUALITY_ISSUE"
REASON_RATING_UNAVAILABLE: Final = "RATING_UNAVAILABLE"

# Default heuristic persistence constants from Phase 02 spec
DEFAULT_PERSISTENCE_MIN_OBSERVATIONS: Final = 3
DEFAULT_PERSISTENCE_MIN_SPAN_HOURS: Final = 0.5  # 30 minutes
DEFAULT_CONTINUITY_GAP_HOURS: Final = 0.5        # 30 minutes
DEFAULT_MIN_CURRENT_GATE: Final = 5.0            # Amperes, minimum mean current to evaluate imbalance


class AnomalyDetectorError(ValueError):
    """Raised when anomaly detector configuration or state is invalid."""


@dataclass(frozen=True)
class SignalThreshold:
    """Directional reference thresholds for a single signal."""
    signal_name: str
    warning_threshold: float  # W
    critical_threshold: float # C
    direction: str            # 'upper' or 'lower'
    unit: str
    provenance: str = "TRAIN_REFERENCE_QUANTILE"

    def __post_init__(self) -> None:
        if self.direction not in ("upper", "lower"):
            raise AnomalyDetectorError(f"Direction must be 'upper' or 'lower', got: {self.direction}")
        if self.direction == "upper" and self.critical_threshold <= self.warning_threshold:
            raise AnomalyDetectorError(
                f"Upper tail requires C > W, got W={self.warning_threshold}, C={self.critical_threshold}"
            )
        if self.direction == "lower" and self.warning_threshold <= self.critical_threshold:
            raise AnomalyDetectorError(
                f"Lower tail requires W > C, got W={self.warning_threshold}, C={self.critical_threshold}"
            )
        for val in (self.warning_threshold, self.critical_threshold):
            if not np.isfinite(val):
                raise AnomalyDetectorError(f"Thresholds must be finite, got {val}")

    def score(self, value: float) -> float:
        """Compute severity s in [0, 1]."""
        if pd.isna(value) or not np.isfinite(value):
            return np.nan
        if self.direction == "upper":
            # s = clip((x - W) / (C - W), 0, 1)
            raw = (value - self.warning_threshold) / (self.critical_threshold - self.warning_threshold)
        else:
            # s = clip((W - x) / (W - C), 0, 1)
            raw = (self.warning_threshold - value) / (self.warning_threshold - self.critical_threshold)
        return float(np.clip(raw, 0.0, 1.0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_name": self.signal_name,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "direction": self.direction,
            "unit": self.unit,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SignalThreshold:
        return cls(
            signal_name=str(data["signal_name"]),
            warning_threshold=float(data["warning_threshold"]),
            critical_threshold=float(data["critical_threshold"]),
            direction=str(data["direction"]),
            unit=str(data["unit"]),
            provenance=str(data.get("provenance", "TRAIN_REFERENCE_QUANTILE")),
        )


@dataclass(frozen=True)
class AnomalyDetectorConfig:
    """Configuration for the Phase 02 hybrid statistical/engineering anomaly detector."""
    thresholds: dict[str, SignalThreshold] = field(default_factory=dict)
    a_on: float = 0.5
    min_persistence_observations: int = DEFAULT_PERSISTENCE_MIN_OBSERVATIONS
    min_persistence_span_hours: float = DEFAULT_PERSISTENCE_MIN_SPAN_HOURS
    continuity_gap_hours: float = DEFAULT_CONTINUITY_GAP_HOURS
    min_current_gate_a: float = DEFAULT_MIN_CURRENT_GATE
    detector_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not (0.0 <= self.a_on <= 1.0):
            raise AnomalyDetectorError(f"a_on must be between 0.0 and 1.0, got: {self.a_on}")
        if self.min_persistence_observations < 1:
            raise AnomalyDetectorError("min_persistence_observations must be >= 1")
        if self.min_persistence_span_hours < 0:
            raise AnomalyDetectorError("min_persistence_span_hours must be non-negative")
        if self.continuity_gap_hours <= 0:
            raise AnomalyDetectorError("continuity_gap_hours must be strictly positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "a_on": self.a_on,
            "min_persistence_observations": self.min_persistence_observations,
            "min_persistence_span_hours": self.min_persistence_span_hours,
            "continuity_gap_hours": self.continuity_gap_hours,
            "min_current_gate_a": self.min_current_gate_a,
            "detector_version": self.detector_version,
            "thresholds": {k: v.to_dict() for k, v in self.thresholds.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AnomalyDetectorConfig:
        thresholds = {
            k: SignalThreshold.from_dict(v) for k, v in data.get("thresholds", {}).items()
        }
        return cls(
            thresholds=thresholds,
            a_on=float(data.get("a_on", 0.5)),
            min_persistence_observations=int(data.get("min_persistence_observations", DEFAULT_PERSISTENCE_MIN_OBSERVATIONS)),
            min_persistence_span_hours=float(data.get("min_persistence_span_hours", DEFAULT_PERSISTENCE_MIN_SPAN_HOURS)),
            continuity_gap_hours=float(data.get("continuity_gap_hours", DEFAULT_CONTINUITY_GAP_HOURS)),
            min_current_gate_a=float(data.get("min_current_gate_a", DEFAULT_MIN_CURRENT_GATE)),
            detector_version=str(data.get("detector_version", "1.0.0")),
        )


@dataclass
class AnomalyPersistenceState:
    """Stateful tracking of candidate alert episodes across consecutive observations."""
    transformer_id: str
    in_alert: bool = False
    consecutive_high_timestamps: list[pd.Timestamp] = field(default_factory=list)
    consecutive_low_timestamps: list[pd.Timestamp] = field(default_factory=list)
    last_timestamp: pd.Timestamp | None = None
    episode_count: int = 0

    def reset(self) -> None:
        self.in_alert = False
        self.consecutive_high_timestamps.clear()
        self.consecutive_low_timestamps.clear()
        self.last_timestamp = None


def get_default_training_thresholds() -> dict[str, SignalThreshold]:
    """Default statistical reference thresholds derived from train partition reference segments."""
    return {
        "current_imbalance_pct": SignalThreshold(
            signal_name="current_imbalance_pct",
            warning_threshold=72.9802,
            critical_threshold=300.0,
            direction="upper",
            unit="percent",
            provenance="TRAIN_REF_Q95_Q995",
        ),
        "voltage_imbalance_pct": SignalThreshold(
            signal_name="voltage_imbalance_pct",
            warning_threshold=1.7494,
            critical_threshold=2.5694,
            direction="upper",
            unit="percent",
            provenance="TRAIN_REF_Q95_Q995",
        ),
        "neutral_current_magnitude": SignalThreshold(
            signal_name="neutral_current_magnitude",
            warning_threshold=51.4000,
            critical_threshold=71.0800,
            direction="upper",
            unit="A",
            provenance="TRAIN_REF_Q95_Q995",
        ),
        "apparent_power_total": SignalThreshold(
            signal_name="apparent_power_total",
            warning_threshold=101.5068,
            critical_threshold=118.0200,
            direction="upper",
            unit="kVA",
            provenance="TRAIN_REF_Q95_Q995",
        ),
        "power_factor_deviation": SignalThreshold(
            signal_name="power_factor_deviation",
            warning_threshold=0.0400,
            critical_threshold=0.0533,
            direction="upper",
            unit="dimensionless",
            provenance="TRAIN_REF_Q95_Q995",
        ),
        "oil_temperature": SignalThreshold(
            signal_name="oil_temperature",
            warning_threshold=40.0000,
            critical_threshold=48.0000,
            direction="upper",
            unit="source_unit",
            provenance="TRAIN_REF_Q95_Q995",
        ),
        "oil_temperature_rate": SignalThreshold(
            signal_name="oil_temperature_rate",
            warning_threshold=8.0000,
            critical_threshold=20.0000,
            direction="upper",
            unit="source_unit_per_hour",
            provenance="TRAIN_REF_Q95_Q995",
        ),
        "temperature_rolling_std": SignalThreshold(
            signal_name="temperature_rolling_std",
            warning_threshold=2.0817,
            critical_threshold=14.5000,
            direction="upper",
            unit="source_unit",
            provenance="TRAIN_REF_Q95_Q995",
        ),
        "thermal_residual": SignalThreshold(
            signal_name="thermal_residual",
            warning_threshold=4.4558,
            critical_threshold=8.0647,
            direction="upper",
            unit="source_unit",
            provenance="TRAIN_REF_Q95_Q995",
        ),
        "oil_level_deviation": SignalThreshold(
            signal_name="oil_level_deviation",
            warning_threshold=-2.7500,
            critical_threshold=-12.7500,
            direction="lower",
            unit="source_unit",
            provenance="TRAIN_REF_Q05_Q005",
        ),
    }


class AnomalyDetector:
    """Stateful, explainable hybrid anomaly detector."""

    def __init__(self, config: AnomalyDetectorConfig | None = None) -> None:
        if config is None:
            self.config = AnomalyDetectorConfig(thresholds=get_default_training_thresholds())
        else:
            self.config = config
        self._states: dict[str, AnomalyPersistenceState] = {}

    def get_state(self, transformer_id: str) -> AnomalyPersistenceState:
        if transformer_id not in self._states:
            self._states[transformer_id] = AnomalyPersistenceState(transformer_id=transformer_id)
        return self._states[transformer_id]

    def reset_state(self, transformer_id: str | None = None) -> None:
        if transformer_id is not None:
            if transformer_id in self._states:
                self._states[transformer_id].reset()
        else:
            self._states.clear()

    def _score_signal(self, signal_name: str, value: float) -> float:
        if signal_name not in self.config.thresholds:
            return np.nan
        return self.config.thresholds[signal_name].score(value)

    def process_record(
        self,
        row: Mapping[str, Any],
        state: AnomalyPersistenceState,
    ) -> dict[str, Any]:
        """Process a single record evaluating severities, protection, persistence, and reasons."""
        timestamp = pd.Timestamp(row["timestamp"])
        reasons: list[str] = []

        # Elapsed time from previous record
        dt_hours: float | None = None
        if state.last_timestamp is not None:
            dt_hours = (timestamp - state.last_timestamp).total_seconds() / 3600.0
            if dt_hours <= 0:
                raise AnomalyDetectorError(f"Timestamps must strictly increase. Prev: {state.last_timestamp}, Cur: {timestamp}")

        # Gap reset check
        if dt_hours is not None and dt_hours > self.config.continuity_gap_hours:
            # Long gap resets persistence buffers
            state.consecutive_high_timestamps.clear()
            state.consecutive_low_timestamps.clear()

        # ---------------------------------------------------------
        # 1. Protection Evidence (Verified active contacts)
        # ---------------------------------------------------------
        s_protection: float | None = None
        oil_alarm = row.get("oil_temp_alarm")
        oil_trip = row.get("oil_temp_trip")
        mog_alarm = row.get("magnetic_oil_gauge_alarm")

        prot_active = False
        has_prot_evidence = False

        if not pd.isna(oil_trip) and oil_trip == 1:
            reasons.append(REASON_OIL_TEMP_TRIP)
            prot_active = True
            has_prot_evidence = True
        elif not pd.isna(oil_trip):
            has_prot_evidence = True

        if not pd.isna(oil_alarm) and oil_alarm == 1:
            reasons.append(REASON_OIL_TEMP_ALARM)
            prot_active = True
            has_prot_evidence = True
        elif not pd.isna(oil_alarm):
            has_prot_evidence = True

        if not pd.isna(mog_alarm) and mog_alarm == 1:
            reasons.append(REASON_MOG_ALARM)
            prot_active = True
            has_prot_evidence = True
        elif not pd.isna(mog_alarm):
            has_prot_evidence = True

        if prot_active:
            s_protection = 1.0
        elif has_prot_evidence:
            s_protection = 0.0

        # ---------------------------------------------------------
        # 2. Thermal Family Evidence
        # ---------------------------------------------------------
        s_T_terms: list[float] = []
        cov_T = 0
        tot_T = 3

        # (a) Oil temperature level
        oil_t = row.get("oil_temperature")
        if not pd.isna(oil_t) and np.isfinite(oil_t):
            s_temp = self._score_signal("oil_temperature", float(oil_t))
            if not np.isnan(s_temp):
                s_T_terms.append(s_temp)
                cov_T += 1
                if s_temp > 0:
                    reasons.append(REASON_HIGH_OIL_TEMP)

        # (b) Rate of rise
        oil_rate = row.get("oil_temperature_rate")
        if not pd.isna(oil_rate) and np.isfinite(oil_rate):
            s_rate = self._score_signal("oil_temperature_rate", float(oil_rate))
            if not np.isnan(s_rate):
                s_T_terms.append(s_rate)
                cov_T += 1
                if s_rate > 0:
                    reasons.append(REASON_RAPID_TEMP_RISE)

        # (c) Thermal residual (from Phase 01 twin)
        t_res = row.get("thermal_residual")
        t_ready = row.get("thermal_readiness")
        if t_ready == "READY" and not pd.isna(t_res) and np.isfinite(t_res):
            t_res_val = float(t_res)
            cov_T += 1
            if t_res_val > 0:
                s_res = self._score_signal("thermal_residual", t_res_val)
                if not np.isnan(s_res):
                    s_T_terms.append(s_res)
                    if s_res > 0:
                        reasons.append(REASON_THERMAL_RESIDUAL_HIGH)
            elif t_res_val < 0:
                # Negative residual is model/condition mismatch, NOT overheating!
                reasons.append(REASON_THERMAL_MODEL_MISMATCH)

        s_thermal = max(s_T_terms) if s_T_terms else np.nan
        coverage_thermal = cov_T / tot_T

        # ---------------------------------------------------------
        # 3. Electrical Family Evidence
        # ---------------------------------------------------------
        s_E_terms: list[float] = []
        cov_E = 0
        tot_E = 4

        # (a) Current spread / imbalance
        cur_imb = row.get("current_imbalance_pct")
        cur_mean = row.get("current_mean")
        # Low load gate: below configured gate, current imbalance is noise
        if not pd.isna(cur_imb) and np.isfinite(cur_imb):
            if cur_mean is None or pd.isna(cur_mean) or float(cur_mean) >= self.config.min_current_gate_a:
                s_cur = self._score_signal("current_imbalance_pct", float(cur_imb))
                if not np.isnan(s_cur):
                    s_E_terms.append(s_cur)
                    cov_E += 1
                    if s_cur > 0:
                        reasons.append(REASON_CURRENT_IMBALANCE)
            else:
                cov_E += 1  # evaluated but gated

        # (b) Voltage spread / imbalance
        volt_imb = row.get("voltage_imbalance_pct")
        if not pd.isna(volt_imb) and np.isfinite(volt_imb):
            s_volt = self._score_signal("voltage_imbalance_pct", float(volt_imb))
            if not np.isnan(s_volt):
                s_E_terms.append(s_volt)
                cov_E += 1
                if s_volt > 0:
                    reasons.append(REASON_VOLTAGE_IMBALANCE)

        # (c) Neutral current magnitude
        neut = row.get("neutral_current_magnitude")
        if not pd.isna(neut) and np.isfinite(neut):
            s_neut = self._score_signal("neutral_current_magnitude", float(neut))
            if not np.isnan(s_neut):
                s_E_terms.append(s_neut)
                cov_E += 1

        # (d) Power factor deviation
        pf_dev = row.get("power_factor_deviation")
        if not pd.isna(pf_dev) and np.isfinite(pf_dev):
            s_pf = self._score_signal("power_factor_deviation", float(pf_dev))
            if not np.isnan(s_pf):
                s_E_terms.append(s_pf)
                cov_E += 1

        s_electrical = max(s_E_terms) if s_E_terms else np.nan
        coverage_electrical = cov_E / tot_E

        # ---------------------------------------------------------
        # 4. Loading Family Evidence
        # ---------------------------------------------------------
        s_L_terms: list[float] = []
        cov_L = 0
        tot_L = 1

        s_total = row.get("apparent_power_total")
        if not pd.isna(s_total) and np.isfinite(s_total):
            s_load = self._score_signal("apparent_power_total", float(s_total))
            if not np.isnan(s_load):
                s_L_terms.append(s_load)
                cov_L += 1
                if s_load > 0:
                    reasons.append(REASON_HIGH_LOADING)

        # OVERLOAD requires verified rated power (apparent_power_utilization > 1.0)
        u_s = row.get("apparent_power_utilization")
        if u_s is not None and not pd.isna(u_s) and float(u_s) > 1.0:
            reasons.append(REASON_OVERLOAD)

        s_loading = max(s_L_terms) if s_L_terms else np.nan
        coverage_loading = cov_L / tot_L

        # ---------------------------------------------------------
        # 5. Oil Family Evidence
        # ---------------------------------------------------------
        s_O_terms: list[float] = []
        cov_O = 0
        tot_O = 1

        oil_dev = row.get("oil_level_deviation")
        if not pd.isna(oil_dev) and np.isfinite(oil_dev):
            s_oil = self._score_signal("oil_level_deviation", float(oil_dev))
            if not np.isnan(s_oil):
                s_O_terms.append(s_oil)
                cov_O += 1
                if s_oil > 0:
                    reasons.append(REASON_OIL_LEVEL_DECREASING)

        s_oil = max(s_O_terms) if s_O_terms else np.nan
        coverage_oil = cov_O / tot_O

        # ---------------------------------------------------------
        # Overall Anomaly Score a = max(s_T, s_E, s_L, s_O, s_prot)
        # ---------------------------------------------------------
        available_families = [x for x in [s_thermal, s_electrical, s_loading, s_oil] if not np.isnan(x)]
        if s_protection is not None:
            available_families.append(s_protection)

        if not available_families:
            # Completely missing evidence
            anomaly_score = np.nan
            anomaly_flag = None
            coverage_overall = 0.0
        else:
            anomaly_score = float(max(available_families))
            coverage_overall = (cov_T + cov_E + cov_L + cov_O) / (tot_T + tot_E + tot_L + tot_O)

            # ---------------------------------------------------------
            # Persistence-aware Alert Flag
            # ---------------------------------------------------------
            if prot_active:
                # Immediate trigger on active verified protection! Bypasses persistence
                anomaly_flag = True
                state.in_alert = True
                state.consecutive_high_timestamps.clear()
                state.consecutive_low_timestamps.clear()
            else:
                # Statistical persistence
                if anomaly_score >= self.config.a_on:
                    state.consecutive_high_timestamps.append(timestamp)
                    state.consecutive_low_timestamps.clear()

                    if not state.in_alert:
                        # Entry check: >= N observations spanning >= min_span_hours
                        if len(state.consecutive_high_timestamps) >= self.config.min_persistence_observations:
                            span = (state.consecutive_high_timestamps[-1] - state.consecutive_high_timestamps[0]).total_seconds() / 3600.0
                            if span >= self.config.min_persistence_span_hours:
                                state.in_alert = True
                                state.episode_count += 1
                else:
                    state.consecutive_low_timestamps.append(timestamp)
                    state.consecutive_high_timestamps.clear()

                    if state.in_alert:
                        # Recovery check: >= N observations spanning >= min_span_hours below cutoff
                        if len(state.consecutive_low_timestamps) >= self.config.min_persistence_observations:
                            span = (state.consecutive_low_timestamps[-1] - state.consecutive_low_timestamps[0]).total_seconds() / 3600.0
                            if span >= self.config.min_persistence_span_hours:
                                state.in_alert = False

                anomaly_flag = state.in_alert

        state.last_timestamp = timestamp

        # Deduplicate reasons preserving order
        unique_reasons = list(dict.fromkeys(reasons))

        return {
            "anomaly_score": anomaly_score,
            "anomaly_flag": anomaly_flag,
            "reason_codes": unique_reasons,
            "severity_thermal": s_thermal,
            "severity_electrical": s_electrical,
            "severity_loading": s_loading,
            "severity_oil": s_oil,
            "severity_protection": s_protection if s_protection is not None else np.nan,
            "coverage_thermal": coverage_thermal,
            "coverage_electrical": coverage_electrical,
            "coverage_loading": coverage_loading,
            "coverage_oil": coverage_oil,
            "coverage_overall": coverage_overall,
        }

    def run(self, telemetry_or_features: pd.DataFrame) -> pd.DataFrame:
        """Run anomaly detection on batch or stream, preserving row ordering."""
        df = telemetry_or_features.copy()
        if not pd.api.types.is_datetime64_any_dtype(df.get("timestamp")):
            df["timestamp"] = pd.to_datetime(df.get("timestamp"), errors="coerce")

        if df["timestamp"].isna().any():
            raise AnomalyDetectorError("Timestamp contains invalid or missing values")
        if df["transformer_id"].isna().any() or (df["transformer_id"].astype(str).str.strip() == "").any():
            raise AnomalyDetectorError("transformer_id must be populated for every row")
        if df.duplicated(["transformer_id", "timestamp"]).any():
            raise AnomalyDetectorError("Duplicate (transformer_id, timestamp) pairs detected")

        original_index = df.index
        temp_df = df.reset_index(drop=True)
        ordered = temp_df.sort_values(["transformer_id", "timestamp"], kind="stable")

        out_rows: list[dict[str, Any]] = []
        for transformer_id, group in ordered.groupby("transformer_id", sort=False):
            state = self.get_state(str(transformer_id))
            for _, row in group.iterrows():
                record_res = self.process_record(row, state)
                record_res["__index"] = row.name
                out_rows.append(record_res)

        out_df = pd.DataFrame(out_rows).set_index("__index").sort_index()

        for col in ALL_ANOMALY_COLUMNS:
            temp_df[col] = out_df[col]

        temp_df.index = original_index
        base_cols = [c for c in telemetry_or_features.columns if c not in ALL_ANOMALY_COLUMNS]
        return temp_df.loc[:, [*base_cols, *ALL_ANOMALY_COLUMNS]]


def run_anomaly_detection(
    data: pd.DataFrame,
    config: AnomalyDetectorConfig | None = None,
) -> pd.DataFrame:
    """Functional interface matching repository convention."""
    detector = AnomalyDetector(config=config)
    return detector.run(data)
