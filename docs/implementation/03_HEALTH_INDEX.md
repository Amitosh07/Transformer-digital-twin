# Phase 03 — Operating Health Index

## 1. Phase objective

Implement the established explainable 0–100 operating-condition Health Index with six components, specified weights, persistent-condition cap, protection override and honest missing coverage. It is not asset age, survival probability or remaining life.

## 2. Scope

Component scoring, weighted aggregation, partial assessment, reasons and verified trip handling. Reuse existing detector/condition evidence; do not design new thresholds or a new health methodology.

## 3. Dependencies

Depends on phase 00 validity/configuration, phase 01 thermal evidence through phase 02, and phase 02 severities/coverage. Produces health_index, components/reasons/coverage for 05–08. Blocks complete maintenance explanation. Arithmetic can be tested on fixtures independently; validate before maintenance/integration acceptance. No trained fault model dependency.

## 4. Inputs

Thermal/electrical/loading/oil severity, protection states and verification, anomaly_score, per-component validity and persistence, configured weights/cap. Loading component requires applicable rating/envelope; historical load percentile alone is not rated loading health.

## 5. Outputs

health_index in [0,100] or null, health_components with thermal/electrical/loading/oil/alarm/anomaly, health_reason_codes[], assessed-weight coverage and partial/insufficient status through approved metadata. Preserve component nulls. Include weighted result and cap/override explanation in internal or approved evidence output so dashboard can explain final score.

## 6. Technical specification

Thermal: valid temperature level, positive rate and positive residual severity. Electrical: phase spread, neutral and validated PF. Loading: configured capacity/current stress and duration. Oil: verified low level/frozen reference/falling trend. Alarm: known clear=100, verified active alarm=40, verified active trip=0. Anomaly: 100(1−anomaly_score).

Ordinary severity normal/warning/severe ranges follow phase 02: no exceedance at/below W; progressive concern between W and C; saturated statistical severity at/beyond C. Statistical severe is not physical critical. Physical limit thresholds remain configured, not inferred.

Use a small 5% anomaly weight despite overlap; this intentional repeated penalty is explicit and not independent evidence. Do not multiply scores into a survival probability. Cap only assessed persistent condition evidence (or known active protection); isolated noise must not acquire persistent-condition cap semantics. Maximum loading/anomaly alone does not enter the cap.

## 7. Mathematical/formula specification

For supported severity s_j in [0,1]:

$$
H_j=100(1-s_j)
$$

H_j is component points [0,100], not percent probability. Protection uses the discrete scores above instead of this continuous map. For anomaly H_A=100(1−a), where a is phase-02 score.

$$
H_{weighted}=0.30H_T+0.20H_E+0.10H_L+0.15H_O+0.20H_P+0.05H_A
$$

T/E/L/O/P/A denote thermal/electrical/loading/oil/protection/anomaly components, all in points. Coefficients are dimensionless heuristic weights summing to 1. They prioritize thermal, electrical and direct protection while limiting loading-alone and overlapping anomaly influence.

For supported persistent-condition set C drawn only from thermal/electrical/oil/protection:

$$
H_{capped}=\min\left(H_{weighted},20+\min_{j\in C}H_j\right)
$$

20 is a heuristic point allowance, not a standard threshold. If C is empty, no condition cap applies. Normal valid components can be present without altering the result. In established fully assessed persistent scenarios this is the original minimum over thermal/electrical/oil/protection. Known verified active trip overrides the result to H=0 immediately.

For available-component set M and fixed original weights w_j:

$$
H_{available}=\frac{\sum_{j\in M}w_jH_j}{\sum_{j\in M}w_j},\qquad
C_H=\sum_{j\in M}w_j
$$

H_available is points; C_H is assessed weight fraction [0,1]. Apply the same supported persistent cap to this available result. Zero denominator → null. Missing critical thermal/protection evidence prevents a confident healthy declaration even if the available score is high. No numeric minimum coverage gate was established; do not invent one.

### Mandatory calculated fixtures

All ordinary cap cases below assume persistent supported evidence and full coverage. These are synthetic arithmetic examples, not measured dataset conditions.

| Scenario | T | E | L | O | P | A | Weighted | Final |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Healthy reference | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| High load, normal thermal response | 100 | 100 | 40 | 100 | 100 | 40 | 91 | 91 |
| High oil temperature | 20 | 100 | 100 | 100 | 100 | 20 | 72 | 40 |
| Current imbalance | 100 | 30 | 100 | 100 | 100 | 30 | 82.5 | 50 |
| Positive thermal residual | 40 | 100 | 100 | 100 | 100 | 40 | 79 | 60 |
| Active alarm | 100 | 100 | 100 | 100 | 40 | 0 | 83 | 60 |
| Verified trip | 100 | 100 | 100 | 100 | 0 | 0 | 75 | 0 override |
| Multiple problems | 20 | 30 | 40 | 40 | 100 | 20 | 43 | 40 |

For high oil: weighted=0.30×20+0.20×100+0.10×100+0.15×100+0.20×100+0.05×20=72; cap=min(72,20+20)=40. An alarm's anomaly component is zero because verified protection gives a=1. A missing component must not be assigned one of these fixture values.

## 8. Parameters and configuration

Weights 0.30/0.20/0.10/0.15/0.20/0.05; active-alarm score 40; cap allowance 20; verified-trip override 0. All heuristic operational choices and versioned configuration. Component W/C/physical thresholds come from upstream, never re-fitted here. Persistence uses 3 valid points over ≥30 minutes without gaps >30 minutes. No arbitrary global HI bands are required for maintenance.

## 9. Processing/algorithm flow

Validate evidence/coverage → produce available component scores → calculate original-weight coverage → renormalize only supported components if partial → apply supported persistent-condition cap → apply verified-trip override → preserve missing components and confidence limitation → attach reasons and contribution/cap explanation.

## 10. Data-quality and missing-data behavior

Missing rating means loading component null, not 100. Unknown protection is not clear. Missing thermal/protection blocks a confident healthy label. Partial aggregate explicitly reports C_H and component nulls. No meaningful assessment gives null; known trip gives zero despite unrelated missing values. Do not multiply HI by coverage, which would make missing data falsely look like physical damage.

## 11. Edge cases

All components missing; only one available; loading unavailable; thermal initializing; high anomaly from sensor issue; clear protection partially unknown; trip with absent temperature; isolated spike versus persistent condition; severe load only; versioned weights; recovery after alarm.

## 12. Leakage/safety constraints

HI is downstream condition reporting, not a fault feature or label. No maintenance-to-HI feedback to manufacture consistency. Threshold fitting remains upstream train-only. HI=0 means operational critical convention under verified trip, not exhausted asset life. Do not infer RUL from HI.

## 13. Integration requirements

Keep established field names and component labels. Provide dashboard reasons such as HIGH_LOADING, HIGH_OIL_TEMP, CURRENT_IMBALANCE, THERMAL_RESIDUAL_HIGH, OIL_TEMP_ALARM/OIL_TEMP_TRIP/MOG_ALARM, with source-unit qualification. Null/coverage/cap metadata must be explicitly documented in the contract. Maintenance reads evidence, not merely a score band.

## 14. Testing requirements

Reproduce all eight fixtures exactly (floating tolerance only for arithmetic); score bounds; monotonic worsening with fixed coverage; cap excludes loading/anomaly; nonpersistent spike does not trigger persistent cap; original weights sum to one; partial renormalization and C_H correct; no available components null; missing protection not clear; trip override precedence; no rating→loading null; no dependence on risk/maintenance.

## 15. Acceptance criteria

Fixtures and missingness tests pass; reasons trace to upstream evidence; cap/override is visible; partial score cannot be presented as complete health; exact weights and semantics recorded. No RUL or probability interpretation.

## 16. Expected behavior

High load with credible normal thermal response causes modest reduction, persistent severe thermal/electrical/oil evidence cannot be averaged away, and a verified trip yields zero immediately. Missing data produces a visibly partial/unavailable assessment.

## 17. Explicit non-goals

No standard-certified health index, failure probability, lifespan, new thresholds, equal-weight redesign, model training or maintenance implementation.

## 18. Handoff to subsequent phases

Deliver score/component/coverage contract, scenario fixtures, reason provenance and cap/override status to maintenance, evaluation and unified pipeline. Record config/version for release.

## 19. Implementation-agent instructions

Use supplied severities and exact specified arithmetic. If upstream evidence is not yet available, use fixtures and null-safe interfaces; do not add substitute methodologies or fit new thresholds.

## Implementation Agent Prompt

Read AUDIT_PLAN.md and 03_HEALTH_INDEX.md. Inspect repository contracts, upstream evidence and any current health code before modifying anything. Implement ONLY phase 03, preserving architecture/contracts and using the documented weights, formulas, cap, missing-data rules and trip override exactly. Do not invent technical values or modify unrelated phases. Add/update tests for every listed scenario and partial-data case, run relevant tests and a health-output integration smoke check. Report changes, tests/results and unresolved configuration/confirmation requirements. Stop after this phase.
