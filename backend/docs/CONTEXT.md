STACK: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync, psycopg 3), Alembic, PostgreSQL 16, pytest, ruff, pydantic-settings, httpx, paho-mqtt (later).

TEAM: Person 1 = ML/Twin (owns dataschema.md + ML contract). Person 2 = me, backend/DB. Person 3 = Streamlit dashboard, consumes my API only. Person 4 = simulator/DevOps (synthetic data, replay, fault injection, MQTT, Docker).

ARCHITECTURE RULE: Raw data -> adapter -> canonical telemetry -> validation -> features -> ML/Twin -> analytics -> API -> dashboard. The backend handles ONLY canonical field names. Never use raw Kaggle column names (VL1, IL1, OTI, WTI, ATI, OLI, OTI_A, ...) in backend code, DB, or API.

CANONICAL TELEMETRY FIELDS (exact names):
- identity: transformer_id (str, required), timestamp (tz-aware datetime, required)
- electrical: phase_voltage_l1, phase_voltage_l2, phase_voltage_l3, current_l1, current_l2, current_l3, neutral_current
- thermal: oil_temperature, winding_temperature, ambient_temperature
- oil: oil_level
- protection (0/1): oil_temp_alarm, oil_temp_trip, magnetic_oil_gauge_alarm
- power: active_power_total (kW), apparent_power_total (kVA), reactive_power_total (kVAr), energy_kwh
- power factor: power_factor_l1, power_factor_l2, power_factor_l3

NAMEPLATE (transformers table, all nullable config): rated_power_kva, rated_voltage_hv, rated_voltage_lv, rated_current_a, cooling_class, oil_type.

HARD RULES:
1. VL12, VL23, VL31 are EXCLUDED. Never in DB columns, Pydantic models, payloads, or docs examples. Pydantic uses extra="forbid" so they are rejected with 422.
2. Missing != zero. Every telemetry field except transformer_id and timestamp is nullable. Never coerce None to 0.
3. Units of oil_temperature, winding_temperature (may be a status, not a continuous temp), ambient_temperature, oil_level are UNVERIFIED. No unit conversion or range checks on them; only numeric/null.
4. Protection fields accept only 0/1/true/false/null.
5. Timestamps: TIMESTAMPTZ in DB, ISO-8601 in API, UTC. Naive timestamps rejected.
6. Every analytics row stores schema_version, feature_version, model_version.
7. Never hard-code a transformer rating.
8. Public-dataset fault prediction is a PROXY (alarm/trip) task. Never describe fault_risk/predicted_fault as a confirmed physical fault.
9. Dashboard must work from API responses alone. Never expose DB internals or ML dataframes.
10. Simulator (Person 4) emits canonical fields only; simulated rows carry metadata source_name and optional scenario_id (metadata, NOT canonical telemetry fields).

ML RESPONSE SHAPE (all analytic outputs nullable when inference_status != "OK"):
{ transformer_id, timestamp, inference_status ("OK"|"INSUFFICIENT_DATA"), missing_features[],
  loading_percent, thermal_model_temperature, thermal_residual, thermal_state,
  anomaly_score (0..1), anomaly_flag, health_index (0..100, 100=healthiest),
  health_components{thermal,electrical,loading,oil,alarm,anomaly}, health_reason_codes[],
  fault_risk (0..1), predicted_fault, prediction_confidence (0..1),
  maintenance_priority ("NORMAL"|"WATCH"|"PLAN"|"URGENT"), maintenance_recommendation, reason_codes[],
  schema_version, feature_version, model_version }
Reason codes: HIGH_OIL_TEMP, RAPID_TEMP_RISE, OVERLOAD, CURRENT_IMBALANCE, VOLTAGE_IMBALANCE, LOW_OIL_LEVEL, OIL_TEMP_ALARM, OIL_TEMP_TRIP, MOG_ALARM, ANOMALOUS_PATTERN.

CODE QUALITY: type hints everywhere, small modules, routes -> services -> repositories (no business logic in route handlers), error responses shaped {"error": {"code","message","details"}}, tests for every module.
