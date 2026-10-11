"""Operating Health Index engine for transformer digital twin.

Phase 03 — Operating Health Index:
- Explainable 0–100 operating-condition Health Index based on six components:
    Thermal (0.30), Electrical (0.20), Loading (0.10), Oil (0.15),
    Protection/Alarm (0.20), Anomaly (0.05).
- Component point scoring: H_j = 100 * (1 - s_j), H_A = 100 * (1 - anomaly_score).
- Protection scoring: clear = 100, verified active alarm = 40, verified active trip = 0.
- Loading component requires applicable verified rating/envelope; null when rating missing.
- Partial coverage: renormalizes original weights over available components (H_available),
  reporting assessed-weight coverage C_H = sum(w_j).
- Persistent-condition cap: min(H_weighted, 20 + min(H_j for j in persistent thermal/electrical/oil/protection)).
  Isolated statistical spikes do NOT trigger persistent cap; loading and anomaly do NOT enter the cap.
- Verified active trip overrides final Health Index to 0 immediately.
- Traceable reason codes and explanation metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Final, Mapping

import numpy as np
import pandas as pd


HEALTH_OUTPUT_COLUMNS: Final = (
    "health_index",
    "health_components",
    "health_reason_codes",
)

HEALTH_METADATA_COLUMNS: Final = (
    "health_coverage",
    "health_unweighted_score",
    "health_cap_applied",
    "health_trip_override",
)

ALL_HEALTH_COLUMNS: Final = (*HEALTH_OUTPUT_COLUMNS, *HEALTH_METADATA_COLUMNS)

# Established component weights summing strictly to 1.0
COMPONENT_WEIGHTS: Final[dict[str, float]] = {
    "thermal": 0.30,
    "electrical": 0.20,
    "loading": 0.10,
    "oil": 0.15,
    "alarm": 0.20,
    "anomaly": 0.05,
}

# Protection discrete scores
PROTECTION_SCORE_CLEAR: Final = 100.0
PROTECTION_SCORE_ALARM: Final = 40.0
PROTECTION_SCORE_TRIP: Final = 0.0

# Persistent condition allowance
CAP_ALLOWANCE_POINTS: Final = 20.0

# Components eligible for the persistent-condition cap
CAP_ELIGIBLE_COMPONENTS: Final = frozenset({"thermal", "electrical", "oil", "alarm"})


class HealthIndexError(ValueError):
    """Raised when Health Index inputs or configuration are invalid."""


@dataclass(frozen=True)
class HealthIndexConfig:
    """Configuration for operating Health Index calculation."""
    weights: dict[str, float] = field(default_factory=lambda: dict(COMPONENT_WEIGHTS))
    alarm_score: float = PROTECTION_SCORE_ALARM
    trip_score: float = PROTECTION_SCORE_TRIP
    clear_score: float = PROTECTION_SCORE_CLEAR
    cap_allowance_points: float = CAP_ALLOWANCE_POINTS
    config_version: str = "1.0.0"

    def __post_init__(self) -> None:
        weight_sum = sum(self.weights.values())
        if not np.isclose(weight_sum, 1.0, atol=1e-6):
            raise HealthIndexError(f"Component weights must sum to 1.0, got: {weight_sum}")
        for k, w in self.weights.items():
            if w < 0:
                raise HealthIndexError(f"Weight for {k} must be non-negative, got: {w}")


@dataclass
class HealthPersistenceState:
    """Stateful tracking of persistent severe condition across observations."""
    transformer_id: str
    last_timestamp: pd.Timestamp | None = None
    # Buffers tracking consecutive severe readings per cap-eligible component
    consecutive_severe_timestamps: dict[str, list[pd.Timestamp]] = field(
        default_factory=lambda: {"thermal": [], "electrical": [], "oil": []}
    )

    def reset(self) -> None:
        self.last_timestamp = None
        for k in self.consecutive_severe_timestamps:
            self.consecutive_severe_timestamps[k].clear()


def calculate_health_index_record(
    components: Mapping[str, float | None],
    *,
    is_trip_active: bool = False,
    persistent_components: set[str] | None = None,
    config: HealthIndexConfig | None = None,
) -> dict[str, Any]:
    """Pure arithmetic engine to compute Health Index for a single evaluation record.

    Parameters:
        components: Dict of component scores in [0, 100], or None if unavailable.
                    Keys: 'thermal', 'electrical', 'loading', 'oil', 'alarm', 'anomaly'.
        is_trip_active: Whether verified active trip contact is present (triggers override to 0).
        persistent_components: Set of components with verified persistent severe conditions
                                eligible for the 20-point cap.
        config: Configuration instance with weights and allowance constants.
    """
    cfg = config or HealthIndexConfig()
    persistent = persistent_components or set()

    # 1. Protection override check: verified trip overrides everything to 0!
    if is_trip_active or components.get("alarm") == cfg.trip_score:
        return {
            "health_index": 0.0,
            "health_components": {k: components.get(k) for k in cfg.weights},
            "health_coverage": sum(cfg.weights[k] for k in cfg.weights if components.get(k) is not None),
            "health_unweighted_score": 0.0,
            "health_cap_applied": False,
            "health_trip_override": True,
        }

    # 2. Identify available components
    available = {
        k: float(v) for k, v in components.items()
        if k in cfg.weights and v is not None and not pd.isna(v)
    }

    if not available:
        # Completely unavailable evidence
        return {
            "health_index": None,
            "health_components": {k: None for k in cfg.weights},
            "health_coverage": 0.0,
            "health_unweighted_score": None,
            "health_cap_applied": False,
            "health_trip_override": False,
        }

    # 3. Calculate weighted available score and coverage
    coverage_weight = sum(cfg.weights[k] for k in available)
    if coverage_weight <= 0:
        return {
            "health_index": None,
            "health_components": {k: components.get(k) for k in cfg.weights},
            "health_coverage": 0.0,
            "health_unweighted_score": None,
            "health_cap_applied": False,
            "health_trip_override": False,
        }

    weighted_sum = sum(cfg.weights[k] * available[k] for k in available)
    h_available = weighted_sum / coverage_weight

    # 4. Persistent-condition cap
    # The cap applies ONLY to supported persistent condition evidence in thermal, electrical, oil, alarm.
    # Isolated noise, loading, and anomaly do NOT enter the cap.
    cap_eligible = [
        available[k] for k in available
        if k in CAP_ELIGIBLE_COMPONENTS and (k in persistent or (k == "alarm" and available[k] == cfg.alarm_score))
    ]

    h_capped = h_available
    cap_applied = False

    if cap_eligible:
        min_eligible = min(cap_eligible)
        cap_val = cfg.cap_allowance_points + min_eligible
        if cap_val < h_available:
            h_capped = cap_val
            cap_applied = True

    final_h = float(np.clip(h_capped, 0.0, 100.0))

    return {
        "health_index": final_h,
        "health_components": {k: components.get(k) for k in cfg.weights},
        "health_coverage": float(coverage_weight),
        "health_unweighted_score": float(h_available),
        "health_cap_applied": cap_applied,
        "health_trip_override": False,
    }


class OperatingHealthIndex:
    """Stateful Operating Health Index pipeline consuming Phase 01/02 outputs."""

    def __init__(self, config: HealthIndexConfig | None = None) -> None:
        self.config = config or HealthIndexConfig()
        self._states: dict[str, HealthPersistenceState] = {}

    def get_state(self, transformer_id: str) -> HealthPersistenceState:
        if transformer_id not in self._states:
            self._states[transformer_id] = HealthPersistenceState(transformer_id=transformer_id)
        return self._states[transformer_id]

    def reset_state(self, transformer_id: str | None = None) -> None:
        if transformer_id is not None:
            if transformer_id in self._states:
                self._states[transformer_id].reset()
        else:
            self._states.clear()

    def process_record(
        self,
        row: Mapping[str, Any],
        state: HealthPersistenceState,
    ) -> dict[str, Any]:
        """Compute Health Index and traceability reasons for a single observation."""
        timestamp = pd.Timestamp(row["timestamp"])

        # Check gaps for persistence tracking
        dt_hours: float | None = None
        if state.last_timestamp is not None:
            dt_hours = (timestamp - state.last_timestamp).total_seconds() / 3600.0
            if dt_hours > 0.5:
                state.reset()

        # -------------------------------------------------------------
        # 1. Thermal Component
        # -------------------------------------------------------------
        s_T = row.get("severity_thermal")
        H_T = float(100.0 * (1.0 - s_T)) if (s_T is not None and not pd.isna(s_T)) else None

        # -------------------------------------------------------------
        # 2. Electrical Component
        # -------------------------------------------------------------
        s_E = row.get("severity_electrical")
        H_E = float(100.0 * (1.0 - s_E)) if (s_E is not None and not pd.isna(s_E)) else None

        # -------------------------------------------------------------
        # 3. Loading Component (Rating required!)
        # -------------------------------------------------------------
        # Rule: Loading health requires an applicable verified rating/envelope.
        # If rating is missing -> loading component is null.
        u_S = row.get("apparent_power_utilization")
        if u_S is not None and not pd.isna(u_S):
            # If rating utilization is available, loading health drops as utilization exceeds 1.0
            s_L = float(np.clip(max(0.0, float(u_S) - 1.0), 0.0, 1.0))
            H_L = float(100.0 * (1.0 - s_L))
        else:
            # Without nameplate rating, loading health remains null
            H_L = None

        # -------------------------------------------------------------
        # 4. Oil Component
        # -------------------------------------------------------------
        s_O = row.get("severity_oil")
        H_O = float(100.0 * (1.0 - s_O)) if (s_O is not None and not pd.isna(s_O)) else None

        # -------------------------------------------------------------
        # 5. Protection/Alarm Component
        # -------------------------------------------------------------
        oil_trip = row.get("oil_temp_trip")
        oil_alarm = row.get("oil_temp_alarm")
        mog_alarm = row.get("magnetic_oil_gauge_alarm")

        is_trip_active = False
        is_alarm_active = False
        has_prot_evidence = False

        if not pd.isna(oil_trip) and oil_trip == 1:
            is_trip_active = True
            has_prot_evidence = True
        elif not pd.isna(oil_trip):
            has_prot_evidence = True

        if not pd.isna(oil_alarm) and oil_alarm == 1:
            is_alarm_active = True
            has_prot_evidence = True
        elif not pd.isna(oil_alarm):
            has_prot_evidence = True

        if not pd.isna(mog_alarm) and mog_alarm == 1:
            is_alarm_active = True
            has_prot_evidence = True
        elif not pd.isna(mog_alarm):
            has_prot_evidence = True

        if is_trip_active:
            H_P = self.config.trip_score
        elif is_alarm_active:
            H_P = self.config.alarm_score
        elif has_prot_evidence:
            H_P = self.config.clear_score
        else:
            # Missing protection contacts are NOT clear!
            H_P = None

        # -------------------------------------------------------------
        # 6. Anomaly Component
        # -------------------------------------------------------------
        a_score = row.get("anomaly_score")
        if a_score is not None and not pd.isna(a_score):
            H_A = float(100.0 * (1.0 - float(a_score)))
        else:
            H_A = None

        # -------------------------------------------------------------
        # Track persistent severe condition for cap
        # -------------------------------------------------------------
        persistent_components: set[str] = set()

        # Check thermal persistence: severe if s_T >= 0.5 (H_T <= 50)
        if H_T is not None and H_T <= 50.0:
            state.consecutive_severe_timestamps["thermal"].append(timestamp)
            if len(state.consecutive_severe_timestamps["thermal"]) >= 3:
                span = (state.consecutive_severe_timestamps["thermal"][-1] - state.consecutive_severe_timestamps["thermal"][0]).total_seconds() / 3600.0
                if span >= 0.5:
                    persistent_components.add("thermal")
        else:
            state.consecutive_severe_timestamps["thermal"].clear()

        # Check electrical persistence: severe if s_E >= 0.5 (H_E <= 50)
        if H_E is not None and H_E <= 50.0:
            state.consecutive_severe_timestamps["electrical"].append(timestamp)
            if len(state.consecutive_severe_timestamps["electrical"]) >= 3:
                span = (state.consecutive_severe_timestamps["electrical"][-1] - state.consecutive_severe_timestamps["electrical"][0]).total_seconds() / 3600.0
                if span >= 0.5:
                    persistent_components.add("electrical")
        else:
            state.consecutive_severe_timestamps["electrical"].clear()

        # Check oil persistence: severe if s_O >= 0.5 (H_O <= 50)
        if H_O is not None and H_O <= 50.0:
            state.consecutive_severe_timestamps["oil"].append(timestamp)
            if len(state.consecutive_severe_timestamps["oil"]) >= 3:
                span = (state.consecutive_severe_timestamps["oil"][-1] - state.consecutive_severe_timestamps["oil"][0]).total_seconds() / 3600.0
                if span >= 0.5:
                    persistent_components.add("oil")
        else:
            state.consecutive_severe_timestamps["oil"].clear()

        state.last_timestamp = timestamp

        # Compute record
        components_map = {
            "thermal": H_T,
            "electrical": H_E,
            "loading": H_L,
            "oil": H_O,
            "alarm": H_P,
            "anomaly": H_A,
        }

        calc_result = calculate_health_index_record(
            components=components_map,
            is_trip_active=is_trip_active,
            persistent_components=persistent_components,
            config=self.config,
        )

        # Trace reason codes from upstream
        reasons: list[str] = []
        upstream_reasons = row.get("reason_codes", [])
        if isinstance(upstream_reasons, (list, tuple)):
            reasons.extend(upstream_reasons)

        if calc_result["health_trip_override"]:
            reasons.append("VERIFIED_TRIP_OVERRIDE")
        if calc_result["health_cap_applied"]:
            reasons.append("PERSISTENT_CONDITION_CAP_APPLIED")
        if H_L is None:
            reasons.append("RATING_UNAVAILABLE")

        unique_reasons = list(dict.fromkeys(reasons))

        return {
            "health_index": calc_result["health_index"],
            "health_components": calc_result["health_components"],
            "health_reason_codes": unique_reasons,
            "health_coverage": calc_result["health_coverage"],
            "health_unweighted_score": calc_result["health_unweighted_score"],
            "health_cap_applied": calc_result["health_cap_applied"],
            "health_trip_override": calc_result["health_trip_override"],
        }

    def run(self, telemetry_or_anomaly_data: pd.DataFrame) -> pd.DataFrame:
        """Run Health Index calculation over DataFrame preserving row ordering."""
        df = telemetry_or_anomaly_data.copy()
        if not pd.api.types.is_datetime64_any_dtype(df.get("timestamp")):
            df["timestamp"] = pd.to_datetime(df.get("timestamp"), errors="coerce")

        original_index = df.index
        temp_df = df.reset_index(drop=True)
        ordered = temp_df.sort_values(["transformer_id", "timestamp"], kind="stable")

        out_rows: list[dict[str, Any]] = []
        for transformer_id, group in ordered.groupby("transformer_id", sort=False):
            state = self.get_state(str(transformer_id))
            for _, row in group.iterrows():
                rec_res = self.process_record(row, state)
                rec_res["__index"] = row.name
                out_rows.append(rec_res)

        out_df = pd.DataFrame(out_rows).set_index("__index").sort_index()

        for col in ALL_HEALTH_COLUMNS:
            temp_df[col] = out_df[col]

        temp_df.index = original_index
        base_cols = [c for c in telemetry_or_anomaly_data.columns if c not in ALL_HEALTH_COLUMNS]
        return temp_df.loc[:, [*base_cols, *ALL_HEALTH_COLUMNS]]


def run_operating_health_index(
    data: pd.DataFrame,
    config: HealthIndexConfig | None = None,
) -> pd.DataFrame:
    """Functional interface matching repository convention."""
    engine = OperatingHealthIndex(config=config)
    return engine.run(data)
