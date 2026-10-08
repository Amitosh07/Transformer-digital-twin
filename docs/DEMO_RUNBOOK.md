# Transformer Digital Twin — Operator Demo & Replay Runbook

**Document:** `docs/DEMO_RUNBOOK.md`  
**Version:** `v1.0.0` (Release Candidate)  
**Author:** Person 1 — ML + Digital Twin / Team Lead  
**Scope:** Interactive demonstration, deterministic replay, and operator walkthrough procedures  

---

## 1. Principles & Ground Rules

1. **Empirical vs Synthetic Separation:**
   - **Historical Replay:** Runs actual Kaggle SCADA telemetry through the canonical adapter and ML pipeline. Evaluates empirical physical behavior.
   - **Synthetic Simulation / Scenario Injection:** Runs deterministic synthetic records designed to test pipeline transitions, visual UI alerts, and edge cases. Synthetic results demonstrate functional behavior only; they must **never** be presented as empirical model validation.
2. **Operational Forecast Status:**
   - The operational forecast proxy risk is intentionally **UNAVAILABLE (`fault_risk = null`)** with status `INSUFFICIENT_VALIDATION`. The runbook demonstrates transparent reporting of this limitation to operators.
3. **Strictly Advisory Guidance:**
   - All maintenance priorities (`NORMAL`, `WATCH`, `PLAN`, `URGENT`) and recommendations are advisory for dispatch personnel. No automated breaker control or SCADA switching is executed.

---

## 2. 6-Stage Golden Path Demonstration

Execute the canonical demonstration sequence via `ml/tests/smoke_e2e.py` or the interactive web studio:

```bash
python -m ml.tests.smoke_e2e
```

### Stage 1: Healthy Ready Reference (Nominal Baseline)
- **Scenario:** Normal operating load ($30\text{ kVA}$ on $100\text{ kVA}$ unit), ambient temperature $25^\circ\text{C}$, oil temperature $35^\circ$, balanced phase currents ($10\text{ A}$ each), unity power factor, zero alarms.
- **Expected Pipeline Output:**
  - `inference_status`: `"HEALTHY"`
  - `loading_percent`: `30.0%`
  - `thermal_readiness`: `"INITIALIZING"` $\to$ `"READY"`
  - `anomaly_score`: `0.0`
  - `anomaly_flag`: `False`
  - `health_index`: `100.0`
  - `maintenance_priority`: `"NORMAL"`
  - `fault_risk`: `null` (Metadata status: `INSUFFICIENT_VALIDATION`)
  - `reason_codes`: `[]`

### Stage 2: Increased Load with Lagged Thermal Response
- **Scenario:** Load ramps up to $90\text{ kVA}$ ($30\text{ A}$ per phase). Oil temperature remains initially at $35^\circ$ due to thermal inertia.
- **Expected Pipeline Output:**
  - `loading_percent`: `90.0%`
  - `thermal_model_temperature`: Rises toward steady-state ($\approx 31.6^\circ$ forcing)
  - `thermal_residual`: $r_t \approx +3.4$ source units
  - `anomaly_score`: Within warning margin
  - `health_index`: $100.0$ (transient heating within thermal time constant)
  - `maintenance_priority`: `"NORMAL"`

### Stage 3: Persistent Thermal Divergence (Cooling Impairment)
- **Scenario:** Load maintained at $90\text{ kVA}$, but oil temperature reaches $80^\circ$ for $\ge 45$ minutes while physical model expects $\approx 50^\circ$ under current ambient and load conditions.
- **Expected Pipeline Output:**
  - `thermal_residual`: $r_t \approx +30.0$ source units (severe divergence)
  - `anomaly_score`: $1.0$ (critical threshold exceeded)
  - `anomaly_flag`: `True` (temporal persistence $\ge 30$ min met)
  - `health_index`: Depressed ($HI \le 20.0$ due to persistent-condition cap)
  - `maintenance_priority`: `"PLAN"`
  - `maintenance_recommendation`: `"Verify cooling, ventilation, and load distribution for sustained thermal elevation."`

### Stage 4: Unreleased Operational Proxy Risk View
- **Scenario:** Reviewing predictive risk during elevated divergence.
- **Expected Pipeline Output:**
  - `fault_risk`: `null`
  - `predicted_fault`: `null`
  - `prediction_confidence`: `null`
  - `metadata.forecast_operational_status`: `"INSUFFICIENT_VALIDATION"`
  - **Operator Explainer:** Informs the dispatcher that the next-hour proxy model is not operationally released because the primary validation split lacked positive onset events. Transparently avoids false confidence.

### Stage 5: Diagnostic Evidence & Source-Unit Qualification
- **Scenario:** Deep inspection of active reason codes and health pillars.
- **Expected Pipeline Output:**
  - `reason_codes`: `["HIGH_OIL_TEMP"]`
  - `metadata.reason_descriptions`: `{"HIGH_OIL_TEMP": "High oil indicator (source units)"}`
  - **Operator Note:** Because physical sensor units are unverified (`SOURCE_UNVERIFIED`), the UI qualifies this as a high oil indicator rather than a confirmed physical temperature breach.

### Stage 6: Advisory Maintenance Recommendation
- **Scenario:** Dispatch guidance generated from corroborated multi-pillar evidence.
- **Expected Pipeline Output:**
  - `maintenance_priority`: `"PLAN"`
  - `maintenance_recommendation`: Clear descriptive guidance directing technicians to check radiators, fans, and oil level before catastrophic tripping.
  - Zero SCADA commands emitted.

---

## 3. Edge Case Scenarios

| Edge Case | Test Stimulus | Expected System Response |
|---|---|---|
| **A. Verified Trip** | Ingestion of `oil_temp_trip = 1` | `health_index = 0.0`, `maintenance_priority = "URGENT"`, `maintenance_trip_latched = True`. |
| **B. Missing Rating** | Asset without registered `rated_power_kva` | `loading_percent = null`, `apparent_power_utilization = null`. Gracefully avoids fictitious loading calculations. |
| **C. Long Telemetry Gap** | Elapsed time $\Delta t > 30$ minutes | `thermal_readiness = "GAP_RESET"`, `thermal_residual = null`. Resets persistence and restarts warm-up. |
| **D. Sparse / Partial Data** | Only `oil_temperature` supplied; electrical missing | `inference_status = "INSUFFICIENT_DATA"`, `maintenance_priority = "WATCH"`. Missing features enumerated. |
| **E. Out-of-Order / Late Rows** | Observation with $t < t_{\text{last}}$ | `inference_status = "REJECTED_LATE_OBSERVATION"`. Rejects integration into forward state. |

---

## 4. Historical Replay Instructions

To replay the public Kaggle dataset in timestamp order:

```bash
# Terminal execution
python -m ml.adaptors.data_adapter --input-dir data/raw --output-csv data/processed/canonical_telemetry.csv
```

To run deterministic batch processing through the unified pipeline:

```python
from ml.pipeline import UnifiedMLPipeline, AssetConfig
import pandas as pd

df = pd.read_csv("data/processed/canonical_telemetry.csv")
records = df.head(100).to_dict(orient="records")

pipeline = UnifiedMLPipeline()
pipeline.register_asset(AssetConfig(transformer_id="TX-001", rated_power_kva=100.0))
results = pipeline.process_batch(records)
print(f"Processed {len(results)} records successfully.")
```
