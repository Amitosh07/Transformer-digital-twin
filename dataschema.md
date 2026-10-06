# Transformer Digital Twin — Canonical Data Schema

**Repository:** `Amitosh07/Transformer-digital-twin`  
**Canonical branch:** `develop` during development; `main` is stable/demo-ready.  
**Purpose:** Shared data contract for ML, backend, dashboard, simulator, and future CPRI/utility data adapters.

> **Single source of truth:** Team members must use these canonical names and meanings at module boundaries. Dataset-specific column names must be translated by the data adapter; they should not leak into APIs, database models, ML feature lists, or dashboard code.

## 1. Design principles
1. Every observation belongs to one `transformer_id` and one `timestamp`.
2. Measurements are stored in engineering units where the source supports a verified unit.
3. Alarm/trip states are **boolean/status fields**, not temperature values.
4. Raw source columns are retained only inside the ingestion/adapter layer.
5. The public Kaggle dataset is a baseline training/source dataset. Future PowerNext/CPRI data must map into this same canonical contract through an adapter.
6. Missing data is allowed and must not be converted to zero unless zero is physically/source-valid.
7. `VL12`, `VL23`, and `VL31` from `CurrentVoltage.csv` are **explicitly excluded** from the canonical schema and must not be used as model, database, API, or dashboard fields.

## 2. Source dataset
Baseline public dataset: **Distributed Transformer Monitoring** on Kaggle.

Five source files:
- `CurrentVoltage.csv`
- `Overview.csv`
- `Power.csv`
- `PowerFactor.csv`
- `TotalPower.csv`

The public dataset description identifies electrical, thermal, oil-level, alarm/trip, power, and power-factor parameters across these files. The dataset is time-indexed through `DeviceTimeStamp`.

## 3. Canonical record
```
TransformerRecord
├── identity
│   ├── transformer_id
│   └── timestamp
├── electrical
│   ├── phase_voltage_l1
│   ├── phase_voltage_l2
│   ├── phase_voltage_l3
│   ├── current_l1
│   ├── current_l2
│   ├── current_l3
│   └── neutral_current
├── thermal
│   ├── oil_temperature
│   ├── winding_temperature
│   └── ambient_temperature
├── oil_condition
│   └── oil_level
├── protection
│   ├── oil_temp_alarm
│   ├── oil_temp_trip
│   └── magnetic_oil_gauge_alarm
├── power
│   ├── active_power_total
│   ├── apparent_power_total
│   ├── reactive_power_total
│   └── energy_kwh
├── power_factor
│   ├── power_factor_l1
│   ├── power_factor_l2
│   └── power_factor_l3
└── derived_twin
    ├── loading_percent
    ├── thermal_model_temperature
    ├── anomaly_score
    ├── anomaly_flag
    ├── health_index
    ├── fault_risk
    ├── predicted_fault
    ├── maintenance_priority
    └── maintenance_recommendation
```

## 4. Identity fields

| Canonical field | Type | Unit / format | Source | Required | Notes |
|---|---|---|---|---|---|
| `transformer_id` | string | stable ID | system/simulator/utility | Yes | Public dataset may not provide a verified asset ID; use a configurable baseline ID only at the adapter layer. |
| `timestamp` | datetime | ISO-8601, timezone-aware when known | `DeviceTimeStamp` | Yes | Primary time key for cross-file alignment. |

## 5. Electrical measurements

| Canonical field | Type | Unit | Baseline source | Notes |
|---|---|---|---|---|
| `phase_voltage_l1` | float | V | `CurrentVoltage.csv: VL1` | Phase line 1 voltage. |
| `phase_voltage_l2` | float | V | `CurrentVoltage.csv: VL2` | Phase line 2 voltage. |
| `phase_voltage_l3` | float | V | `CurrentVoltage.csv: VL3` | Phase line 3 voltage. |
| `current_l1` | float | A | `CurrentVoltage.csv: IL1` | Line current 1. |
| `current_l2` | float | A | `CurrentVoltage.csv: IL2` | Line current 2. |
| `current_l3` | float | A | `CurrentVoltage.csv: IL3` | Line current 3. |
| `neutral_current` | float | A | `CurrentVoltage.csv: INUT` | Neutral current. |

### Explicitly excluded
- `VL12`
- `VL23`
- `VL31`

These three are intentionally not mapped.

## 6. Thermal measurements

| Canonical field | Type | Baseline source | Unit policy | Notes |
|---|---|---|---|---|
| `oil_temperature` | float | `Overview.csv: OTI` | **Source unit until engineering unit is verified** | Do not assume °C from the public dataset without verification. |
| `winding_temperature` | float/status | `Overview.csv: WTI` | **Source semantics must be verified** | Do not automatically treat it as a continuous temperature series. |
| `ambient_temperature` | float | `Overview.csv: ATI` | source unit; use °C only when verified | Ambient temperature indicator. |

## 7. Oil-condition fields

| Canonical field | Type | Baseline source | Unit | Notes |
|---|---|---|---|---|
| `oil_level` | float | `Overview.csv: OLI` | source-defined / currently unspecified | Do not invent litres, %, or mm without source evidence. |

## 8. Protection / alarm states

| Canonical field | Type | Baseline source | Allowed values | Meaning |
|---|---|---|---|---|
| `oil_temp_alarm` | boolean/int | `Overview.csv: OTI_A` | 0/1 | Oil-temperature alarm indicator. |
| `oil_temp_trip` | boolean/int | `Overview.csv: OTI_T` | 0/1 | Oil-temperature trip indicator. |
| `magnetic_oil_gauge_alarm` | boolean/int | `Overview.csv: MOG_A` | 0/1 | Magnetic oil gauge alarm indicator. |

These are outputs/status indicators. They can be used as baseline/proxy labels for retrospective ML tasks, but must not be presented as confirmed physical-failure ground truth unless future data provides confirmed labels.

## 9. Power measurements

Normalize the source total-power fields as:

| Canonical field | Type | Unit | Baseline source | Notes |
|---|---|---|---|---|
| `active_power_total` | float | kW | `Power.csv` / `TotalPower.csv` | Map from the source total active-power field after exact column verification. |
| `apparent_power_total` | float | kVA | `Power.csv` / `TotalPower.csv` | Useful for loading/capacity calculation when rating is known. |
| `reactive_power_total` | float | kVAr | `Power.csv` / `TotalPower.csv` | Preserve source sign convention. |
| `energy_kwh` | float | kWh | `Power.csv` / `TotalPower.csv` | Treat as cumulative only if source semantics confirm it. |

Phase-level power fields may be kept internally if needed, but they are not required for the minimum shared contract.

## 10. Power factor

| Canonical field | Type | Unit | Baseline source |
|---|---|---|---|
| `power_factor_l1` | float | dimensionless | `PowerFactor.csv: PFL1` |
| `power_factor_l2` | float | dimensionless | `PowerFactor.csv: PFL2` |
| `power_factor_l3` | float | dimensionless | `PowerFactor.csv: PFL3` |

## 11. Asset metadata / nameplate

These are required for the twin but are not guaranteed in the public dataset.

| Canonical field | Type | Unit | Required | Purpose |
|---|---|---|---|---|
| `rated_power_kva` | float | kVA | future/config | Transformer nameplate rating; used for loading %. |
| `rated_voltage_hv` | float | V/kV | future/config | High-side rated voltage. |
| `rated_voltage_lv` | float | V/kV | future/config | Low-side rated voltage. |
| `rated_current_a` | float | A | future/config | Rated line/phase current as specified by asset. |
| `cooling_class` | string | — | optional | Thermal model configuration. |
| `oil_type` | string | — | optional | Future thermal/condition model input. |

Do not hard-code an unverified nameplate rating.

## 12. Future/add-on condition-monitoring fields

Your draft condition-monitoring sheet contains concepts that are important for the target solution but are not present as equivalent live fields in the public dataset. Treat them as future/test-module fields.

### Current/voltage protection tests
- `measured_trip_current_l1_a`
- `measured_trip_current_l2_a`
- `measured_trip_current_l3_a`
- `current_trip_time_s`
- `measured_voltage_l1_v`
- `measured_voltage_l2_v`
- `measured_voltage_l3_v`
- `current_deviation_pct`
- `voltage_deviation_pct`
- `current_trip_pass`
- `voltage_accuracy_pass`

### Temperature-trip tests
- `temperature_trip_setting_1`
- `temperature_trip_setting_2`
- `temperature_trip_setting_3`
- `temperature_trip_observed_1`
- `temperature_trip_observed_2`
- `temperature_trip_observed_3`
- `temperature_trip_deviation_1`
- `temperature_trip_deviation_2`
- `temperature_trip_deviation_3`

### Oil leakage
- `oil_leakage_alarm`
- `oil_level_min_threshold`
- `oil_level_alarm_threshold`
- `oil_leakage_detected`
- `oil_volume_or_level_measurement` (only after units are provided)

### Communication
- `communication_status`
- `communication_protocol`
- `gateway_id`
- `sim_id_or_device_id` (only when appropriate)

These do not belong in the ML feature vector by default.

## 13. Derived Digital Twin fields

| Field | Type | Unit | Producer | Meaning |
|---|---|---|---|---|
| `loading_percent` | float | % | twin/analytics | Estimated loading versus configured transformer rating. |
| `thermal_model_temperature` | float | verified thermal unit | thermal model | Model-estimated thermal state. |
| `anomaly_score` | float | model-specific | anomaly detector | Continuous abnormality score. |
| `anomaly_flag` | boolean/int | 0/1 | anomaly detector | Abnormal-condition flag. |
| `health_index` | float | 0–100 | health engine | Overall asset condition score. |
| `fault_risk` | float | 0–1 | fault model | Estimated risk for configured target. |
| `predicted_fault` | string/null | — | fault model | Predicted class when supported. |
| `maintenance_priority` | enum | — | maintenance engine | NORMAL / WATCH / PLAN / URGENT. |
| `maintenance_recommendation` | string | — | maintenance engine | Human-readable action. |

## 14. Health Index

Target range:

```
100 = healthiest
0   = critical
```

Recommended explainable components:
- thermal_condition
- electrical_condition
- loading_condition
- oil_condition
- alarm_condition
- anomaly_condition

The weights and thresholds must be documented in `docs/methodology.md`, and the dashboard should show contributing sub-scores/reasons.

## 15. Anomaly features

Candidate feature families:
- phase-current imbalance
- phase-voltage imbalance
- neutral-current magnitude
- power demand / utilization
- apparent-power utilization
- power-factor deviation
- oil-temperature level and rate
- ambient-to-oil temperature difference
- winding/thermal state where semantics are valid
- oil-level trend/deviation
- rolling mean/std/slope
- time since last alarm

Never use future-derived target information as a feature for the same evaluation target.

## 16. Fault prediction

For the public baseline, fault prediction should be described as a **baseline/proxy-label task** unless confirmed physical fault labels are provided.

Possible baseline targets:
- `oil_temp_alarm`
- `oil_temp_trip`
- `magnetic_oil_gauge_alarm`
- composite `condition_alert`

Future utility/CPRI data can replace these with confirmed classes without changing the raw telemetry contract.

## 17. Maintenance recommendation contract

Inputs:
- Health Index
- anomaly score/flag
- fault risk/prediction
- loading
- thermal condition
- alarm/trip states
- oil condition
- trend severity

Outputs:
```
maintenance_priority
maintenance_recommendation
reason_codes[]
```

Recommended reason codes:
- `HIGH_OIL_TEMP`
- `RAPID_TEMP_RISE`
- `OVERLOAD`
- `CURRENT_IMBALANCE`
- `VOLTAGE_IMBALANCE`
- `LOW_OIL_LEVEL`
- `OIL_TEMP_ALARM`
- `OIL_TEMP_TRIP`
- `MOG_ALARM`
- `ANOMALOUS_PATTERN`

## 18. Data quality

Ingestion should calculate:
```
row_count
missing_count_by_field
duplicate_timestamp_count
timestamp_gap_statistics
out_of_range_count
parse_error_count
source_file
ingestion_timestamp
schema_version
```

Recommended metadata:
- `data_quality_score`
- `is_duplicate`
- `is_missing_critical`
- `source_name`
- `schema_version`

## 19. Source mapping

| Source column | Canonical field |
|---|---|
| `DeviceTimeStamp` | `timestamp` |
| `VL1` | `phase_voltage_l1` |
| `VL2` | `phase_voltage_l2` |
| `VL3` | `phase_voltage_l3` |
| `IL1` | `current_l1` |
| `IL2` | `current_l2` |
| `IL3` | `current_l3` |
| `INUT` | `neutral_current` |
| `OTI` | `oil_temperature` |
| `WTI` | `winding_temperature` |
| `ATI` | `ambient_temperature` |
| `OLI` | `oil_level` |
| `OTI_A` | `oil_temp_alarm` |
| `OTI_T` | `oil_temp_trip` |
| `MOG_A` | `magnetic_oil_gauge_alarm` |
| `PFL1` | `power_factor_l1` |
| `PFL2` | `power_factor_l2` |
| `PFL3` | `power_factor_l3` |
| source total active power | `active_power_total` |
| source total apparent power | `apparent_power_total` |
| source total reactive power | `reactive_power_total` |
| source cumulative energy | `energy_kwh` |

### Explicitly excluded source fields
```
VL12
VL23
VL31
```

## 20. Ownership

### Person 1 — ML + Digital Twin / Team Lead
Owns schema, adapters, features, thermal model, anomaly detection, Health Index, fault model, evaluation and ML integration.

### Person 2 — Backend + Database
Owns PostgreSQL, FastAPI, ingestion, database models/migrations, APIs, validation and persistence of ML outputs.

### Person 3 — Frontend + Dashboard
Owns Streamlit/Plotly UX, monitoring cards, trends, Health Index, alerts, recommendations, historical views and demo presentation.

### Person 4 — Simulator + DevOps
Owns canonical synthetic data, replay, fault injection, MQTT/live simulation, Docker/Compose, testing and deployment/runbook.

## 21. Versioning

Current version: **1.0.0**

- MAJOR = breaking field meaning/name/type changes.
- MINOR = backward-compatible fields.
- PATCH = clarification/documentation only.

Model artifacts must record:
```
schema_version
feature_version
model_version
training_dataset_version
training_date
```

## 22. Non-negotiable implementation boundary

**Raw data → Adapter → Canonical telemetry → Validation → Feature engineering → Twin/ML → Derived analytics → API → Dashboard**

No team member should bypass the canonical layer by importing another team's internal dataframe, database table, or UI-specific field names.
