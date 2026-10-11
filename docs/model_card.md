# Model Card: Transformer Digital Twin & Diagnostics Engine

**Release Version:** `v1.0.0` (Release Candidate)  
**Model Family:** Physics-Informed Digital Twin, Quantile Anomaly Detector, 6-Pillar Composite Health Index, Advisory Maintenance Engine, and Gated Proxy Classifier  
**Date:** 2026-10-09  
**License / Policy:** PowerNext Track 2 Academic / Competition Evaluation  
**Author / Maintainer:** Person 1 — ML + Digital Twin / Team Lead  
**Associated Contracts:** `dataschema.md` v1.0.0, `mlcontract.md` v1.0.0, `docs/methodology.md` v1.0.0, `data/processed/release_manifest.json`  

---

## 1. Intended Use & Scope

### 1.1 Intended Applications
- Real-time thermodynamic top-oil tracking and residual calculation on medium-voltage distribution transformers.
- Multivariate statistical anomaly detection identifying phase unbalance, overloads, and cooling divergence.
- Multi-pillar operational health indexing and transparent condition degradation tracking.
- Automated advisory prescriptive maintenance recommendations to guide human field technicians.
- Offline causal simulation and deterministic historical telemetry replay for grid operator training.

### 1.2 Out-of-Scope & Prohibited Uses
- **Autonomous Grid Control:** Emitting automated circuit-breaker trip commands, load-shedding directives, or tap-changer commands without human supervision.
- **Physical Equipment Certification:** Claiming statutory adherence, warranty validation, or CPRI certification without on-site calibrated instrumentation.
- **Remaining Useful Life (RUL) Claims:** Estimating remaining asset lifetime in years or percent without verified thermal-paper degradation or DGA history.
- **Uncalibrated Failure Predictions:** Using proxy onset probability as confirmed equipment breakdown likelihood.

---

## 2. Model Architecture & Pipeline Flow

The unified intelligence pipeline integrates five analytical stages into an immutable, stateful evaluation:

```
[Canonical Telemetry] ──> [Feature Pipeline] ──> [Thermal Twin ODE]
                                                     │ (r_t residual)
                                                     ▼
                                            [Anomaly Detector]
                                                     │ (anomaly_score, flags)
                                                     ▼
                                            [Health Index Engine]
                                                     │ (health_index, pillars)
                                                     ▼
                                            [Maintenance Engine]
                                                     │ (priority, recommendation)
                                                     ▼
                                            [Proxy Classifier]
                                                     │ (GATED: fault_risk = null)
                                                     ▼
                                            [Unified API Output]
```

---

## 3. Training & Evaluation Data Provenance

### 3.1 Dataset Accounting
- **Raw Telemetry Source:** Public Kaggle Distributed Transformer Monitoring Dataset (Assets: `TX-001`).
- **Telemetry Volume:** 20,024 15-minute observations spanning `2019-06-25 12:39:00` to `2020-04-14 00:30:00`.
- **Chronological Split Boundaries:**
  - **Train Split:** `2019-06-25 12:39:00` to `2019-11-23 10:30:00` ($N = 12,010$ rows; 4 purged before boundary).
  - **Validation Split:** `2019-11-23 11:45:00` to `2020-02-13 10:00:00` ($N = 4,000$ rows; 5 purged before boundary).
  - **Test Split:** `2020-02-13 11:15:00` to `2020-04-14 00:30:00` ($N = 4,005$ rows; 0 purged).
- **Data Integrity:** Zero duplicate timestamps permitted; missing fields preserved as `null`; raw phase-to-phase voltages (`VL12`, `VL23`, `VL31`) dropped; WTI excluded from continuous temperature estimation.

---

## 4. Subsystem Specifications & Released Performance

### 4.1 Thermal Twin (`thermal_twin_first_order` v1.0.0)
- **Formulation:** First-order differential ODE driven by ambient temperature and mean-squared phase current:
  $$\frac{dT}{dt} = \frac{(b_0 + b_A \cdot A(t) + b_J \cdot J(t)) - T(t)}{\tau}$$
- **Mode & Units:** `PUBLIC_EMPIRICAL` mode; `SOURCE_UNVERIFIED` temperature units (relative empirical monitoring).
- **Calibrated Parameters:** $b_0 = -1.9940$, $b_A = 1.1359$, $b_J = 5.1943 \times 10^{-5}$, $\tau = 0.4947$ h ($29.68$ min).
- **Temporal Test Performance:**
  - Test MAE: `1.17` source units
  - Test RMSE: `1.50` source units
  - Test Bias: `-0.10` source units
- **Readiness Policy:** Requires 3 observations spanning $\ge 30$ min; gaps $> 30$ min trigger `GAP_RESET`.

### 4.2 Anomaly Detector (`hybrid_anomaly_detector` v1.0.0)
- **Formulation:** Grouped quantiles $W_i$ ($Q_{0.95}$) and $C_i$ ($Q_{0.995}$) fitted on clean training reference segments.
- **Score Scale:** Anomaly score $a_t \in [0.0, 1.0]$ indicates abnormality severity, **NOT** failure probability.
- **Persistence:** $\ge 3$ consecutive readings spanning $\ge 30$ minutes with gap $\le 30$ minutes required for alert flag.
- **Heuristic Reference Budget:** $\le 1$ alert episode per 7 asset-days (~$0.143$ ep/day; evaluation reference budget, not a mandatory release threshold).
- **Authoritative Phase 06 Evaluation Results:**
  - Validation: $0$ flagged episodes ($0.0$ ep/day; $0.0$ ep/7 asset-days; heuristic budget met).
  - Test: $19$ flagged episodes ($0.488$ ep/day; ~$3.42$ ep/7 asset-days; heuristic budget exceeded; primary contributor: `HIGH_OIL_TEMP`).
  - Operational Acceptance Status: `NEEDS CONFIRMATION / CONFIGURATION REQUIRED`.

### 4.3 Composite Health Index (v1.0.0)
- **Formulation:** 6-Pillar weighted score in $[0, 100]$:
  - Thermal (30%)
  - Electrical (20%)
  - Loading (10%)
  - Oil Condition (15%)
  - Protection (20%)
  - Anomaly Margin (5%)
- **Policy Rules:** Verified trip sets $HI = 0.0$; alarm penalty deducts $40.0$ points; persistent thermal elevation caps $HI \le 20.0$.
- **Interpretation:** Instantaneous operating condition score; **NOT** asset age, survival probability, or RUL.

### 4.4 Prescriptive Maintenance Engine (v1.0.0)
- **Priorities:** `NORMAL` (routine), `WATCH` (elevated), `PLAN` (scheduled intervention), `URGENT` (immediate dispatch).
- **Trip Latching:** Active trip latches `URGENT` priority until verified de-escalation.
- **Nature:** Strictly advisory; zero control commands.

### 4.5 Proxy Forecast Classifier (`proxy_prediction` v1.0.0)
- **Target:** Next-hour proxy abnormal onset $Y_t \in \{0, 1\}$ over $(t, t + 1\,\text{hour}]$.
- **Model:** Logistic Regression ($L_2$ regularization, $C = 1.0$).
- **Features & Frozen Order:**
  1. `oil_temperature`
  2. `ambient_temperature`
  3. `temperature_slope`
  4. `current_mean`
  5. `current_imbalance_pct`
  6. `apparent_power_total`
  7. `rolling_load_mean`
  8. `thermal_residual`
- **Operational Release Status:** `INSUFFICIENT_VALIDATION`.
  - **Gating Reason:** Primary validation partition has zero positive onset instances (single-class). Probability calibration and alert threshold selection cannot be mathematically verified.
  - **Contract Output:** `fault_risk = null`, `predicted_fault = null`, `prediction_confidence = null`.

---

## 5. Quantitative Capability Matrix

| Subsystem / Capability | Release Status | Evidence & Limitation Summary |
|---|---|---|
| **Unified Pipeline Orchestration** | `AVAILABLE / VERIFIED` | Stateful, idempotent, multi-asset isolated, tested on 173 unit tests. |
| **Thermal Twin Monitoring** | `AVAILABLE` | Calibrated empirical mode; temperature units unverified; °C unconfirmed. |
| **Multivariate Anomaly Detection** | `AVAILABLE / VERIFIED` | Grouped reference quantiles active; alert rate exceeds heuristic budget. |
| **Operating Health Index** | `AVAILABLE / VERIFIED` | 6 pillars active; trip override and persistent caps tested and verified. |
| **Prescriptive Advisory Engine** | `AVAILABLE / VERIFIED` | Strictly advisory; latched trip escalation verified; zero SCADA control. |
| **Loading Percentage ($S / S_r$)** | `CONDITIONAL` | Requires verified nameplate kVA rating; outputs `null` when rating missing. |
| **Operational Fault Probability** | `INSUFFICIENT_VALIDATION` | Single-class validation partition; gated to `null`; uncalibrated. |
| **Remaining Useful Life (RUL)** | `NOT ESTIMABLE` | Needs organizer confirmation; no degradation physics or DGA support. |
| **Site Critical Physical Limits** | `CONFIGURATION REQUIRED` | Factory alarm and trip settings require physical asset certificates. |
| **Standards Compliance / Cert** | `NOT ESTABLISHED` | Standards used for ODE principles only; no CPRI certification claimed. |
| **PowerNext Final Judging Performance** | `REQUIRES REVALIDATION` | Unreleased until final organizer dataset audit and 12-step protocol. |

---

## 6. Safety, Environmental & Ethical Considerations

- **Advisory Guardrails:** The system is engineered as an operator-assist tool. Automated commands that can disconnect generation, feeders, or protection relays are architecturally prohibited.
- **Fairness & Bias:** Performance is characterized on a single public transformer (`TX-001`) in an unverified geographic and climatic domain. Models must not be deployed to diverse substation asset classes without executing the 12-Step Revalidation Protocol.
- **Carbon & Compute Footprint:** Zero GPU or cloud-training requirements. Calibration and inference run locally on standard CPU in $< 10$ seconds.

---

## 7. Future Judging Dataset Protocol

Refer to [`docs/methodology.md`](file:///c:/Users/Amitosh%20Nigam/Desktop/Transformer-digital-twin/docs/methodology.md) Section 9 for the complete 12-Step Audit and Revalidation Protocol required upon receipt of the final PowerNext Track 2 competition dataset.
