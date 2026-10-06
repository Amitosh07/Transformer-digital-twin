# Transformer Digital Twin — ML Contract

**Repository:** `Amitosh07/Transformer-digital-twin`  
**Owner:** Person 1 — ML + Digital Twin / Team Lead  
**Status:** Development contract  
**Schema dependency:** `dataschema.md` v1.0.0

---

## 1. Purpose

This document defines the machine-learning and Digital Twin interface used by the transformer monitoring system.

It specifies:

- what the ML/Twin layer receives
- which features are created
- what each analytical component produces
- output field names and types
- model/version metadata
- missing-data behavior
- integration expectations for the backend
- rules for retraining when new PowerNext/CPRI data arrives

`dataschema.md` defines the meaning of the underlying telemetry fields. This document defines how the ML/Twin layer consumes those fields and produces analytical outputs.

---

## 2. ML/Twin Pipeline

```text
Canonical TransformerRecord
            ↓
       Data validation
            ↓
     Feature engineering
            ↓
   ┌────────┼───────────┐
   ↓        ↓           ↓
Thermal   Anomaly     Fault-risk
 Model     Model        Model
   │        │           │
   └────────┼───────────┘
            ↓
       Health Index
            ↓
 Maintenance Engine
            ↓
      ML/Twin Result
```

---

## 3. Input Contract

The ML/Twin layer receives canonical fields only.

It must never depend directly on Kaggle or PowerNext source column names.

### 3.1 Core input fields

```text
transformer_id
timestamp

phase_voltage_l1
phase_voltage_l2
phase_voltage_l3

current_l1
current_l2
current_l3
neutral_current

oil_temperature
winding_temperature
ambient_temperature
oil_level

oil_temp_alarm
oil_temp_trip
magnetic_oil_gauge_alarm

active_power_total
apparent_power_total
reactive_power_total
energy_kwh

power_factor_l1
power_factor_l2
power_factor_l3
```

Asset configuration may additionally provide:

```text
rated_power_kva
rated_voltage_hv
rated_voltage_lv
rated_current_a
cooling_class
oil_type
```

These are configuration/asset inputs rather than ordinary telemetry.

---

## 4. Feature Engineering Contract

The feature pipeline may derive additional features from canonical telemetry.

### 4.1 Electrical features

```text
current_mean
current_max
current_min
current_imbalance_pct

voltage_mean
voltage_imbalance_pct

neutral_current_magnitude

active_power_demand
apparent_power_utilization
power_factor_mean
power_factor_deviation
```

### 4.2 Thermal features

```text
oil_temperature_level
ambient_temperature_level
ambient_to_oil_delta

oil_temperature_rate
temperature_rolling_mean
temperature_rolling_std
temperature_slope

thermal_residual
```

`thermal_residual` is:

```text
observed_temperature - thermal_model_temperature
```

### 4.3 Oil features

```text
oil_level_deviation
oil_level_rate
oil_level_rolling_mean
```

### 4.4 Temporal features

```text
rolling_load_mean
rolling_load_std
time_since_last_alarm
time_since_last_trip
```

The exact feature list used by a trained model must be versioned.

---

## 5. Model Feature Vector

Every trained model artifact must explicitly store:

```text
feature_version
feature_names
feature_order
preprocessing_version
```

Example:

```json
{
  "feature_version": "1.0.0",
  "feature_names": [
    "current_imbalance_pct",
    "voltage_imbalance_pct",
    "apparent_power_utilization",
    "power_factor_deviation",
    "oil_temperature_level",
    "ambient_to_oil_delta",
    "oil_temperature_rate",
    "thermal_residual",
    "oil_level_deviation"
  ]
}
```

The order must remain identical during training and inference.

---

## 6. Thermal Model Contract

### Input

```text
loading_percent
ambient_temperature
historical thermal state
transformer configuration where available
```

### Output

```text
thermal_model_temperature
thermal_residual
thermal_state
```

Example:

```json
{
  "thermal_model_temperature": 57.4,
  "thermal_residual": 6.8,
  "thermal_state": "ELEVATED"
}
```

The thermal model must document its assumptions and verified units.

---

## 7. Anomaly Detection Contract

### Input

Canonical telemetry + engineered features.

### Output

```text
anomaly_score
anomaly_flag
reason_codes[]
```

Example:

```json
{
  "anomaly_score": 0.82,
  "anomaly_flag": true,
  "reason_codes": [
    "RAPID_TEMP_RISE",
    "CURRENT_IMBALANCE"
  ]
}
```

`anomaly_score` must use a documented scale.

Current project convention:

```text
0 = least abnormal
1 = most abnormal
```

The threshold used for `anomaly_flag` must be configurable and versioned.

---

## 8. Health Index Contract

### Input

```text
thermal_condition
electrical_condition
loading_condition
oil_condition
alarm_condition
anomaly_condition
```

### Output

```text
health_index
health_components
health_reason_codes[]
```

Health Index range:

```text
100 = healthiest
0   = critical
```

Example:

```json
{
  "health_index": 68.4,
  "health_components": {
    "thermal": 52,
    "electrical": 76,
    "loading": 61,
    "oil": 81,
    "alarm": 90,
    "anomaly": 55
  },
  "health_reason_codes": [
    "HIGH_OIL_TEMP",
    "CURRENT_IMBALANCE"
  ]
}
```

The weighting methodology must be documented in `docs/methodology.md`.

---

## 9. Fault Prediction Contract

The baseline public-dataset implementation is a proxy/baseline prediction task unless confirmed physical fault labels become available.

### Input

The exact model-specific feature vector defined by:

```text
feature_version
model_version
```

### Output

```text
fault_risk
predicted_fault
prediction_confidence
```

Example:

```json
{
  "fault_risk": 0.67,
  "predicted_fault": "THERMAL_STRESS",
  "prediction_confidence": 0.81
}
```

The meaning of `fault_risk` must be documented for the selected target.

The model must never claim a confirmed physical fault when the training target is only an alarm/trip proxy.

---

## 10. Maintenance Recommendation Contract

### Input

```text
health_index
anomaly_score
anomaly_flag
fault_risk
predicted_fault
loading_percent
thermal condition
alarm/trip states
oil condition
trend severity
```

### Output

```text
maintenance_priority
maintenance_recommendation
reason_codes[]
```

Allowed priorities:

```text
NORMAL
WATCH
PLAN
URGENT
```

Example:

```json
{
  "maintenance_priority": "PLAN",
  "maintenance_recommendation":
    "Inspect cooling performance and investigate sustained thermal rise.",
  "reason_codes": [
    "HIGH_OIL_TEMP",
    "RAPID_TEMP_RISE"
  ]
}
```

---

## 11. Complete ML/Twin Response

The backend should receive one stable analytical response.

Example:

```json
{
  "transformer_id": "TX-001",
  "timestamp": "2026-10-06T11:30:00Z",

  "thermal_model_temperature": 57.4,
  "thermal_residual": 6.8,

  "anomaly_score": 0.82,
  "anomaly_flag": true,

  "health_index": 68.4,

  "fault_risk": 0.67,
  "predicted_fault": "THERMAL_STRESS",
  "prediction_confidence": 0.81,

  "maintenance_priority": "PLAN",
  "maintenance_recommendation":
    "Inspect cooling performance and investigate sustained thermal rise.",

  "reason_codes": [
    "HIGH_OIL_TEMP",
    "RAPID_TEMP_RISE",
    "CURRENT_IMBALANCE"
  ],

  "schema_version": "1.0.0",
  "feature_version": "1.0.0",
  "model_version": "1.0.0"
}
```

Person 2 should be able to use this contract without knowing anything about the internal Python model implementation.

---

## 12. Missing Data Rules

Missing values must not automatically become zero.

The ML layer must distinguish:

```text
0
```

from:

```text
missing
```

For missing critical model features, the inference layer must either:

1. use the documented preprocessing/imputation strategy, or
2. return an explicit insufficient-data status.

Example:

```json
{
  "inference_status": "INSUFFICIENT_DATA",
  "missing_features": [
    "oil_temperature"
  ]
}
```

The model must never silently produce a prediction from invalid input.

---

## 13. New PowerNext / CPRI Dataset Contract

When a new dataset is provided:

```text
New raw columns
       ↓
Source adapter
       ↓
Canonical schema
       ↓
Feature pipeline
       ↓
Existing model
```

If only variable names or units change:

```text
Mapping / unit conversion
```

may be sufficient.

If the new dataset introduces useful new variables:

```text
Canonical schema extension
       ↓
Feature pipeline update
       ↓
Feature version increment
       ↓
Retraining if required
       ↓
Model version increment
```

If a model-required feature is completely unavailable:

```text
Do not invent the feature.

Use:
- an alternate model, or
- a retrained model using available features.
```

---

## 14. Model Metadata

Every model artifact must contain:

```text
schema_version
feature_version
model_version
training_dataset_version
training_date
target_definition
feature_names
feature_order
preprocessing_version
evaluation_metrics
```

Example:

```json
{
  "schema_version": "1.0.0",
  "feature_version": "1.2.0",
  "model_version": "0.3.0",
  "training_dataset_version": "kaggle-v1",
  "training_date": "2026-10-06",
  "target_definition": "oil_temp_alarm"
}
```

---

## 15. Data Leakage Rules

Features must only use information that would have been available at prediction time.

When evaluating a future/next-state prediction task:

```text
Past → train
Middle → validation
Latest → test
```

Randomly mixing future and past observations must be avoided when it creates temporal leakage.

Target-derived information must never be used as an input feature for the same target.

---

## 16. Integration Ownership

### Person 1 owns

```text
ML input definition
Feature engineering
Thermal model
Anomaly model
Health Index
Fault model
Maintenance logic
Model artifacts
ML contract
```

### Person 2 consumes

```text
ML/Twin output contract
```

and exposes it through FastAPI.

### Person 3 consumes

```text
ML-derived API fields
```

for visualization.

### Person 4 produces

```text
Canonical telemetry
```

and controlled fault scenarios for testing.

---

## 17. Contract Versioning

ML contract changes follow:

```text
MAJOR
Breaking input/output changes

MINOR
Backward-compatible additions

PATCH
Documentation/clarification only
```

Any breaking model/API integration change must be communicated before merging to `develop`.

---

## 18. Golden Rule

```text
Raw dataset
    ↓
Source adapter
    ↓
Canonical schema
    ↓
Feature engineering
    ↓
ML/Twin
    ↓
Stable analytical output
    ↓
Backend API
    ↓
Dashboard
```

No downstream module should depend on raw dataset column names or internal ML implementation details.
