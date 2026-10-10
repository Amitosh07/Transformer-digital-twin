"""Deterministic, stateful, quality-aware unified ML/Twin pipeline orchestrator.

Phase 07 â€” Unified ML/Twin Pipeline:
- Integrates Phases 00-06 into ONE deterministic canonical-to-analytics pipeline.
- Enforces strict execution order:
    1. Resolve compatible bundle/config
    2. Validate schema/time/identity
    3. Apply duplicate/replay policy
    4. Load compatible per-asset state
    5. Build causal features using available historical context
    6. Calculate loading only when verified rating exists
    7. Run Phase 01 thermal twin using its owning implementation
    8. Run Phase 02 anomaly detector using its owning implementation
    9. Run Phase 04 forecast/proxy branch only when its eligibility/status allows it
    10. Run Phase 03 Health Index using its owning implementation
    11. Run Phase 05 Maintenance Engine using its owning implementation
    12. Serialize stable response
    13. Persist state/result atomically
    14. Return one consistent analytical result
- Per-asset state isolation: state never leaks across assets.
- Batch/stream equivalence: processing in chunks or 1-by-1 yields identical results.
- Idempotency & Replay: duplicate identical observations return identical results without double-advancing state.
- Late-row policy: late observations (t <= last_t) are rejected or idempotently returned. Negative elapsed time is never integrated.
- Rating & loading: loading_percent and apparent_power_utilization remain null without verified rating.
- Forecast status: remains null / INSUFFICIENT_VALIDATION while unreleased.
"""

from __future__ import annotations

import copy
import logging
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from ml.anomaly.detector import AnomalyDetector
from ml.features.feature_engineering import (
    DEFAULT_GAP_LIMIT_MINUTES,
    REQUIRED_TELEMETRY_COLUMNS,
    build_features,
)
from ml.health.engine import OperatingHealthIndex
from ml.maintenance.engine import MaintenanceEngine
from ml.pipeline.asset_config import AssetConfig
from ml.pipeline.bundle import PipelineBundle
from ml.pipeline.state import AssetPipelineState
from ml.pipeline.identity import payload_hash, utc, FIELDS
from ml.rul.model import update_degradation, operational_result
from ml.prediction.model import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_INSUFFICIENT_VALIDATION,
)
from ml.thermal.thermal_twin import (
    ThermalReadinessStatus,
    ThermalTwin,
    compute_current_forcing,
)

logger = logging.getLogger(__name__)

# Excluded source columns that must never appear in input or output
EXCLUDED_NORMALIZED_FIELDS = frozenset({"vl12", "vl23", "vl31"})


class PipelineError(ValueError):
    """Raised when pipeline inputs or contracts are violated."""


class PipelineValidationError(PipelineError):
    """Raised when record schema or time validation fails."""


def ingestion_outcome(record, digest, status):
    return {'schema_version': '1.1.0', 'transformer_id': record['transformer_id'],
            'timestamp': utc(record['timestamp']), 'snapshot_id': digest,
            'ingestion_outcome': status, 'http_status': 409,
            'forward_state_advanced': False, 'analytics': None,
            'reason': 'SEMANTIC_PAYLOAD_CONFLICT' if status == 'CONFLICT' else 'OUT_OF_ORDER_EVENT_TIME'}


def _check_no_excluded_fields(record: Mapping[str, Any]) -> None:
    for key in record:
        if isinstance(key, str):
            norm = "".join(c for c in key.casefold() if c.isalnum())
            if norm in EXCLUDED_NORMALIZED_FIELDS:
                raise PipelineValidationError(
                    f"Field {key!r} is strictly excluded from canonical telemetry"
                )


def _sanitize_numeric(val: Any) -> float | None:
    """Sanitize float values ensuring JSON compliance (NaN/Inf -> None)."""
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        if not np.isfinite(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


class UnifiedMLPipeline:
    """Unified stateful execution engine for the Transformer Digital Twin."""

    def __init__(
        self,
        bundle: PipelineBundle | None = None,
        asset_configs: Mapping[str, AssetConfig] | None = None,
    ) -> None:
        self.bundle = bundle or PipelineBundle.load_from_processed_dir()
        self.asset_configs: dict[str, AssetConfig] = (
            {k: v for k, v in asset_configs.items()} if asset_configs else {}
        )
        self._asset_states: dict[str, AssetPipelineState] = {}

        # Instantiate owning module runners with bundle configurations
        self.thermal_twin = ThermalTwin(config=self.bundle.thermal_config)
        self.anomaly_detector = AnomalyDetector(config=self.bundle.anomaly_config)
        self.health_engine = OperatingHealthIndex(config=self.bundle.health_config)
        self.maintenance_engine = MaintenanceEngine(config=self.bundle.maintenance_config)

    def register_asset(self, config: AssetConfig) -> None:
        """Register or update asset nameplate configuration."""
        self.asset_configs[config.transformer_id] = config

    def hydrate_history(self, config, current, history):
        """Hydrate a cold asset once; subsequent history is consistency evidence.

        Never replay already accepted records. Unknown older durable identities
        require the backend receipt store; only the bounded cache is checked here.
        """
        asset = config.transformer_id
        rows = [dict(r) for r in history]
        if any(r.get('transformer_id') != asset for r in rows):
            raise PipelineValidationError('history contains another asset')
        rows.sort(key=lambda r: utc(r['timestamp']))
        if any(utc(r['timestamp']) >= utc(current['timestamp']) for r in rows):
            raise PipelineValidationError('history must precede current event')
        state = self._asset_states.get(asset)
        if state is None or state.last_processed_timestamp is None:
            for row in rows:
                outcome = self.process_record(row, config)
                if 'ingestion_outcome' in outcome:
                    raise PipelineValidationError('history conflict')
        else:
            for row in rows:
                prior = state.identity_cache.get(pd.Timestamp(row['timestamp']).tz_convert('UTC').isoformat())
                if prior and prior['hash'] != payload_hash(row):
                    raise PipelineValidationError('supplied history conflicts with accepted identity')
                if pd.Timestamp(row['timestamp']) > state.last_processed_timestamp:
                    raise PipelineValidationError('new history requires explicit cold hydration/backfill session')

    def get_state(self, transformer_id: str) -> AssetPipelineState:
        """Retrieve or initialize isolated state for the given transformer."""
        if transformer_id not in self._asset_states:
            self._asset_states[transformer_id] = AssetPipelineState(
                transformer_id=transformer_id,
                bundle_id=self.bundle.bundle_id,
                schema_version=self.bundle.schema_version,
                feature_version=self.bundle.feature_version,
                model_version=self.bundle.model_version,
            )
        state = self._asset_states[transformer_id]

        # Explicit state compatibility check
        if not state.is_compatible(
            self.bundle.bundle_id,
            self.bundle.schema_version,
            self.bundle.feature_version,
            self.bundle.model_version,
        ):
            logger.warning(
                "State for asset %s is incompatible with current bundle/version. Resetting state.",
                transformer_id,
            )
            state.reset(
                bundle_id=self.bundle.bundle_id,
                schema_version=self.bundle.schema_version,
                feature_version=self.bundle.feature_version,
                model_version=self.bundle.model_version,
            )

        return state

    def reset_state(self, transformer_id: str | None = None) -> None:
        """Reset state for a specific asset or all assets."""
        if transformer_id is not None:
            if transformer_id in self._asset_states:
                self._asset_states[transformer_id].reset()
        else:
            for state in self._asset_states.values():
                state.reset()

    def process_record(
        self,
        record: Mapping[str, Any],
        asset_config: AssetConfig | None = None,
    ) -> dict[str, Any]:
        """Process a single canonical TransformerRecord.

        Returns one stable analytical response.
        """
        # 1 & 2. Validate schema & identity
        _check_no_excluded_fields(record)
        if record.get('schema_version', '1.0.0') not in ('1.0.0', '1.1.0'):
            raise PipelineValidationError('unsupported telemetry envelope version')

        tx_id = record.get("transformer_id")
        if not tx_id or not str(tx_id).strip():
            raise PipelineValidationError("Record requires a populated non-empty 'transformer_id'")
        tx_id = str(tx_id).strip()
        if len(tx_id) > 128:
            raise PipelineValidationError('asset identity exceeds 128 characters')
        if tx_id != record['transformer_id']:
            raise PipelineValidationError('identity whitespace is not normalized implicitly')
        a = record.get('acquisition') or {}
        allowed = set(FIELDS) | {'transformer_id', 'timestamp', 'schema_version',
                                'source_name', 'scenario_id', 'acquisition'}
        if set(record) - allowed:
            raise PipelineValidationError(f'noncanonical input fields: {sorted(set(record) - allowed)}')
        simulated_origin = a.get('source_kind') == 'SIMULATED' or (
            a.get('source_kind') == 'REPLAYED' and a.get('origin_kind') == 'SIMULATED')
        if a:
            if a.get('timezone_status') == 'UNKNOWN':
                raise PipelineValidationError('unknown timezone must be staged')
            if a.get('timezone_status') == 'DECLARED_UTC' and not simulated_origin:
                raise PipelineValidationError('declared UTC requires synthetic provenance')
            if a.get('timezone_status') == 'ASSUMED' and (a.get('source_kind') != 'REPLAYED' or a.get('timestamp_origin') != 'REPLAY_ASSUMPTION'):
                raise PipelineValidationError('undeclared replay timezone assumption')
            if record.get('source_name') is not None and record['source_name'] != a.get('source_name'):
                raise PipelineValidationError('source names disagree')
            if any(v == 'SYNTHETIC' for v in a.get('field_verification', {}).values()) and not simulated_origin:
                raise PipelineValidationError('synthetic units cannot authorize a real source')
        if a.get('source_kind') == 'REPLAYED' and (
            a.get('origin_transformer_id') == tx_id or not a.get('origin_transformer_id') or not a.get('replay_run_id') or tx_id not in self.asset_configs):
            raise PipelineValidationError('replay requires a separate registered asset and origin/run IDs')
        if 'received_at' in record:
            raise PipelineValidationError('received_at is backend-owned; remove it from the inference input')

        ts_raw = record.get("timestamp")
        if ts_raw is None or pd.isna(ts_raw):
            raise PipelineValidationError("Record requires a populated 'timestamp'")
        try:
            ts = pd.Timestamp(ts_raw)
            if ts.tzinfo is None:
                raise PipelineValidationError('timezone-aware timestamp required')
            else:
                ts = ts.tz_convert(timezone.utc)
        except Exception as exc:
            raise PipelineValidationError(f"Invalid timestamp format: {ts_raw}") from exc

        # Resolve asset configuration
        cfg = asset_config or self.asset_configs.get(tx_id) or AssetConfig(transformer_id=tx_id)
        if cfg.transformer_id != tx_id:
            raise PipelineValidationError('configuration/record asset mismatch')

        # 3 & 4. Load compatible per-asset state & Check idempotency / late-row
        # Reject retries/conflicts/late observations before any compatibility reset.
        state = self._asset_states.get(tx_id) or self.get_state(tx_id)

        semantic_hash = payload_hash(record)
        snapshot = (record.get('acquisition') or {}).get('snapshot_id') or semantic_hash
        if snapshot != semantic_hash:
            raise PipelineValidationError('snapshot_id must equal semantic payload hash')
        identity = ts.isoformat()
        prior = state.identity_cache.get(identity)
        if prior is not None:
            if prior['hash'] != semantic_hash:
                return ingestion_outcome(record, semantic_hash, 'CONFLICT')
            return copy.deepcopy(prior['result'])
        if state.last_processed_timestamp is not None and ts <= state.last_processed_timestamp:
            return ingestion_outcome(record, semantic_hash, 'REJECTED_LATE_OBSERVATION')
        # H05 uses the reserved extension on H01's candidate state. Validate before
        # mutating any existing algorithm, and never infer D from HI/anomaly.
        scenario = cfg.additional_configuration.get('synthetic_rul')
        if state.synthetic_degradation is not None and scenario is None:
            raise PipelineValidationError('active synthetic scenario removal requires explicit state migration')
        if scenario is not None:
            try:
                candidate_degradation, projection = update_degradation(state.synthetic_degradation, record, scenario)
                rul_result = projection.rul
            except ValueError as exc:
                raise PipelineValidationError(f'invalid synthetic RUL state/configuration: {exc}') from exc
        else:
            candidate_degradation = None
            rul_result = operational_result(ts, a, cfg.additional_configuration.get('operational_rul_evidence'))
        state = self.get_state(tx_id)
        if state.configuration_fingerprint is not None and state.configuration_fingerprint != cfg.fingerprint:
            state.reset()
        state.configuration_fingerprint = cfg.fingerprint

        # Check gap > 30 minutes from last processed timestamp
        if state.last_processed_timestamp is not None:
            gap_hours = (ts - state.last_processed_timestamp).total_seconds() / 3600.0
            if gap_hours > self.bundle.thermal_config.continuity_gap_hours:
                # Continuity broken: reset upstream persistence & warm-up tracking
                logger.info("Long gap (%.2f h) detected for %s; resetting persistence.", gap_hours, tx_id)
                # Note: ThermalTwin.process_asset will detect dt_hours > continuity_gap_hours
                # and transition thermal readiness to GAP_RESET before resetting state.
                state.anomaly_state.reset()
                state.health_state.reset()
                # Preserve the unresolved maintenance/protection latch across gaps.
                state.history_records.clear()

        # 5. Build causal features using rolling historical context
        # Combine historical records + current record
        history = list(state.history_records)
        curr_dict = dict(record)
        curr_dict["transformer_id"] = tx_id
        curr_dict["timestamp"] = ts

        # Ensure all REQUIRED_TELEMETRY_COLUMNS exist in the dict (with None if missing)
        for col in REQUIRED_TELEMETRY_COLUMNS:
            if col not in curr_dict:
                curr_dict[col] = None

        combined_rows = history + [curr_dict]
        comb_df = pd.DataFrame(combined_rows)
        comb_df["timestamp"] = pd.to_datetime(comb_df["timestamp"], utc=True)
        # Ensure numeric columns are properly typed floats so .abs() etc. succeed even if None/NaN
        for col in REQUIRED_TELEMETRY_COLUMNS:
            if col not in ("transformer_id", "timestamp"):
                comb_df[col] = pd.to_numeric(comb_df[col], errors="coerce")

        # Compute causal features over available window
        try:
            feat_df = build_features(
                comb_df,
                rolling_window="1h",
                gap_limit_minutes=DEFAULT_GAP_LIMIT_MINUTES,
            )
            curr_feat_row = feat_df.iloc[-1].to_dict()
        except Exception as exc:
            logger.error("Feature engineering error: %s", exc)
            curr_feat_row = curr_dict.copy()

        # 6. Calculate loading percent and utilization only when verified rating exists
        apparent_power = _sanitize_numeric(record.get("apparent_power_total"))
        loading_percent, apparent_power_utilization = cfg.calculate_loading(apparent_power, record.get('acquisition'))
        curr_feat_row["loading_percent"] = loading_percent
        curr_feat_row["apparent_power_utilization"] = apparent_power_utilization

        # 7. Run Phase 01 Thermal Twin using its owning implementation
        # ThermalTwin processes the single current observation advancing state.thermal_state
        single_df = pd.DataFrame([curr_feat_row])
        thermal_res_df = self.thermal_twin.process_asset(single_df, state.thermal_state)
        thermal_res = thermal_res_df.iloc[0]

        t_model = _sanitize_numeric(thermal_res.get("thermal_model_temperature"))
        t_residual = _sanitize_numeric(thermal_res.get("thermal_residual"))
        t_state = thermal_res.get("thermal_state")
        t_readiness = thermal_res.get("thermal_readiness")

        # Update features row with thermal residual for downstream models
        curr_feat_row["thermal_residual"] = t_residual
        curr_feat_row["thermal_model_temperature"] = t_model
        curr_feat_row["thermal_state"] = t_state
        curr_feat_row["thermal_readiness"] = t_readiness

        # 8. Run Phase 02 Anomaly Detector using its owning implementation
        anomaly_out = self.anomaly_detector.process_record(curr_feat_row, state.anomaly_state)

        a_score = _sanitize_numeric(anomaly_out.get("anomaly_score"))
        a_flag = anomaly_out.get("anomaly_flag")
        a_reasons = list(anomaly_out.get("reason_codes", []))

        # Add anomaly outputs to feature row for Health Index & Maintenance
        curr_feat_row["anomaly_score"] = a_score
        curr_feat_row["anomaly_flag"] = a_flag
        curr_feat_row["reason_codes"] = a_reasons
        for col in [
            "severity_thermal",
            "severity_electrical",
            "severity_loading",
            "severity_oil",
            "severity_protection",
            "coverage_thermal",
            "coverage_electrical",
            "coverage_loading",
            "coverage_oil",
            "coverage_overall",
        ]:
            curr_feat_row[col] = anomaly_out.get(col)

        # 9. Run Phase 04 Forecast branch only when eligibility/status allows it
        # Under Phase 04 and Phase 06, operational status is INSUFFICIENT_VALIDATION
        forecast_risk = None
        predicted_fault = None
        prediction_confidence = None
        experimental_risk = None
        forecast_inference_status = self.bundle.forecast_operational_status
        is_op_released = bool(
            self.bundle.forecast_model is not None
            and self.bundle.forecast_model.is_operationally_released
        )

        if self.bundle.forecast_model is not None and is_op_released:
            pred_res = self.bundle.forecast_model.predict_record(curr_feat_row)
            forecast_risk = _sanitize_numeric(pred_res.get("fault_risk"))
            predicted_fault = pred_res.get("predicted_fault")
            prediction_confidence = _sanitize_numeric(pred_res.get("prediction_confidence"))
            forecast_inference_status = pred_res.get("inference_status", "READY")
        elif self.bundle.forecast_model is not None:
            # Predict experimental risk for research metadata if available
            pred_res = self.bundle.forecast_model.predict_record(curr_feat_row)
            experimental_risk = _sanitize_numeric(pred_res.get("experimental_risk"))
            forecast_inference_status = pred_res.get("inference_status", STATUS_INSUFFICIENT_VALIDATION)

        # 10. Run Phase 03 Health Index using its owning implementation
        health_row = dict(curr_feat_row)
        if state.maintenance_state.trip_latched:
            health_row['oil_temp_trip'] = 1
        health_out = self.health_engine.process_record(health_row, state.health_state)

        h_index = _sanitize_numeric(health_out.get("health_index"))
        h_components = health_out.get("health_components", {})
        # Sanitize numeric component values
        sanitized_components = {
            k: _sanitize_numeric(v) for k, v in h_components.items()
        } if h_components else None
        h_reasons = list(health_out.get("health_reason_codes", []))

        # Add health outputs to feature row for Maintenance
        curr_feat_row["health_index"] = h_index
        curr_feat_row["health_components"] = sanitized_components
        curr_feat_row["health_reason_codes"] = h_reasons
        curr_feat_row["fault_risk"] = forecast_risk
        curr_feat_row["is_operationally_released"] = is_op_released

        # 11. Run Phase 05 Maintenance Engine using its owning implementation
        maint_out = self.maintenance_engine.process_record(
            curr_feat_row,
            state.maintenance_state,
        )

        m_priority = maint_out.get("maintenance_priority", "NORMAL")
        m_recommendation = maint_out.get("maintenance_recommendation", "")
        m_reasons = list(maint_out.get("maintenance_reason_codes", []))

        # Combine all traceable reason codes preserving order
        all_reasons = list(dict.fromkeys(a_reasons + h_reasons + m_reasons))

        # Determine overall inference status
        # If critical measurements missing -> INSUFFICIENT_DATA, else OK
        missing_crit: list[str] = []
        for crit_col in ("oil_temperature", "current_l1", "current_l2", "current_l3"):
            if record.get(crit_col) is None or pd.isna(record.get(crit_col)):
                missing_crit.append(crit_col)

        overall_status = "INSUFFICIENT_DATA" if len(missing_crit) >= 2 else "OK"

        # Allowed canonical ReasonCode literals in dataschema.md & backend schema
        ALLOWED_CANONICAL_REASONS = frozenset({
            "HIGH_OIL_TEMP",
            "RAPID_TEMP_RISE",
            "OVERLOAD",
            "CURRENT_IMBALANCE",
            "VOLTAGE_IMBALANCE",
            "LOW_OIL_LEVEL",
            "OIL_TEMP_ALARM",
            "OIL_TEMP_TRIP",
            "MOG_ALARM",
            "ANOMALOUS_PATTERN",
        })

        # Sanitize thermal_state
        if t_state is not None and pd.isna(t_state):
            t_state = None
        elif t_state is not None:
            t_state = str(t_state)

        # Filter reasons to canonical allowed set for top-level schema contract
        canonical_health_reasons = [r for r in h_reasons if r in ALLOWED_CANONICAL_REASONS]
        canonical_all_reasons = [r for r in all_reasons if r in ALLOWED_CANONICAL_REASONS]

        # Build human-readable reason representations respecting physical vs unverified indicator
        is_verified_temp = (self.bundle.thermal_config.temperature_unit == "DEG_C")
        reason_descriptions = {}
        for r in all_reasons:
            if r == "HIGH_OIL_TEMP":
                reason_descriptions[r] = (
                    "High oil temperature (Â°C)" if is_verified_temp else "High oil indicator (source units)"
                )
            elif r == "RAPID_TEMP_RISE":
                reason_descriptions[r] = "Rapid temperature rise rate"
            elif r == "OVERLOAD":
                reason_descriptions[r] = "Overload condition exceeding rated capacity"
            elif r == "CURRENT_IMBALANCE":
                reason_descriptions[r] = "Phase current imbalance"
            elif r == "VOLTAGE_IMBALANCE":
                reason_descriptions[r] = "Phase voltage imbalance"
            elif r == "LOW_OIL_LEVEL":
                reason_descriptions[r] = "Low oil level indicator departure"
            elif r == "OIL_LEVEL_DECREASING":
                reason_descriptions[r] = "Decreasing oil level trend"
            elif r == "OIL_TEMP_ALARM":
                reason_descriptions[r] = "Active oil temperature alarm contact"
            elif r == "OIL_TEMP_TRIP":
                reason_descriptions[r] = "Active oil temperature trip contact"
            elif r == "MOG_ALARM":
                reason_descriptions[r] = "Active magnetic oil gauge alarm"
            elif r == "THERMAL_RESIDUAL_HIGH":
                reason_descriptions[r] = "Positive thermal model divergence (exceeding baseline expectation)"
            elif r == "THERMAL_MODEL_MISMATCH":
                reason_descriptions[r] = "Thermal model mismatch (negative residual)"
            else:
                reason_descriptions[r] = r.replace("_", " ").title()

        # 12. Serialize stable analytical response matching contract
        result = {
            "transformer_id": tx_id,
            "timestamp": ts.isoformat(),
            "inference_status": overall_status,
            "missing_features": missing_crit,
            "loading_percent": loading_percent,
            "thermal_model_temperature": t_model,
            "thermal_residual": t_residual,
            "thermal_state": t_state,
            "anomaly_score": a_score,
            "anomaly_flag": a_flag,
            "health_index": h_index,
            "health_components": sanitized_components,
            "health_reason_codes": canonical_health_reasons,
            "fault_risk": forecast_risk,
            "predicted_fault": predicted_fault,
            "prediction_confidence": prediction_confidence,
            "maintenance_priority": m_priority,
            "maintenance_recommendation": m_recommendation,
            "reason_codes": canonical_all_reasons,
            "schema_version": self.bundle.schema_version,
            "feature_version": self.bundle.feature_version,
            "model_version": self.bundle.model_version,
            # Documented approved metadata
            "metadata": {
                "thermal_readiness": t_readiness,
                "thermal_model_mode": self.bundle.thermal_config.mode.value,
                "thermal_temperature_unit": self.bundle.thermal_config.temperature_unit,
                "apparent_power_utilization": apparent_power_utilization,
                "forecast_operational_status": self.bundle.forecast_operational_status,
                "experimental_fault_risk": experimental_risk,
                "maintenance_trip_latched": state.maintenance_state.trip_latched,
                "maintenance_clear_policy_status": state.maintenance_state.clear_policy_status,
                "coverage_overall": _sanitize_numeric(anomaly_out.get("coverage_overall")),
                "health_coverage": _sanitize_numeric(health_out.get("health_coverage")),
                "extended_reason_codes": all_reasons,
                "extended_health_reason_codes": h_reasons,
                "reason_descriptions": reason_descriptions,
            },
        }

        coverage = state.coverage(ts, curr_dict)
        coverage['missing_fields'] = [key for key in FIELDS if record.get(key) is None]
        readiness_reasons = []
        if coverage['fraction'] < 1:
            readiness_reasons.append('REDUCED_HISTORY_COVERAGE')
        if state.history_capped:
            readiness_reasons.append('HISTORY_COUNT_CAP')
        if self.bundle.runtime_mode != 'STRICT_FITTED':
            readiness_reasons.append(self.bundle.runtime_mode)
        if not a:
            readiness_reasons.append('UNKNOWN_PROVENANCE_AND_UNITS')
        elif any(a.get('field_verification', {}).get(k) == 'UNVERIFIED' or a.get('field_units', {}).get(k) in (None, 'UNKNOWN')
                 for k in ('oil_temperature', 'ambient_temperature', 'current_l1', 'current_l2', 'current_l3')):
            readiness_reasons.append('UNVERIFIED_MEASUREMENT_UNITS')
        if loading_percent is None:
            readiness_reasons.append('LOADING_CONFIGURATION_OR_UNITS_INELIGIBLE')
        if state.lifecycle_status == 'REINITIALIZED':
            readiness_reasons.append('STATE_REINITIALIZED_WARMUP')
        if state.protection_context_unknown and record.get('oil_temp_trip') is None:
            readiness_reasons.append('PROTECTION_CONTEXT_UNKNOWN')
        state.lifecycle_status = 'COVERAGE_LOSS' if coverage['fraction'] < 1 else (
            'READY' if t_readiness == 'READY' else 'WARMING_UP')
        result['schema_version'] = record.get('schema_version', '1.0.0')
        result['metadata'].update({
            'coverage': coverage,
            'units': dict(a.get('field_units', {})),
            'versions': {'bundle_id': self.bundle.bundle_id,
                         'configuration_version': cfg.configuration_version,
                         'preprocessing_version': self.bundle.preprocessing_version,
                         'artifact_schema_version': self.bundle.schema_version},
            'forecast': {'target_definition': 'new_oil_alert_within_1h',
                         'horizon_hours': 1., 'release_status': 'INSUFFICIENT_VALIDATION',
                         'operational_eligible': False,
                         'limitation_codes': ['INSUFFICIENT_VALIDATION']},
            'components': {name: {'status': ('INSUFFICIENT_DATA' if self.bundle.runtime_mode != 'STRICT_FITTED' and status == 'READY' else status), 'unit': unit,
                                  'coverage_fraction': coverage['fraction'],
                                  'reasons': readiness_reasons + reasons}
                for name, status, unit, reasons in (
                    ('thermal', 'READY' if t_readiness == 'READY' else 'WARMING_UP',
                     self.bundle.thermal_config.temperature_unit, []),
                    ('anomaly', 'READY' if a_score is not None else 'INSUFFICIENT_DATA', '1', []),
                    ('health', 'READY' if h_index is not None else 'INSUFFICIENT_DATA', 'index', []),
                    ('maintenance', 'INSUFFICIENT_DATA' if overall_status == 'INSUFFICIENT_DATA' else 'READY', None, []),
                    ('forecast', 'UNAVAILABLE', None, ['INSUFFICIENT_VALIDATION']),
                    ('rul', 'UNAVAILABLE', 'h', ['H05_NOT_IMPLEMENTED']))},
        })
        result['metadata']['extended_reason_codes'] = list(dict.fromkeys(all_reasons + readiness_reasons))

        # Preserve the exact unextended legacy response shape. Explicit synthetic
        # configuration or a 1.1.0 envelope opts into the additive RUL member.
        if result['schema_version'] == '1.1.0' or scenario is not None:
            result['rul'] = rul_result
        result['metadata']['components']['rul'] = {
            'status': 'INSUFFICIENT_DATA' if rul_result['rul_status'] == 'INSUFFICIENT_DATA' else 'READY',
            'unit': 'h', 'coverage_fraction': rul_result['coverage_fraction'],
            'reasons': list(rul_result['limitation_codes'])}
        state.synthetic_degradation = candidate_degradation

        # 13. Persist state atomically
        state.commit_observation(curr_dict, ts, result)
        state.last_payload_hash = semantic_hash
        state.last_snapshot_id = snapshot
        state.identity_cache[identity] = {'hash': semantic_hash, 'result': copy.deepcopy(result)}
        if len(state.identity_cache) > state.max_history_rows:
            del state.identity_cache[next(iter(state.identity_cache))]
        state.protection_context_unknown = state.protection_context_unknown and record.get('oil_temp_trip') is None

        # 14. Return consistent response
        return copy.deepcopy(result)

    def process_batch(
        self,
        records: Sequence[Mapping[str, Any]],
        asset_configs: Mapping[str, AssetConfig] | None = None,
    ) -> list[dict[str, Any]]:
        """Process a batch of canonical records, correctly ordering by event-time per asset.

        Supports multi-asset interleaved sequences without state leakage.
        """
        if not records:
            return []

        # Convert to records list
        records_list = [dict(r) for r in records]

        # Group by asset and sort chronologically per asset
        # To maintain the input ordering or return by timestamp, we tag with original index
        indexed_records = list(enumerate(records_list))

        # Sort by timestamp to respect causal sequencing
        def get_ts(item: tuple[int, dict[str, Any]]) -> pd.Timestamp:
            raw_ts = item[1].get("timestamp")
            try:
                t = pd.Timestamp(raw_ts)
                return t.tz_localize(timezone.utc) if t.tzinfo is None else t.tz_convert(timezone.utc)
            except Exception:
                return pd.Timestamp.min.tz_localize(timezone.utc)

        sorted_records = sorted(indexed_records, key=get_ts)

        results_with_idx: list[tuple[int, dict[str, Any]]] = []
        for orig_idx, rec in sorted_records:
            tx_id = str(rec.get("transformer_id") or "")
            cfg = (asset_configs or {}).get(tx_id) or self.asset_configs.get(tx_id)
            res = self.process_record(rec, asset_config=cfg)
            results_with_idx.append((orig_idx, res))

        # Re-sort by original input order
        results_with_idx.sort(key=lambda x: x[0])
        return [r for _, r in results_with_idx]


# Public person-1 callable entrypoint for backend PythonMLTwinClient integration
def analyze(
    transformer: Mapping[str, Any],
    record: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    pipeline: UnifiedMLPipeline | None = None,
) -> dict[str, Any]:
    """Backend adapter entrypoint matching PythonMLTwinClient requirements.

    Args:
        transformer: TransformerOut dictionary containing id and nameplate configuration.
        record: Current TelemetryIn dictionary.
        history: Sequence of prior TelemetryIn dictionaries, oldest first.
        pipeline: Optional UnifiedMLPipeline instance; defaults to global singleton.

    Returns:
        Dictionary conforming to MLResultIn schema.
    """
    pipe = pipeline or _get_global_pipeline()

    # Register/update asset configuration from transformer metadata
    asset_cfg = AssetConfig.from_dict(transformer)
    pipe.register_asset(asset_cfg)
    pipe.hydrate_history(asset_cfg, record, history)

    # Process record through unified pipeline
    res = pipe.process_record(record, asset_config=asset_cfg)

    # Return top-level dictionary compatible with MLResultIn
    return res


_GLOBAL_PIPELINE: UnifiedMLPipeline | None = None


def _get_global_pipeline() -> UnifiedMLPipeline:
    global _GLOBAL_PIPELINE
    if _GLOBAL_PIPELINE is None:
        _GLOBAL_PIPELINE = UnifiedMLPipeline()
    return _GLOBAL_PIPELINE
