# Phase 06 — Time-Aware Evaluation

## 1. Phase objective

Produce honest, reproducible temporal evaluation and model-release eligibility for the established thermal/anomaly/HI/proxy/maintenance implementation. This phase formalizes results; its leakage rules apply from the first fit, not only now.

## 2. Scope

Frozen chronological splits, horizon purging, baseline comparison, event-aware metrics, calibration feasibility, uncertainty/limitations, alert burden, scenario validation and promotion gates. No model redesign to chase test results.

## 3. Dependencies

Consumes 00–05 data provenance, fitted artifacts, predictions and decision fixtures. Produces evaluation evidence/eligibility for 07–08. Blocks validated probability/model promotion, not null-safe pipeline construction. Evaluation harness can start early. Must validate before unified candidate promotion; phase 07 reruns affected end-to-end checks without changing frozen test fitting rules.

## 4. Inputs

Original timeline/data hash, quality/censoring masks, event IDs, frozen model/preprocessor/config versions, chronological predictions, thermal baselines, anomaly episodes, HI/maintenance fixture outputs. Separate historical and synthetic inputs explicitly.

## 5. Outputs

Versioned evaluation report/metrics with split boundaries, sample and independent-event counts, missing/censored counts, metric definitions, confidence limitations, calibration status and release eligibility. Store predicted-versus-observed traces and false/missed-event explanations in repository-appropriate artifacts. A metric can be NOT ESTIMABLE; no fabricated numeric replacement.

## 6. Technical specification

### Primary partitions

| Split | Boundary on original union timeline |
|---|---|
| Train | timestamp < 2019-11-23 11:45 |
| Validation | 2019-11-23 11:45 ≤ timestamp < 2020-02-13 11:15 |
| Test | timestamp ≥ 2020-02-13 11:15 |

These derive approximately from 60/20/20 ordered union rows, before filtering. Historical timezone remains unknown; interpret in original consistent source time. Do not recompute boundaries after dropping rows to quietly move events.

All supplied thermal/MOG positives occur in training. Later validation/test can measure thermal error, operating shift and false alerts, not positive-class recall/discrimination. An always-negative classifier achieves roughly 99.757% current-trip row accuracy while detecting none; do not celebrate accuracy.

### Exploratory event-era protocol

Train before 2019-08-01; validate Aug 1–15 inclusive; test Aug 16–Sep 3 inclusive; later negative surveillance from Sep 4. This protocol was chosen after observing label distribution and is exploratory, not untouched confirmation. Only one observed thermal episode exists in its validation interval; probability calibration/large search is not justified.

### Baselines and priorities

Thermal: prior oil observation, ambient plus training-median offset, ambient-only dynamic model. Load-dependent twin must demonstrate held-out improvement and sensible response before a stronger claim.

Forecast: always-negative and training-prevalence reference; simple causal indicator/trend rule as an explicitly configured benchmark if available. Do not invent its engineering cutoff. Compare regularized Logistic Regression; challengers need more evidence and no test tuning.

Primary use-case metric: event recall at constrained false-alert burden and useful lead time. Report row metrics as supplementary because overlapping windows and long alarm episodes are correlated.

## 7. Mathematical/formula specification

For binary eligible evaluated labels/predictions:

$$
Precision=\frac{TP}{TP+FP},\qquad Recall=\frac{TP}{TP+FN}
$$

$$
F_1=\frac{2\,Precision\,Recall}{Precision+Recall}
$$

TP/FP/TN/FN are row counts for the declared label/cutoff; metrics are dimensionless. Zero denominators must be explicitly reported with support counts rather than a misleading software default. No positives means positive recall/ranking performance not estimable.

$$
MAE=\frac{1}{N}\sum_i|T_i-\widehat T_i|,\qquad
RMSE=\sqrt{\frac{1}{N}\sum_i(T_i-\widehat T_i)^2}
$$

$$
Bias=\frac{1}{N}\sum_i(T_i-\widehat T_i)
$$

N is valid ready evaluated oil predictions; all three metrics are in T's source unit or verified °C. Report excluded warm-up/missing counts and residual tail quantiles. Positive bias means observation above model.

$$
Brier=\frac{1}{N}\sum_i(p_i-Y_i)^2
$$

p is predicted probability and Y binary next-hour target; Brier dimensionless. Calibration claim requires sufficient independent time-separated both-class support; a low score on an all-negative segment is not proof of calibration.

$$
EventRecall=\frac{\text{eligible onset episodes warned in advance}}{\text{eligible onset episodes}}
$$

An advance warning must occur while clear, within the specified (t,t+1h] relationship, before onset. Count each event once. First qualifying warning determines reported lead time e−t, in minutes/hours; record timing convention. No eligible events → not estimable.

$$
FalseAlertRate=\frac{\text{unexplained false alert episodes}}{\text{adequately observed asset-days}}
$$

Rate unit is episodes/asset-day. Use covered observed duration, not calendar days spanning missing data. Episode counting follows persistence/recovery policy; repeated flagged rows are not separate alerts. Initial heuristic budget ≤1 episode/7 observed asset-days. Report unexplained alerts separately from unlabelled but plausible anomalies; missing ground truth does not prove a detection false.

PR-AUC/AP: explicitly name the selected integration/average-precision definition; report class prevalence and support. Do not conflate AP and trapezoidal PR-AUC. Reliability plots compare predicted probability and observed frequency with event/day dependence acknowledged.

## 8. Parameters and configuration

Frozen boundaries above; forecast horizon 1 hour; continuity 30 minutes; persistence 3 valid observations over ≥30 minutes; threshold tuning validation-only. Confidence interval resampling unit is event/day blocks rather than independent rows. No resampling count, minimum positive-event gate, confidence level or numeric recall acceptance target was established; specify as evaluation configuration/NEEDS CONFIRMATION, not invented safety facts.

## 9. Processing/algorithm flow

Verify artifact hashes/versions → freeze original partitions → apply causal quality/eligibility masks and target-horizon purge → fit only permitted training data → generate chronological predictions with valid prior state → tune only validation → freeze threshold/model → evaluate test once → calculate supported row/event/thermal/alert metrics → assess calibration eligibility → run synthetic HI/maintenance fixtures separately → record limitations and release status.

Carry past observed history into validation/test to match deployment, without fitting on future outcomes. Event-overlap windows must not be split across train/fold label boundaries. If implementation changes after test inspection, record the test's reuse and do not pretend it remains untouched.

## 10. Data-quality and missing-data behavior

Censored labels excluded with reasons/counts. Invalid or unready thermal predictions excluded transparently, not replaced with zero error. Denominator observation exposure excludes long unknown gaps. Missing model output tracked as coverage failure, not a correct negative. Single-class partitions report applicable specificity/false alerts and unsupported positive metrics honestly.

## 11. Edge cases

No positives; no predictions; all missing; one independent event; duplicate event windows; first event after gap; fold with one class; active-event samples excluded; right-censored horizon; model reset at boundary; test domain outside training range; insufficient calibrated probabilities.

## 12. Leakage/safety constraints

Fit every scaler/imputer/quantile/thermal parameter on training only. Fault training residuals must be chronological out of fold. Calibration data disjoint from classifier fitting. No random split, temporal SMOTE, future interpolation or test threshold selection. Synthetic detector/simulator agreement is functional demonstration, not independent empirical validation. No unsupported failure/standards/RUL claims.

## 13. Integration requirements

Write evaluation_metrics and eligibility/calibration status into the versioned bundle. Phase 07 consumes release status and null-safe fallback; phase 08 publishes limitations. Report discrepancies in metadata/target/features as integration blockers. Pipeline changes trigger relevant replay/evaluation checks with frozen boundaries, not a new split.

## 14. Testing requirements

Unit tests for cutoff/horizon purge, time splits before filtering, metric denominators, empty/single-class partitions, episode counts, observed-time denominator and censoring. Regression tests ensure no fitted object sees later rows. Reproduce HI arithmetic and maintenance scenario table. Smoke-run historical primary and exploratory partitions, recording positive-event scarcity, and run synthetic demos separately.

## 15. Acceptance criteria

Report is reproducible and source/version linked. All metric support/limitations explicit. Operational forecast is released only if time-separated both classes, adequate event uncertainty evidence, baseline improvement, calibration and alert burden are supportable. Current supplied labels do not establish that gate. A documented INSUFFICIENT_VALIDATION conclusion is acceptable completion, not a failed implementation.

## 16. Expected behavior

Later all-negative data produces false-alert and thermal results without invented recall. Event-era experiment remains clearly exploratory. No inflated random-split accuracy drives model selection or demo claims.

## 17. Explicit non-goals

No new model family/target, test-set optimization, fabricated confidence intervals from dependent rows, certification or RUL. Do not expand testing unrelated modules without a concrete gate.

## 18. Handoff to subsequent phases

Give phase 07 frozen bundle eligibility, evaluation configuration and integration test expectations. Give phase 08 metrics/limitations, event counts, target/split/calibration provenance and remaining blocked claims.

## 19. Implementation-agent instructions

Implement evaluation around existing phase outputs. If performance is weak, report it and preserve gates; do not silently redesign upstream methodology. Fix evaluation bugs only within this scope and identify upstream defects separately.

## Implementation Agent Prompt

Read AUDIT_PLAN.md and 06_EVALUATION.md. Inspect repository training/evaluation paths, contracts, model artifacts and tests before editing. Implement ONLY phase 06 with the documented chronology, target purging, event accounting, formulas and release gates. Preserve architecture/contracts; do not invent performance evidence, numeric acceptance thresholds or labels. Do not modify unrelated phases or tune on test. Add/update tests, run relevant tests and historical/synthetic evaluation smoke checks separately. Report changes, tests/results, non-estimable metrics, release eligibility and unresolved configuration/confirmation requirements. Stop after this phase.
