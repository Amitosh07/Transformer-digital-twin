# ML + Digital Twin

## Owner

**Person 1 — ML + Digital Twin / Team Lead**

This folder contains the machine-learning, Digital Twin, condition-assessment, anomaly-detection, fault-risk, Health Index, and maintenance intelligence components.

---

## 1. Mission

Build the intelligence layer of the Transformer Digital Twin.

The ML/Twin layer must transform canonical transformer telemetry into:

- Transformer thermal state
- Anomaly detection
- Transformer Health Index
- Fault risk / baseline fault prediction
- Maintenance priority
- Maintenance recommendation
- Explainable reason codes

The Digital Twin should not be just a prediction model. It must combine transformer behavior modeling with data-driven analytics.

---

## 2. Important Documents

Before writing code, read:

```text
../dataschema.md
../mlcontract.md
../docs/
```

### `dataschema.md`

Defines the canonical fields and meanings used across the entire project.

### `mlcontract.md`

Defines:

- ML inputs
- engineered features
- ML outputs
- Health Index contract
- anomaly contract
- fault-prediction contract
- maintenance contract
- model/version metadata
- retraining rules

Do not bypass these contracts.

---

## 3. Data Flow

```text
Raw Dataset
     ↓
Source Adapter
     ↓
Canonical Telemetry
     ↓
Data Validation
     ↓
Feature Engineering
     ↓
Digital Twin / Thermal Model
     ↓
Anomaly Detection
     ↓
Health Index
     ↓
Fault Risk / Prediction
     ↓
Maintenance Recommendation
     ↓
Stable ML/Twin Output
```

---

## 4. Baseline Dataset

The initial baseline is the public Kaggle Distributed Transformer Monitoring dataset.

Source files:

```text
CurrentVoltage.csv
Overview.csv
Power.csv
PowerFactor.csv
TotalPower.csv
```

The adapter must normalize the raw files into the canonical schema.

Raw Kaggle column names must not leak into downstream ML code.

---

## 5. Mandatory Exclusion

The following source variables are explicitly excluded:

```text
VL12
VL23
VL31
```

Do not use them in:

- feature engineering
- ML models
- Digital Twin calculations
- database contracts
- APIs
- dashboard outputs

---

## 6. Main Responsibilities

### 6.1 Data Adapter

Build a source adapter that:

- loads all five CSV files
- aligns records using `DeviceTimeStamp`
- converts source names to canonical names
- validates data types
- identifies duplicate timestamps
- identifies missing values
- validates joins
- produces canonical telemetry

Future PowerNext/CPRI datasets must be supported through additional adapters rather than rewriting the ML system.

---

### 6.2 Feature Engineering

Build reusable feature-generation functions.

Initial feature families:

#### Electrical

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

#### Thermal

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

#### Oil

```text
oil_level_deviation
oil_level_rate
oil_level_rolling_mean
```

#### Temporal

```text
rolling_load_mean
rolling_load_std
time_since_last_alarm
time_since_last_trip
```

The exact feature set used by each trained model must be versioned.

---

## 7. Digital Twin / Thermal Model

Build an interpretable thermal model using:

```text
loading
ambient temperature
historical thermal state
transformer configuration where available
```

The model should produce:

```text
thermal_model_temperature
thermal_residual
thermal_state
```

The primary Digital Twin demonstration should show:

```text
Observed Temperature
        vs
Model/Expected Temperature
        ↓
Thermal Residual
        ↓
Condition Assessment
```

Document all assumptions and units.

Do not invent engineering units that are not verified in the source data.

---

## 8. Anomaly Detection

Implement a baseline anomaly detector.

Required outputs:

```text
anomaly_score
anomaly_flag
reason_codes[]
```

Current project convention:

```text
0 = least abnormal
1 = most abnormal
```

The anomaly threshold must be configurable and versioned.

Candidate evidence includes:

- current imbalance
- voltage imbalance
- neutral current
- loading
- apparent-power utilization
- power-factor deviation
- oil temperature
- temperature rate of change
- ambient-to-oil temperature difference
- oil-level trend
- rolling statistics
- alarm history

---

## 9. Health Index

Implement an explainable:

```text
Health Index = 0–100
```

Where:

```text
100 = healthiest
0   = critical
```

Recommended components:

```text
thermal_condition
electrical_condition
loading_condition
oil_condition
alarm_condition
anomaly_condition
```

The system must expose both:

```text
health_index
```

and the contributing component scores/reasons.

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
  }
}
```

Weights and thresholds must be documented.

---

## 10. Fault Prediction

For the public baseline, use a clearly defined proxy/baseline target unless confirmed physical fault labels are available.

Possible baseline targets:

```text
oil_temp_alarm
oil_temp_trip
magnetic_oil_gauge_alarm
condition_alert
```

Do not claim that a proxy alarm label represents a confirmed physical transformer failure.

The future PowerNext/CPRI dataset may contain better confirmed fault labels.

---

## 11. Maintenance Recommendation Engine

Combine:

```text
health_index
anomaly_score
anomaly_flag
fault_risk
predicted_fault
loading
thermal condition
alarm/trip states
oil condition
trend severity
```

and produce:

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

Example reason codes:

```text
HIGH_OIL_TEMP
RAPID_TEMP_RISE
OVERLOAD
CURRENT_IMBALANCE
VOLTAGE_IMBALANCE
LOW_OIL_LEVEL
OIL_TEMP_ALARM
OIL_TEMP_TRIP
MOG_ALARM
ANOMALOUS_PATTERN
```

---

## 12. Model Evaluation

Use time-aware evaluation where the task is temporal.

Prefer:

```text
Older data  → Train
Middle data → Validation
Latest data → Test
```

Avoid random splitting when it causes temporal leakage.

Evaluate using appropriate metrics such as:

```text
Precision
Recall
F1
Confusion Matrix
PR-AUC where applicable
False-negative behavior
Calibration / risk interpretation
```

Document:

- dataset version
- target definition
- feature version
- model version
- preprocessing version
- training date
- evaluation metrics

---

## 13. Model Artifact Requirements

Every trained model must preserve:

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

The feature order used during training must be identical during inference.

---

## 14. Output Contract

The backend must receive a stable analytical response.

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
  "maintenance_recommendation": "Inspect cooling performance and investigate sustained thermal rise.",

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

Person 2 will use this interface.

---

## 15. Missing Data

Never silently convert missing values to zero.

Distinguish:

```text
0
```

from:

```text
missing
```

For missing critical features, either use the documented preprocessing strategy or return:

```text
INSUFFICIENT_DATA
```

with the missing feature list.

---

## 16. Future PowerNext / CPRI Data

When new organizer data arrives:

```text
PowerNext Raw Dataset
        ↓
PowerNext Adapter
        ↓
Canonical Schema
        ↓
Feature Pipeline
        ↓
Existing Model
```

Different variable names:

```text
IR → current_l1
IY → current_l2
IB → current_l3
```

should be handled by the adapter.

Do not rewrite the ML layer just because raw names changed.

If new useful variables are introduced:

```text
Schema extension
      ↓
Feature update
      ↓
Feature version change
      ↓
Retraining if required
      ↓
Model version change
```

Never invent missing variables.

---

## 17. Deliverables

This folder must eventually contain:

- Source/data adapters
- Feature engineering pipeline
- Thermal Digital Twin
- Anomaly detector
- Health Index engine
- Fault-risk/prediction model
- Maintenance recommendation engine
- Model artifacts
- Tests
- ML methodology documentation
- Integration-ready ML interface

---

## 18. Definition of Done

The ML work is considered integrated when:

```text
Public raw data
      ↓
Adapter
      ↓
Canonical record
      ↓
Validation
      ↓
Feature pipeline
      ↓
Digital Twin / ML
      ↓
Stable analytics result
```

works without downstream modules knowing the original CSV column names.

---

## 19. Ownership

Person 1 owns:

- ML
- Digital Twin
- Data adapters
- Feature engineering
- Thermal model
- Anomaly detection
- Health Index
- Fault prediction
- Maintenance engine
- Model evaluation
- ML contract
- ML methodology
- Integration coordination

Do not directly modify another team's internal implementation.

Use shared contracts at module boundaries.
