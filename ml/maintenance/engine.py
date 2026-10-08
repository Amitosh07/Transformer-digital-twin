"""Deterministic advisory Maintenance Engine for Transformer Digital Twin.

Phase 05 — Maintenance Engine:
- Converts established upstream condition evidence into deterministic advisory
  NORMAL / WATCH / PLAN / URGENT priority, human-readable recommendations, and traceable reason codes.
- Implements strict decision precedence:
    URGENT > PLAN > WATCH > NORMAL
- Enforces elapsed-time persistence predicate:
    P_on = 1 iff n_valid >= 3 and (t_last - t_first) >= 30 min and max(Delta t_adjacent) <= 30 min
- Tracks independent evidence families:
    Thermal (T), Electrical (E), Loading (L), Oil (O), Protection (Prot).
    Thermal signals (temperature level, slope/rate, residual) belong to ONE thermal family.
    Health Index and anomaly score summarize upstream evidence and do NOT create independent corroboration.
- Implements verified protection bypass and trip latching:
    Verified active trip (oil_temp_trip == 1) immediately escalates to URGENT,
    overrides missing non-protection inputs, and latches until cleared under authorized operator policy.
- Evaluates recovery using the same elapsed-time predicate on qualifying clear observations.
- Strictly advisory: no automatic electrical control, switching commands, or invented emergency envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final, Mapping, Sequence

import numpy as np
import pandas as pd


class MaintenancePriority(str, Enum):
    """Allowed maintenance priorities under canonical ML contract."""
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    PLAN = "PLAN"
    URGENT = "URGENT"


# Output column names
MAINTENANCE_OUTPUT_COLUMNS: Final = (
    "maintenance_priority",
    "maintenance_recommendation",
    "maintenance_reason_codes",
)

MAINTENANCE_METADATA_COLUMNS: Final = (
    "reason_codes",
    "maintenance_data_quality_status",
    "maintenance_inference_status",
    "maintenance_trip_latched",
    "maintenance_clear_policy_status",
)

ALL_MAINTENANCE_COLUMNS: Final = (*MAINTENANCE_OUTPUT_COLUMNS, *MAINTENANCE_METADATA_COLUMNS)

# Standard reason codes specified in Phase 05
REASON_VERIFIED_TRIP: Final = "VERIFIED_TRIP"
REASON_TRIP_LATCHED: Final = "TRIP_LATCHED"
REASON_OIL_TEMP_TRIP: Final = "OIL_TEMP_TRIP"
REASON_CRITICAL_OPERATIONAL_LIMIT_EXCEEDED: Final = "CRITICAL_OPERATIONAL_LIMIT_EXCEEDED"
REASON_PERSISTENT_SEVERE_HEATING: Final = "PERSISTENT_SEVERE_HEATING"
REASON_CONFIRMED_LOW_OIL: Final = "CONFIRMED_LOW_OIL"
REASON_PERSISTENT_MOG_ALARM: Final = "PERSISTENT_MOG_ALARM"
REASON_PERSISTENT_OIL_TEMP_ALARM: Final = "PERSISTENT_OIL_TEMP_ALARM"
REASON_PERSISTENT_CURRENT_IMBALANCE: Final = "PERSISTENT_CURRENT_IMBALANCE"
REASON_PERSISTENT_POSITIVE_THERMAL_RESIDUAL: Final = "PERSISTENT_POSITIVE_THERMAL_RESIDUAL"
REASON_PERSISTENT_MULTI_FAMILY_WARNING: Final = "PERSISTENT_MULTI_FAMILY_WARNING"
REASON_PERSISTENT_THERMAL_ELEVATION: Final = "PERSISTENT_THERMAL_ELEVATION"
REASON_PERSISTENT_OIL_LEVEL_ANOMALY: Final = "PERSISTENT_OIL_LEVEL_ANOMALY"
REASON_VALIDATED_PROXY_RISK_EPISODE: Final = "VALIDATED_PROXY_RISK_EPISODE"
REASON_UNCONFIRMED_STATISTICAL_EXCEEDANCE: Final = "UNCONFIRMED_STATISTICAL_EXCEEDANCE"
REASON_HIGH_DEMAND_NO_RATING: Final = "HIGH_DEMAND_NO_RATING"
REASON_RATING_UNAVAILABLE: Final = "RATING_UNAVAILABLE"
REASON_OVERLOAD_UNAPPROVED_ENVELOPE: Final = "OVERLOAD_UNAPPROVED_ENVELOPE"
REASON_OVERLOAD: Final = "OVERLOAD"
REASON_THERMAL_MODEL_MISMATCH: Final = "THERMAL_MODEL_MISMATCH"
REASON_SENSOR_MISMATCH: Final = "SENSOR_MISMATCH"
REASON_DATA_QUALITY_ISSUE: Final = "DATA_QUALITY_ISSUE"
REASON_MISSING_CRITICAL_TELEMETRY: Final = "MISSING_CRITICAL_TELEMETRY"
REASON_INSUFFICIENT_DATA: Final = "INSUFFICIENT_DATA"
REASON_EXPERIMENTAL_PROXY_RISK_RESEARCH_ONLY: Final = "EXPERIMENTAL_PROXY_RISK_RESEARCH_ONLY"
REASON_OIL_LEVEL_DECREASING: Final = "OIL_LEVEL_DECREASING"
REASON_HIGH_OIL_TEMP: Final = "HIGH_OIL_TEMP"
REASON_RAPID_TEMP_RISE: Final = "RAPID_TEMP_RISE"
REASON_CURRENT_IMBALANCE: Final = "CURRENT_IMBALANCE"
REASON_THERMAL_RESIDUAL_HIGH: Final = "THERMAL_RESIDUAL_HIGH"
REASON_LOW_OIL_LEVEL: Final = "LOW_OIL_LEVEL"
REASON_MOG_ALARM: Final = "MOG_ALARM"
REASON_OIL_TEMP_ALARM: Final = "OIL_TEMP_ALARM"
REASON_HIGH_LOADING: Final = "HIGH_LOADING"

# Standard advisory recommendations from Phase 05 Section 6
RECOMMENDATION_NORMAL: Final = "Normal operating condition; continue standard monitoring."
RECOMMENDATION_HIGH_DEMAND_NO_RATING: Final = "Review load distribution and monitor thermal response."
RECOMMENDATION_OVERLOAD_UNAPPROVED_ENVELOPE: Final = (
    "Review loading duration and operating envelope; thermal response currently normal."
)
RECOMMENDATION_CURRENT_IMBALANCE: Final = (
    "Verify measurement/phase allocation and plan balancing if confirmed."
)
RECOMMENDATION_POSITIVE_RESIDUAL: Final = (
    "Verify sensor, cooling, ventilation and operating configuration."
)
RECOMMENDATION_FALLING_OIL: Final = (
    "Verify gauge and inspect for leakage; do not assert leakage as fact."
)
RECOMMENDATION_MOG_ALARM: Final = (
    "Arrange oil-level/protection inspection under operating procedure."
)
RECOMMENDATION_OIL_TEMP_ALARM: Final = (
    "Arrange oil-temperature protection inspection under operating procedure."
)
RECOMMENDATION_TRIP: Final = (
    "Immediate operator review under site protection procedure."
)
RECOMMENDATION_TRIP_LATCHED: Final = (
    "Immediate operator review under site protection procedure (trip latched; requires authorized clear)."
)
RECOMMENDATION_SENSOR_MISMATCH_OR_MISSING: Final = (
    "Verify instrumentation/communication before diagnosing physical damage."
)
RECOMMENDATION_SEVERE_THERMAL_AND_LOW_OIL: Final = (
    "Immediate inspection required: severe thermal stress corroborated by low oil condition."
)
RECOMMENDATION_EXPERIMENTAL_PROXY_RISK: Final = (
    "Research annotation: unvalidated experimental proxy risk detected; monitor operation."
)
RECOMMENDATION_UNCONFIRMED_SPIKE: Final = (
    "Monitor transient; verify whether temperature rise is sustained."
)
RECOMMENDATION_UNCONFIRMED_EXCEEDANCE: Final = (
    "Monitor transient; unconfirmed condition exceedance."
)
RECOMMENDATION_MULTI_FAMILY_WARNING: Final = (
    "Schedule maintenance inspection: persistent multi-family condition warnings detected."
)
RECOMMENDATION_CRITICAL_LIMIT: Final = (
    "Immediate operator response required: critical operational limit exceeded."
)
RECOMMENDATION_SEVERE_THERMAL_ELEVATION: Final = (
    "Verify cooling, ventilation, and load distribution for sustained thermal elevation."
)

# Persistence timing defaults
DEFAULT_MIN_PERSISTENCE_OBSERVATIONS: Final = 3
DEFAULT_MIN_PERSISTENCE_SPAN_MINUTES: Final = 30.0
DEFAULT_CONTINUITY_GAP_MINUTES: Final = 30.0


class MaintenanceEngineError(ValueError):
    """Raised when maintenance engine configuration or inputs are invalid."""


@dataclass(frozen=True)
class MaintenanceEngineConfig:
    """Configuration for deterministic advisory Maintenance Engine."""
    min_persistence_observations: int = DEFAULT_MIN_PERSISTENCE_OBSERVATIONS
    min_persistence_span_minutes: float = DEFAULT_MIN_PERSISTENCE_SPAN_MINUTES
    continuity_gap_minutes: float = DEFAULT_CONTINUITY_GAP_MINUTES
    critical_temp_limit_c: float | None = None
    validated_proxy_risk_threshold: float | None = None
    engine_version: str = "1.0.0"


@dataclass
class ConditionRun:
    """Continuous observation timestamp tracker for an active condition."""
    timestamps: list[pd.Timestamp] = field(default_factory=list)

    def add_observation(
        self,
        timestamp: pd.Timestamp,
        is_active: bool,
        gap_threshold_seconds: float = 1800.0,
    ) -> bool:
        """Add an observation. If active, append and evaluate persistence; else clear buffer."""
        if not is_active:
            self.timestamps.clear()
            return False

        if self.timestamps:
            dt = (timestamp - self.timestamps[-1]).total_seconds()
            if dt > gap_threshold_seconds:
                # Continuity gap breaks the qualifying run!
                self.timestamps.clear()

        self.timestamps.append(timestamp)
        return self.is_persistent(gap_threshold_seconds)

    def is_persistent(
        self,
        gap_threshold_seconds: float = 1800.0,
        min_obs: int = 3,
        min_span_seconds: float = 1800.0,
    ) -> bool:
        """Check predicate: n_valid >= 3 and span >= 30 min and max adjacent gap <= 30 min."""
        if len(self.timestamps) < min_obs:
            return False
        span = (self.timestamps[-1] - self.timestamps[0]).total_seconds()
        if span < min_span_seconds:
            return False
        for i in range(1, len(self.timestamps)):
            if (self.timestamps[i] - self.timestamps[i - 1]).total_seconds() > gap_threshold_seconds:
                return False
        return True

    def clear(self) -> None:
        self.timestamps.clear()


@dataclass
class MaintenancePersistenceState:
    """Stateful tracking of evidence runs, trip latching, and recovery for an asset."""
    transformer_id: str
    last_timestamp: pd.Timestamp | None = None
    trip_latched: bool = False
    latched_at: pd.Timestamp | None = None
    clear_policy_status: str = "NOT_APPLICABLE"
    escalated_priority: MaintenancePriority | None = None

    # Condition runs for various persistent conditions
    run_severe_thermal: ConditionRun = field(default_factory=ConditionRun)
    run_current_imbalance: ConditionRun = field(default_factory=ConditionRun)
    run_positive_residual: ConditionRun = field(default_factory=ConditionRun)
    run_mog_alarm: ConditionRun = field(default_factory=ConditionRun)
    run_oil_temp_alarm: ConditionRun = field(default_factory=ConditionRun)
    run_oil_level_anomaly: ConditionRun = field(default_factory=ConditionRun)
    run_multi_family_warning: ConditionRun = field(default_factory=ConditionRun)
    run_clear_recovery: ConditionRun = field(default_factory=ConditionRun)

    def reset(self) -> None:
        self.last_timestamp = None
        self.trip_latched = False
        self.latched_at = None
        self.clear_policy_status = "NOT_APPLICABLE"
        self.escalated_priority = None
        self.run_severe_thermal.clear()
        self.run_current_imbalance.clear()
        self.run_positive_residual.clear()
        self.run_mog_alarm.clear()
        self.run_oil_temp_alarm.clear()
        self.run_oil_level_anomaly.clear()
        self.run_multi_family_warning.clear()
        self.run_clear_recovery.clear()


class MaintenanceEngine:
    """Stateful deterministic advisory Maintenance Engine."""

    def __init__(self, config: MaintenanceEngineConfig | None = None) -> None:
        self.config = config or MaintenanceEngineConfig()
        self._states: dict[str, MaintenancePersistenceState] = {}

    def get_state(self, transformer_id: str) -> MaintenancePersistenceState:
        if transformer_id not in self._states:
            self._states[transformer_id] = MaintenancePersistenceState(transformer_id=transformer_id)
        return self._states[transformer_id]

    def clear_trip_latch(
        self,
        transformer_id: str,
        operator_id: str | None = None,
        clear_policy: str | None = None,
    ) -> bool:
        """Clear latched trip status under authorized operator procedure."""
        state = self.get_state(transformer_id)
        if not state.trip_latched:
            return False
        if operator_id is None:
            state.clear_policy_status = "CONFIGURATION REQUIRED"
            return False

        state.trip_latched = False
        state.clear_policy_status = f"OPERATOR_CLEARED:{operator_id}:{clear_policy or 'DEFAULT'}"
        if state.escalated_priority == MaintenancePriority.URGENT:
            state.escalated_priority = None
        return True

    def process_record(
        self,
        record: Mapping[str, Any] | pd.Series,
        state: MaintenancePersistenceState | None = None,
    ) -> dict[str, Any]:
        """Evaluate a single record against decision precedence and persistence."""
        transformer_id = str(record.get("transformer_id", "default_transformer"))
        if state is None:
            state = self.get_state(transformer_id)

        raw_ts = record.get("timestamp")
        if raw_ts is not None and not pd.isna(raw_ts):
            timestamp = pd.to_datetime(raw_ts)
        else:
            timestamp = pd.Timestamp.now(tz=timezone.utc)

        gap_sec = self.config.continuity_gap_minutes * 60.0
        min_span_sec = self.config.min_persistence_span_minutes * 60.0
        min_obs = self.config.min_persistence_observations

        # -------------------------------------------------------------
        # 1. Parse Protection Evidence
        # -------------------------------------------------------------
        oil_trip = record.get("oil_temp_trip")
        oil_alarm = record.get("oil_temp_alarm")
        mog_alarm = record.get("magnetic_oil_gauge_alarm")

        is_trip_active = False
        has_protection_coverage = False

        if oil_trip is not None and not pd.isna(oil_trip):
            has_protection_coverage = True
            if float(oil_trip) == 1.0:
                is_trip_active = True

        is_oil_alarm_active = False
        if oil_alarm is not None and not pd.isna(oil_alarm):
            has_protection_coverage = True
            if float(oil_alarm) == 1.0:
                is_oil_alarm_active = True

        is_mog_alarm_active = False
        if mog_alarm is not None and not pd.isna(mog_alarm):
            has_protection_coverage = True
            if float(mog_alarm) == 1.0:
                is_mog_alarm_active = True

        # -------------------------------------------------------------
        # 2. Parse Telemetry and Derived Condition Signals
        # -------------------------------------------------------------
        oil_temp = record.get("oil_temperature")
        oil_temp_rate = record.get("oil_temperature_rate")
        t_res = record.get("thermal_residual")
        t_ready = record.get("thermal_readiness")
        s_thermal = record.get("severity_thermal")

        has_temp_coverage = oil_temp is not None and not pd.isna(oil_temp)

        # Thermal Family Evidence (all thermal signals belong to ONE family)
        is_thermal_spike = False
        is_severe_thermal = False
        is_positive_residual_concerning = False
        is_thermal_model_mismatch = False

        # Positive residual
        if t_ready == "READY" and t_res is not None and not pd.isna(t_res):
            t_res_val = float(t_res)
            if t_res_val > 0 and (t_res_val >= 4.0 or (s_thermal is not None and not pd.isna(s_thermal) and float(s_thermal) >= 0.5)):
                is_positive_residual_concerning = True
            elif t_res_val < 0:
                is_thermal_model_mismatch = True

        # Severe thermal condition
        if s_thermal is not None and not pd.isna(s_thermal) and float(s_thermal) >= 0.8:
            is_severe_thermal = True
        elif has_temp_coverage and float(oil_temp) >= 85.0:
            is_severe_thermal = True

        # Thermal spike (unconfirmed single observation or elevated thermal)
        if (s_thermal is not None and not pd.isna(s_thermal) and float(s_thermal) >= 0.5) or (
            has_temp_coverage and float(oil_temp) >= 75.0
        ) or is_positive_residual_concerning:
            is_thermal_spike = True

        # Check upstream reason codes for thermal hints
        raw_reasons = record.get("reason_codes", [])
        if not isinstance(raw_reasons, (list, tuple)):
            raw_reasons = []
        if REASON_THERMAL_MODEL_MISMATCH in raw_reasons:
            is_thermal_model_mismatch = True

        # Electrical Family Evidence
        cur_imb = record.get("current_imbalance_pct")
        s_electrical = record.get("severity_electrical")
        is_electrical_concerning = False
        if s_electrical is not None and not pd.isna(s_electrical) and float(s_electrical) >= 0.5:
            is_electrical_concerning = True
        elif cur_imb is not None and not pd.isna(cur_imb) and float(cur_imb) >= 50.0:
            is_electrical_concerning = True
        elif REASON_CURRENT_IMBALANCE in raw_reasons:
            is_electrical_concerning = True

        # Oil Family Evidence
        s_oil = record.get("severity_oil")
        oil_dev = record.get("oil_level_deviation")
        is_low_oil_confirmed = False
        is_oil_level_decreasing = False

        if s_oil is not None and not pd.isna(s_oil) and float(s_oil) >= 0.5:
            is_low_oil_confirmed = True
        elif oil_dev is not None and not pd.isna(oil_dev) and float(oil_dev) <= -2.0:
            is_low_oil_confirmed = True
        elif REASON_LOW_OIL_LEVEL in raw_reasons:
            is_low_oil_confirmed = True

        if REASON_OIL_LEVEL_DECREASING in raw_reasons:
            is_oil_level_decreasing = True

        # Loading Evidence
        kva = record.get("apparent_power_kva")
        rated_kva = record.get("rated_power_kva")
        load_pct = record.get("loading_percent")
        s_loading = record.get("severity_loading")

        is_high_demand_no_rating = False
        is_overload_unapproved_envelope = False

        has_rating = (rated_kva is not None and not pd.isna(rated_kva) and float(rated_kva) > 0)
        has_high_load = False
        if load_pct is not None and not pd.isna(load_pct) and float(load_pct) > 100.0:
            has_high_load = True
        elif s_loading is not None and not pd.isna(s_loading) and float(s_loading) >= 0.5:
            has_high_load = True
        elif kva is not None and not pd.isna(kva) and float(kva) >= 800.0:
            has_high_load = True
        elif REASON_HIGH_LOADING in raw_reasons:
            has_high_load = True

        thermal_normal = not is_severe_thermal and not is_thermal_spike

        if has_high_load and not has_rating and thermal_normal:
            is_high_demand_no_rating = True
        elif has_high_load and has_rating and thermal_normal and (load_pct is not None and float(load_pct) > 100.0):
            is_overload_unapproved_envelope = True

        # Sensor data quality
        is_sensor_quality_issue = (
            REASON_DATA_QUALITY_ISSUE in raw_reasons
            or REASON_SENSOR_MISMATCH in raw_reasons
        )

        # Experimental Proxy Risk
        fault_risk = record.get("fault_risk")
        is_released = bool(record.get("is_operationally_released", False))
        has_experimental_risk = (
            fault_risk is not None
            and not pd.isna(fault_risk)
            and float(fault_risk) >= 0.5
            and not is_released
        )

        # Multi-family warning check (independent families: T, E, O)
        # Note: T signals (level, rate, residual) count as AT MOST 1 family
        active_warning_families = 0
        if is_thermal_spike or is_severe_thermal:
            active_warning_families += 1
        if is_electrical_concerning:
            active_warning_families += 1
        if is_low_oil_confirmed or is_oil_level_decreasing or is_mog_alarm_active:
            active_warning_families += 1

        is_multi_family_warning = (active_warning_families >= 2)

        # -------------------------------------------------------------
        # 3. Update Condition Persistence State Machine
        # -------------------------------------------------------------
        p_severe_thermal = state.run_severe_thermal.add_observation(
            timestamp, is_severe_thermal, gap_sec
        )
        p_current_imbalance = state.run_current_imbalance.add_observation(
            timestamp, is_electrical_concerning, gap_sec
        )
        p_positive_residual = state.run_positive_residual.add_observation(
            timestamp, is_positive_residual_concerning and not is_thermal_model_mismatch, gap_sec
        )
        p_mog_alarm = state.run_mog_alarm.add_observation(
            timestamp, is_mog_alarm_active, gap_sec
        )
        p_oil_temp_alarm = state.run_oil_temp_alarm.add_observation(
            timestamp, is_oil_alarm_active, gap_sec
        )
        p_oil_level = state.run_oil_level_anomaly.add_observation(
            timestamp, is_low_oil_confirmed, gap_sec
        )
        p_multi_family = state.run_multi_family_warning.add_observation(
            timestamp, is_multi_family_warning, gap_sec
        )

        # Trip latching state update
        if is_trip_active:
            state.trip_latched = True
            state.latched_at = timestamp
            state.clear_policy_status = "CONFIGURATION REQUIRED"

        state.last_timestamp = timestamp

        # -------------------------------------------------------------
        # 4. Evaluate Decision Precedence
        # -------------------------------------------------------------
        priority: MaintenancePriority | None = None
        recommendation: str = ""
        reasons: list[str] = []
        data_quality_status: str = "COMPLETE"
        inference_status: str = "VALIDATED"

        # Check critical operational limit
        is_critical_limit_exceeded = False
        if (
            self.config.critical_temp_limit_c is not None
            and has_temp_coverage
            and float(oil_temp) >= self.config.critical_temp_limit_c
        ):
            is_critical_limit_exceeded = True

        # Corroborated severe heating: persistent severe thermal + independent low oil/protection
        is_corroborated_severe_heating = p_severe_thermal and (
            is_low_oil_confirmed or is_mog_alarm_active or is_oil_alarm_active or is_electrical_concerning
        )

        # ---------------------------------------------------------
        # LEVEL 1: URGENT Precedence
        # ---------------------------------------------------------
        if state.trip_latched:
            priority = MaintenancePriority.URGENT
            recommendation = (
                RECOMMENDATION_TRIP if is_trip_active else RECOMMENDATION_TRIP_LATCHED
            )
            reasons.extend([REASON_VERIFIED_TRIP, REASON_OIL_TEMP_TRIP])
            if not is_trip_active:
                reasons.append(REASON_TRIP_LATCHED)
            state.escalated_priority = MaintenancePriority.URGENT

        elif is_critical_limit_exceeded:
            priority = MaintenancePriority.URGENT
            recommendation = RECOMMENDATION_CRITICAL_LIMIT
            reasons.append(REASON_CRITICAL_OPERATIONAL_LIMIT_EXCEEDED)
            state.escalated_priority = MaintenancePriority.URGENT

        elif is_corroborated_severe_heating:
            priority = MaintenancePriority.URGENT
            recommendation = RECOMMENDATION_SEVERE_THERMAL_AND_LOW_OIL
            reasons.extend([REASON_PERSISTENT_SEVERE_HEATING, REASON_CONFIRMED_LOW_OIL])
            if has_temp_coverage and float(oil_temp) >= 75.0:
                reasons.append(REASON_HIGH_OIL_TEMP)
            if is_low_oil_confirmed:
                reasons.append(REASON_LOW_OIL_LEVEL)
            state.escalated_priority = MaintenancePriority.URGENT

        # ---------------------------------------------------------
        # LEVEL 2: PLAN Precedence
        # ---------------------------------------------------------
        elif p_mog_alarm:
            priority = MaintenancePriority.PLAN
            recommendation = RECOMMENDATION_MOG_ALARM
            reasons.extend([REASON_PERSISTENT_MOG_ALARM, REASON_MOG_ALARM])
            state.escalated_priority = MaintenancePriority.PLAN

        elif p_oil_temp_alarm:
            priority = MaintenancePriority.PLAN
            recommendation = RECOMMENDATION_OIL_TEMP_ALARM
            reasons.extend([REASON_PERSISTENT_OIL_TEMP_ALARM, REASON_OIL_TEMP_ALARM])
            state.escalated_priority = MaintenancePriority.PLAN

        elif p_current_imbalance:
            priority = MaintenancePriority.PLAN
            recommendation = RECOMMENDATION_CURRENT_IMBALANCE
            reasons.extend([REASON_PERSISTENT_CURRENT_IMBALANCE, REASON_CURRENT_IMBALANCE])
            state.escalated_priority = MaintenancePriority.PLAN

        elif p_positive_residual:
            priority = MaintenancePriority.PLAN
            recommendation = RECOMMENDATION_POSITIVE_RESIDUAL
            reasons.extend([REASON_PERSISTENT_POSITIVE_THERMAL_RESIDUAL, REASON_THERMAL_RESIDUAL_HIGH])
            state.escalated_priority = MaintenancePriority.PLAN

        elif p_severe_thermal:
            priority = MaintenancePriority.PLAN
            recommendation = RECOMMENDATION_SEVERE_THERMAL_ELEVATION
            reasons.extend([REASON_PERSISTENT_THERMAL_ELEVATION, REASON_HIGH_OIL_TEMP])
            state.escalated_priority = MaintenancePriority.PLAN

        elif p_oil_level:
            priority = MaintenancePriority.PLAN
            recommendation = RECOMMENDATION_FALLING_OIL
            reasons.extend([REASON_PERSISTENT_OIL_LEVEL_ANOMALY, REASON_LOW_OIL_LEVEL])
            state.escalated_priority = MaintenancePriority.PLAN

        elif p_multi_family:
            priority = MaintenancePriority.PLAN
            recommendation = RECOMMENDATION_MULTI_FAMILY_WARNING
            reasons.append(REASON_PERSISTENT_MULTI_FAMILY_WARNING)
            state.escalated_priority = MaintenancePriority.PLAN

        elif (
            is_released
            and fault_risk is not None
            and not pd.isna(fault_risk)
            and self.config.validated_proxy_risk_threshold is not None
            and float(fault_risk) >= self.config.validated_proxy_risk_threshold
        ):
            priority = MaintenancePriority.PLAN
            recommendation = "Schedule preventive inspection based on validated proxy-risk forecast."
            reasons.append(REASON_VALIDATED_PROXY_RISK_EPISODE)
            state.escalated_priority = MaintenancePriority.PLAN

        # ---------------------------------------------------------
        # LEVEL 3: WATCH Precedence
        # ---------------------------------------------------------
        elif not has_temp_coverage or not has_protection_coverage:
            priority = MaintenancePriority.WATCH
            recommendation = RECOMMENDATION_SENSOR_MISMATCH_OR_MISSING
            reasons.extend([REASON_MISSING_CRITICAL_TELEMETRY, REASON_INSUFFICIENT_DATA])
            data_quality_status = "INSUFFICIENT_COVERAGE"

        elif is_high_demand_no_rating:
            priority = MaintenancePriority.WATCH
            recommendation = RECOMMENDATION_HIGH_DEMAND_NO_RATING
            reasons.extend([REASON_HIGH_DEMAND_NO_RATING, REASON_RATING_UNAVAILABLE])
            data_quality_status = "RATING_UNAVAILABLE"

        elif is_overload_unapproved_envelope:
            priority = MaintenancePriority.WATCH
            recommendation = RECOMMENDATION_OVERLOAD_UNAPPROVED_ENVELOPE
            reasons.extend([REASON_OVERLOAD_UNAPPROVED_ENVELOPE, REASON_OVERLOAD])

        elif is_thermal_model_mismatch:
            priority = MaintenancePriority.WATCH
            recommendation = RECOMMENDATION_POSITIVE_RESIDUAL
            reasons.append(REASON_THERMAL_MODEL_MISMATCH)

        elif is_sensor_quality_issue:
            priority = MaintenancePriority.WATCH
            recommendation = RECOMMENDATION_SENSOR_MISMATCH_OR_MISSING
            reasons.extend([REASON_DATA_QUALITY_ISSUE, REASON_SENSOR_MISMATCH])

        elif has_experimental_risk:
            priority = MaintenancePriority.WATCH
            recommendation = RECOMMENDATION_EXPERIMENTAL_PROXY_RISK
            reasons.append(REASON_EXPERIMENTAL_PROXY_RISK_RESEARCH_ONLY)
            inference_status = "UNVALIDATED_RESEARCH_ONLY"

        elif is_oil_level_decreasing:
            priority = MaintenancePriority.WATCH
            recommendation = RECOMMENDATION_FALLING_OIL
            reasons.append(REASON_OIL_LEVEL_DECREASING)

        elif is_thermal_spike or is_electrical_concerning or is_mog_alarm_active or is_oil_alarm_active:
            # Unconfirmed statistical spike / exceedance without persistence
            priority = MaintenancePriority.WATCH
            if is_thermal_spike:
                recommendation = RECOMMENDATION_UNCONFIRMED_SPIKE
                reasons.extend([REASON_UNCONFIRMED_STATISTICAL_EXCEEDANCE, REASON_HIGH_OIL_TEMP])
            elif is_mog_alarm_active:
                recommendation = RECOMMENDATION_MOG_ALARM
                reasons.extend([REASON_UNCONFIRMED_STATISTICAL_EXCEEDANCE, REASON_MOG_ALARM])
            elif is_oil_alarm_active:
                recommendation = RECOMMENDATION_OIL_TEMP_ALARM
                reasons.extend([REASON_UNCONFIRMED_STATISTICAL_EXCEEDANCE, REASON_OIL_TEMP_ALARM])
            else:
                recommendation = RECOMMENDATION_CURRENT_IMBALANCE
                reasons.extend([REASON_UNCONFIRMED_STATISTICAL_EXCEEDANCE, REASON_CURRENT_IMBALANCE])

        # ---------------------------------------------------------
        # LEVEL 4: NORMAL Precedence and Recovery State Machine
        # ---------------------------------------------------------
        else:
            # No current active problem on this observation
            if state.escalated_priority in (MaintenancePriority.PLAN, MaintenancePriority.URGENT):
                # An escalated state requires qualifying clear persistence to recover
                is_clear_obs = (
                    has_temp_coverage
                    and has_protection_coverage
                    and not is_trip_active
                    and not is_oil_alarm_active
                    and not is_mog_alarm_active
                    and not is_severe_thermal
                    and not is_electrical_concerning
                    and not is_low_oil_confirmed
                    and not is_high_demand_no_rating
                    and not is_overload_unapproved_envelope
                )
                p_recovered = state.run_clear_recovery.add_observation(
                    timestamp, is_clear_obs, gap_sec
                )
                if p_recovered:
                    # Successfully recovered after continuous clear observation window
                    state.escalated_priority = None
                    priority = MaintenancePriority.NORMAL
                    recommendation = RECOMMENDATION_NORMAL
                    state.clear_policy_status = "RECOVERED"
                else:
                    # In recovery window: maintain escalated priority until P_clear is fulfilled
                    priority = state.escalated_priority
                    recommendation = (
                        RECOMMENDATION_CURRENT_IMBALANCE
                        if priority == MaintenancePriority.PLAN
                        else RECOMMENDATION_TRIP
                    )
                    reasons.append("RECOVERY_IN_PROGRESS")
            else:
                priority = MaintenancePriority.NORMAL
                recommendation = RECOMMENDATION_NORMAL

        # Clean reasons preserving order
        unique_reasons = list(dict.fromkeys(reasons))

        persistence_status = {
            "p_severe_thermal": p_severe_thermal,
            "p_current_imbalance": p_current_imbalance,
            "p_positive_residual": p_positive_residual,
            "p_mog_alarm": p_mog_alarm,
            "p_oil_temp_alarm": p_oil_temp_alarm,
            "p_oil_level": p_oil_level,
            "p_multi_family": p_multi_family,
        }

        return {
            "maintenance_priority": priority.value if priority else MaintenancePriority.NORMAL.value,
            "maintenance_recommendation": recommendation,
            "maintenance_reason_codes": unique_reasons,
            "reason_codes": unique_reasons,
            "maintenance_data_quality_status": data_quality_status,
            "maintenance_inference_status": inference_status,
            "maintenance_trip_latched": state.trip_latched,
            "maintenance_clear_policy_status": state.clear_policy_status,
            "maintenance_persistence_status": persistence_status,
        }

    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        """Process a DataFrame of telemetry / analytics in chronological order per transformer."""
        df = data.copy()
        if not pd.api.types.is_datetime64_any_dtype(df.get("timestamp")):
            df["timestamp"] = pd.to_datetime(df.get("timestamp"), errors="coerce")

        if "transformer_id" not in df.columns:
            df["transformer_id"] = "default_transformer"

        original_index = df.index
        temp_df = df.reset_index(drop=True)
        ordered = temp_df.sort_values(["transformer_id", "timestamp"], kind="stable")

        out_rows: list[dict[str, Any]] = []
        for transformer_id, group in ordered.groupby("transformer_id", sort=False):
            state = self.get_state(str(transformer_id))
            for _, row in group.iterrows():
                res = self.process_record(row, state)
                res["__index"] = row.name
                out_rows.append(res)

        out_df = pd.DataFrame(out_rows).set_index("__index").sort_index()

        for col in ALL_MAINTENANCE_COLUMNS:
            temp_df[col] = out_df[col]

        temp_df.index = original_index
        base_cols = [c for c in data.columns if c not in ALL_MAINTENANCE_COLUMNS]
        return temp_df.loc[:, [*base_cols, *ALL_MAINTENANCE_COLUMNS]]


def evaluate_maintenance(
    record: Mapping[str, Any] | pd.Series,
    state: MaintenancePersistenceState | None = None,
    config: MaintenanceEngineConfig | None = None,
) -> dict[str, Any]:
    """Pure functional interface to evaluate maintenance on a single record."""
    engine = MaintenanceEngine(config=config)
    return engine.process_record(record, state=state)


def run_maintenance_engine(
    data: pd.DataFrame,
    config: MaintenanceEngineConfig | None = None,
) -> pd.DataFrame:
    """Run Maintenance Engine on a DataFrame conforming to the repository pipeline."""
    engine = MaintenanceEngine(config=config)
    return engine.run(data)
