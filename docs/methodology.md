# Transformer Digital Twin — Technical Methodology Specification

**Repository:** `Amitosh07/Transformer-digital-twin`  
**Phase:** 08 — Model Metadata and Release  
**Status:** Released Candidate Specification (v1.0.0)  
**Authoritative References:** `docs/implementation/AUDIT_PLAN.md`, `08_MODEL_METADATA_AND_RELEASE.md`, `dataschema.md` v1.0.0, `mlcontract.md` v1.0.0  

---

## 1. Executive Summary & Architecture Overview

The Transformer Digital Twin intelligence layer converts multivariate canonical SCADA telemetry into physics-guided diagnostics, anomaly detection, composite condition indices, and prescriptive maintenance recommendations.

The architecture strictly follows a unidirectional, causal data flow:

```
Raw Telemetry CSVs / Stream
            │
            ▼
┌────────────────────────────────────────┐
│  Phase 00: Canonical Data Adapter      │  Zero silent zero-fills, time validation,
│  (dataschema.md v1.0.0)                │  drop raw phase-to-phase fields (VL12, VL23, VL31)
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  Phase 00: Causal Feature Pipeline     │  No look-ahead; continuity gap enforcement (30 min)
│  (FEATURE_VERSION = 1.0.0)             │  WTI excluded from continuous temperature features
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  Phase 01: Thermal Digital Twin ODE    │  First-order dynamic ODE; empirical calibrated mode
│  (PUBLIC_EMPIRICAL, SOURCE_UNVERIFIED) │  Warm-up & gap-reset tracking; signed residual r_t
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  Phase 02: Hybrid Anomaly Detector     │  Quantile references (Q95/Q99.5) + engineering limits
│  (Score ∈ [0, 1], Severity Flag)      │  Temporal persistence (3 readings ≥ 30 min)
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  Phase 03: Operating Health Index (HI) │  6-Pillar weighted composite (sum weights = 1.0)
│  (Score ∈ [0, 100], Coverage Ratio)    │  Persistent cap (20.0), trip override (HI = 0.0)
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  Phase 04: Experimental Proxy Forecast │  Next-hour proxy onset model
│  (INSUFFICIENT_VALIDATION Gate)        │  Operationally GATED to null (unreleased)
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  Phase 05: Prescriptive Maintenance    │  Advisory priorities (NORMAL, WATCH, PLAN, URGENT)
│  (Advisory Operator Action Engine)     │  Latched trip escalation; zero autonomous control
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  Phase 07: Unified Pipeline Result     │  Stable immutable dictionary contract;
│  (PythonMLTwinClient API Contract)     │  Idempotent replay; isolated state per asset
└────────────────────────────────────────┘
```

---

## 2. Phase 00: Ingestion & Feature Engineering

### 2.1 Excluded & Guarded Fields
- **Phase-to-phase voltages (`VL12`, `VL23`, `VL31`):** Completely excluded per `dataschema.md` principle 7. Only phase-to-neutral voltages (`phase_voltage_l1`, `phase_voltage_l2`, `phase_voltage_l3`) are ingested.
- **Winding Temperature Indicator (`winding_temperature` / WTI):** Excluded from continuous thermal modeling. In the public dataset, WTI exhibits discrete switch/gauge characteristics and must not be treated as a true continuous thermodynamic temperature.
- **Missing Telemetry Policy:** Missing values remain `null` / `NaN`. They are never imputed as `0.0`. If critical fields are absent, the inference engine marks the record as `INSUFFICIENT_DATA`.

### 2.2 Continuity Gap & Three-Phase Symmetry
- Telemetry intervals exceeding `30.0 minutes` (`DEFAULT_GAP_LIMIT_MINUTES`) suppress rate calculations ($\Delta T / \Delta t$) because constant-load linear assumptions do not hold across unobserved intervals.
- Three-phase averages and imbalance percentages require all three valid phases; partial availability produces `NaN`, preventing fabricated "zero imbalance".

---

## 3. Phase 01: Thermal Digital Twin

### 3.1 Thermodynamic Formulation
The top-oil thermal model implements a continuous first-order differential equation driven by ambient temperature and ohmic loading:

$$\frac{dT}{dt} = \frac{F(t) - T(t)}{\tau}$$

Where the thermal forcing function $F(t)$ is defined by:

$$F(t) = b_0 + b_A \cdot A(t) + b_J \cdot J(t)$$

- $T(t)$: Top-oil temperature indicator (source units)
- $A(t)$: Ambient temperature indicator (source units)
- $J(t)$: Mean squared phase current: $J = \frac{1}{3} (I_{L1}^2 + I_{L2}^2 + I_{L3}^2)$ in $\text{A}^2$
- $\tau$: Thermal time constant in hours

### 3.2 Discrete-Time Analytical Integration
For discrete observations with elapsed interval $\Delta t$ hours:

$$\hat{T}_t = T_{t-1} \cdot e^{-\Delta t / \tau} + F_t \cdot \left(1 - e^{-\Delta t / \tau}\right)$$

### 3.3 Calibrated Parameter Artifact (`thermal_twin_params.json`)
Calibrated on clean training split reference data ($N = 8,434$ observations):

| Parameter | Calibrated Value | Unit | Interpretation |
|---|---|---|---|
| $b_0$ | `-1.994021` | source unit | Empirical baseline intercept |
| $b_A$ | `1.135926` | dimensionless | Ambient coupling coefficient |
| $b_J$ | `5.194284e-05` | source unit / $\text{A}^2$ | Ohmic loss heating coefficient |
| $\tau$ | `0.494686` | hours ($29.68$ min) | Effective top-oil thermal time constant |
| $\Delta t_{\text{gap}}$ | `0.5` | hours ($30$ min) | Continuity gap threshold |
| $t_{\text{warmup}}$ | `1.4819` | hours ($3\tau$) | Warm-up duration required |

### 3.4 Signed Thermal Residual & Readiness
The signed residual is defined as:

$$r_t = T_t - \hat{T}_t$$

- **Positive residual ($r_t > 0$):** Observed temperature is elevated above physical model expectation (potential cooling impairment, internal degradation, or ambient blockage).
- **Negative residual ($r_t < 0$):** Model mismatch (e.g. over-prediction during sudden load drops).
- **Thermal Readiness States:**
  - `INITIALIZING`: Awaiting 3 observations spanning $\ge 30$ minutes.
  - `READY`: Warm-up complete; residual is prospective and active.
  - `GAP_RESET`: Gap $> 30$ minutes detected; state reset to current observed temperature; warm-up restarts.

---

## 4. Phase 02: Hybrid Anomaly Detection

### 4.1 Scoring Mechanism
The anomaly engine combines statistical reference quantiles with deterministic engineering protection limits. For each signal $x_i$, severity $s_i \in [0, 1]$ is evaluated against warning threshold $W_i$ and critical threshold $C_i$:

$$s_i(x_i) = \begin{cases} 
0.0, & x_i \le W_i \\
\frac{x_i - W_i}{C_i - W_i}, & W_i < x_i < C_i \\
1.0, & x_i \ge C_i 
\end{cases}$$

### 4.2 Fitted Quantile Reference Thresholds (`anomaly_detector_params.json`)
Fitted on clean training split segments ($N_{\text{clean}} = 8,434$):

| Signal Name | Warning $W$ (Q95) | Critical $C$ (Q99.5) | Unit | Direction |
|---|---|---|---|---|
| `current_imbalance_pct` | 72.98% | 300.0% | % | Upper |
| `voltage_imbalance_pct` | 1.75% | 2.57% | % | Upper |
| `neutral_current_magnitude` | 51.40 A | 71.08 A | A | Upper |
| `apparent_power_total` | 101.51 kVA | 118.02 kVA | kVA | Upper |
| `power_factor_deviation` | 0.0400 | 0.0533 | dimensionless | Upper |
| `oil_temperature` | 40.00 | 48.00 | source units | Upper |
| `oil_temperature_rate` | 8.00 | 20.00 | source unit/h | Upper |
| `temperature_rolling_std` | 2.08 | 14.50 | source units | Upper |
| `thermal_residual` | 4.46 | 8.06 | source units | Upper |
| `oil_level_deviation` | -2.75 | -12.75 | source units | Lower |

### 4.3 Severity & Flag Logic
- **Subsystem Severity Scores:** Grouped into `thermal`, `electrical`, `loading`, `oil`, and `protection`.
- **Composite Anomaly Score:** Maximum across active subsystem severities: $a_t = \max_j (s_j)$.
- **Anomaly Flag:** Requires temporal persistence: $a_t \ge a_{\text{on}} = 0.5$ for $\ge 3$ consecutive readings spanning $\ge 30$ minutes with gap $\le 30$ minutes. Active protection trip contacts immediately bypass persistence and set flag to `True`.

---

## 5. Phase 03: Operating Health Index (HI)

### 5.1 Formulation & Weights
The Composite Operating Health Index quantifies instantaneous operational condition on a $[0, 100]$ scale:

$$HI = \sum_{j \in \text{available}} w_j' \cdot H_j,\qquad w_j' = \frac{w_j}{\sum_{k \in \text{available}} w_k}$$

The authoritative, frozen weights ($\sum w_j = 1.0$) are:

| Subsystem Component | Weight $w_j$ | Evaluated Inputs |
|---|---|---|
| **Thermal** | `0.30` | Top-oil temperature, thermal residual, rate of rise |
| **Electrical** | `0.20` | Current imbalance, voltage imbalance, neutral current, power factor |
| **Loading** | `0.10` | Apparent power utilization ($S / S_r$ or apparent power baseline) |
| **Oil Condition** | `0.15` | Oil level indicator departure and rolling trend |
| **Protection** | `0.20` | Binary alarm contacts (OTI alarm, OTI trip, MOG alarm) |
| **Anomaly Margin** | `0.05` | Integrated multivariate anomaly severity margin ($100 \cdot (1 - a_t)$) |

### 5.2 Deterministic Safety Overrides & Caps
1. **Verified Trip Override:** Any verified active or latched `oil_temp_trip` contact clamps composite $HI = 0.0$ immediately.
2. **Protection Alarm Penalty:** Active alarm contact applies a $40$-point deduction to the protection sub-index.
3. **Persistent-Condition Cap:** If sustained thermal residual elevation or anomaly persistence is confirmed, composite $HI$ is hard-capped at $\le 20.0$, regardless of healthy electrical parameters.
4. **Coverage Threshold:** If available component weight coverage $\sum_{k} w_k < 0.60$, composite $HI$ is set to `null` with status `INSUFFICIENT_DATA`.

---

## 6. Phase 04: Experimental Proxy Fault Prediction

### 6.1 Task & Target Formulation
Due to the absence of confirmed physical tear-down or DGA fault records in the public Kaggle dataset, Phase 04 implements a **next-hour proxy onset prediction** model:

$$Y_t = \mathbb{I}\left(\text{onset in } (t, t + 1\,\text{hour}]\right)$$

Where an onset event represents the transition of telemetry into an alarm, trip, or severe threshold breach from an initially healthy baseline.

### 6.2 Model Structure & Feature Order
A regularized linear classification baseline (Logistic Regression with L2 penalty, $C = 1.0$):

$$P(Y_t = 1 \mid \mathbf{x}_t) = \sigma\left(\mathbf{w}^T \tilde{\mathbf{x}}_t + b\right)$$

The exact, frozen feature order ($\mathbf{x}_t$) and learned coefficients are:

1. `oil_temperature`: $+3.6826$
2. `ambient_temperature`: $-2.0082$
3. `temperature_slope`: $+0.0053$
4. `current_mean`: $+3.7397$
5. `current_imbalance_pct`: $-0.5620$
6. `apparent_power_total`: $-3.0489$
7. `rolling_load_mean`: $-1.9043$
8. `thermal_residual`: $+0.2499$
Intercept $b$: $-2.4148$

### 6.3 Operational Gating (`INSUFFICIENT_VALIDATION`)
- In the primary chronological split, the validation partition ($N = 4,000$ rows) contains **zero positive onset events** (single-class all-negative partition).
- Under strict temporal evaluation principles, probability calibration curves and alert threshold tuning cannot be validated without positive class support.
- Consequently, the model is gated to:
  ```json
  "fault_risk": null,
  "predicted_fault": null,
  "prediction_confidence": null,
  "inference_status": "INSUFFICIENT_VALIDATION"
  ```
- **Safety invariant:** Uncalibrated proxy risk is NEVER output as an operational failure probability.

---

## 7. Phase 05: Prescriptive Advisory Maintenance Engine

### 7.1 Priority Taxonomy
The maintenance engine assigns deterministic advisory priorities:

| Priority | Operational Definition | Primary Trigger Conditions |
|---|---|---|
| **NORMAL** | Routine scheduled inspection | $HI \ge 85$, no anomaly, no alarms |
| **WATCH** | Heightened surveillance | $70 \le HI < 85$, single-sensor departure, unconfirmed transient |
| **PLAN** | Scheduled intervention required | $HI < 70$, persistent anomaly flag, persistent thermal divergence |
| **URGENT** | Immediate dispatch / crew required | Active/latched trip contact, catastrophic oil departure, multi-alarm |

### 7.2 Safety Constraints & Non-Goals
- **Strictly Advisory:** The maintenance engine provides guidance for human operators. It does NOT emit automated SCADA breaker-open commands, relay re-closers, or control actions.
- **Trip Latching:** Once a trip contact is detected, the engine latches `URGENT` priority until an explicit clear condition or gap reset occurs.

---

## 8. Standards Provenance & Limitations

| Standard / Document | Status | Application in Project | What Remains Unverified |
|---|---|---|---|
| **IEEE C57.91-2011 / IEC 60076-7:2018** | THEORETICAL BASIS | First-order ODE formulation for top-oil temperature dynamics. | Transformer factory heat-run constants ($n, m, \Delta \theta_{or}, R$). |
| **IS 2026 (Part 7):2009** | REFERENCE LOADING GUIDE | Current Indian Standard for loading mineral oil-immersed transformers. | Operational alarm setpoints (require nameplate certificate). |
| **IS 6600:1972** | HISTORICAL REFERENCE | Withdrawn Indian Standard; used only for historical cross-check. | Superseded by IS 2026 Part 7; not used for active criteria. |
| **IS 1180 (Part 1):2014** | TEST-CONTEXT REFERENCE | Temperature-rise limits (50°C top-oil rise, 55°C winding rise). | Factory test criteria, NOT real-time SCADA trip setpoints. |
| **CPRI Standards** | PREREQUISITE | Central Power Research Institute testing protocols. | No CPRI certification or compliance claimed on public data. |

---

## 9. Future PowerNext Judging Dataset Revalidation Protocol

When the final PowerNext Track 2 organizer dataset is delivered, the system must follow this **12-Step Revalidation Protocol** before making any performance claims:

1. **Schema Verification:** Audit organizer dataset columns against canonical schema (`dataschema.md`).
2. **Unit & Semantic Verification:** Verify physical units (°C vs source units, V, A, kW).
3. **Alarm & Trip Semantics Verification:** Confirm active-high/active-low contact polarity and latching rules.
4. **Nameplate & Configuration Verification:** Extract verified rated kVA, voltages, currents, and cooling class.
5. **Scenario & Label Verification:** Audit ground-truth fault/alarm labels and onset definitions.
6. **Canonical Schema Compatibility:** Update/verify data adapter to produce canonical telemetry records.
7. **Feature Contract Compatibility:** Verify causal feature engineering without look-ahead leakage.
8. **Subsystem Parameter Revalidation:** Re-evaluate thermal ODE dynamics and statistical reference quantiles.
9. **Target & Model Retraining/Refitting:** Retrain or refit where domain shift or new verified targets require it.
10. **Fresh Chronological Time-Aware Evaluation:** Execute evaluation harness across organizer splits.
11. **Unified Pipeline Regression:** Verify latency, state isolation, and API contract compatibility.
12. **Release Manifest Update:** Regenerate release manifest, provenance hashes, and capability matrix.
