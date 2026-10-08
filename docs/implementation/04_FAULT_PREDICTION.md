# Phase 04 — Experimental Future Proxy Prediction

## 1. Phase objective

Implement the established leakage-safe next-hour oil-alert onset experiment and stable unavailable-output behavior. Do not convert alarm labels into confirmed transformer failures or publish unsupported probabilities.

## 2. Scope

Target construction, eligibility/censoring, small causal feature vector, regularized Logistic Regression baseline, chronological evaluation hooks, optional calibration eligibility and inference release gate. No new fault taxonomy or new ML methodology.

## 3. Dependencies

Depends on phase 00 corrected/provenanced telemetry, phase 01 out-of-sample residuals/readiness and master evaluation protocol. Produces labels, experimental artifact or explicit unavailable status for 05–08. Blocks predictive claims, not the rest of monitoring. Target/interface tests can be built independently. Validate before risk may influence maintenance.

## 4. Inputs

oil_temp_alarm/oil_temp_trip status history for labels/eligibility only; timestamps/quality/coverage; approved causal features; source/config versions; fixed chronological partitions. Observed counts in audited data: alarm 100 rows/11 transitions; trip 47/10; MOG 2,087/5. All thermal positives end Sep 3, 2019. These are proxy events and not necessarily independent physical failures.

## 5. Outputs

Versioned target/eligibility/censoring table; fitted preprocessing/model if feasible; predictions for evaluation; model/calibration release status; fault_risk, predicted_fault, prediction_confidence, all nullable when unsupported. Operational default is null risk fields with explicit INSUFFICIENT_VALIDATION, documented as a contract extension where necessary.

## 6. Technical specification

Target: will a **new oil-temperature alarm OR trip** be observed within the next one hour, while both are known clear now? Use exact elapsed time, not next four rows. Current active event is monitoring, not new-onset prediction.

Onset requires a valid prior clear observation followed by active within accepted gap. Three-valued OR: any 1 active; both 0 clear; otherwise unknown. Gap >30 minutes makes continuity uncertain. Require adequately observed clear history before eligibility; its additional duration was not established and is NEEDS CONFIRMATION/configuration, not an invented washout interval.

Negatives require adequately observed follow-up through the whole horizon. End-of-record/insufficient coverage is censored. A reliably observed onset inside the horizon permits positive classification; do not label a potentially missed earlier event across an unknown gap as a precise onset. Overlapping windows for one event share event identity and are not independent samples.

Initial candidate features: oil indicator, ambient indicator, one-hour temperature slope, J or current mean, current spread, kVA and one-hour load summary, validated positive residual. Keep a small predeclared set; reduce rather than expand when events are scarce. Do not use both redundant J/current summaries without evaluation justification.

Exclude current alarm/trip/MOG, time-since-alarm/trip, WTI, HI, maintenance, alarm-derived anomaly, absolute timestamp, row number, cumulative energy and future-derived values. Current oil can predict future onset causally, but suspicious encoding must be investigated. All 47 audited trip rows coincide with OTI>100; contemporaneous classification is not the requested forecast.

Selected model: regularized Logistic Regression. Shallow Gradient Boosting is a challenger only if evidence permits. Random Forest secondary; XGBoost/LightGBM and deep learning deferred. Isolation Forest belongs to optional anomaly work, not supervised future-event prediction.

## 7. Mathematical/formula specification

$$
B_t=oil\_temp\_alarm_t\lor oil\_temp\_trip_t
$$

B is Boolean/unknown with three-valued logic, not a probability. Let E be valid observed clear-to-active onset timestamps. For an eligible t:

$$
Y_t=\mathbf{1}\{\exists e\in E:\ t<e\le t+h\},\qquad h=1\ \text{hour}
$$

Y is binary only when label coverage conditions are met, otherwise censored. h is the established heuristic forecast horizon, not a standard requirement. Open-left/closed-right interval excludes current events and includes an event exactly at the horizon.

$$
p_{raw}(z)=\frac{1}{1+\exp[-(\beta_0+\boldsymbol\beta^\mathsf{T}z)]}
$$

z is the ordered train-preprocessed feature vector; β coefficients and intercept are learned; p_raw is a dimensionless model probability estimate, not demonstrated calibration. Train-only scaling/imputation must be frozen. Critical unavailable features either use documented fitted preprocessing or return insufficient data.

If separately calibrated, a sigmoid mapping can be fitted:

$$
p=\frac{1}{1+\exp(a_c f+b_c)}
$$

f is model decision score, a_c/b_c learned calibration coefficients on temporally separate natural-prevalence data. This merely states the established sigmoid calibration option; coefficients and eligibility are not supplied. Do not fit on classifier training rows or on a one-class validation set.

For a validated calibrated binary output only:

$$
prediction\_confidence=\max(p,1-p)
$$

This is predicted-class probability, not independent model reliability. fault_risk=p means next-hour proxy onset probability. predicted_fault=OIL_TEMP_ALERT_WITHIN_1H when the validation-selected decision threshold is crossed; otherwise null. Boundary convention must be documented/tested. Do not manufacture a second uncertainty score.

## 8. Parameters and configuration

h=1 hour; gap policy initially 30 minutes; target version and feature list/order; train-only preprocessing; regularization/class-weight settings selected inside training folds; decision threshold validation-selected; calibration status. No numeric regularization strength, minimum event-count release threshold or reliable-calibration cutoff was established. Mark them as validation/configuration decisions, not standards facts. Additional clear-history duration NEEDS CONFIRMATION.

## 9. Processing/algorithm flow

Freeze original time boundaries → validate statuses → identify covered clear-to-active episodes → construct eligible/censored horizon labels → create causal feature cutoff at t → build chronological out-of-fold thermal features → train preprocessing/model within training → compare simple baselines → tune threshold on validation only if feasible → calibrate only with independent adequate events → evaluate untouched test → gate operational probability output → return either validated outputs or explicit unavailable status.

Prefer regularization/threshold selection to synthetic oversampling. No temporal SMOTE. If class weighting is used, tune within training. Prevent one long event from dominating through many overlapping positives; use event-balanced weighting and report the exact policy. Calibration uses natural prevalence, not rebalanced prevalence.

## 10. Data-quality and missing-data behavior

Unknown contacts are not clear; absent follow-up is not a negative. Unknown future gaps censor labels. Preserve quality-related exclusions with counts. Train-only imputation may support approved model features; raw telemetry remains untouched. Runtime distribution/feature incompatibility produces unavailable status, not an invented zero-risk prediction. A current active alarm invokes monitoring, not a reassuring low onset risk.

## 11. Edge cases

All-negative fold; no eligible positives; one validation episode; event exactly at cutoff/horizon; alarm already active; trip occurring during active alarm episode; simultaneous alarm/trip; gap immediately before onset; end-of-file; duplicate contact conflict; missing features; rapid OTI encoding jump; new asset/domain; repeated event windows.

## 12. Leakage/safety constraints

No HI, maintenance or target-derived current outputs in model vector. Purge training horizons crossing split boundary. Past observed history may initialize test state; test labels may not influence fitting. Thermal residual training features are out of fold. No random temporal mixing. No confirmed-failure language. Unvalidated scores never promote maintenance. Synthetic scenarios do not prove historical forecasting accuracy.

## 13. Integration requirements

Keep fault_risk/predicted_fault/prediction_confidence and declare target/horizon/version. Provide INSUFFICIENT_VALIDATION or INSUFFICIENT_DATA through approved status metadata. Maintenance checks model eligibility, not merely numeric score. Experimental research scores must be clearly separate from operational validated probability fields/views. Future confirmed labels swap target/model/calibration versions without rewriting raw canonical schema; domain validation remains mandatory.

## 14. Testing requirements

Three-valued OR; onset requires clear predecessor; active-event exclusion; time-based horizon under irregular cadence; t excluded and t+h included; end censoring; gap censoring; no label leakage across split; feature allowlist excludes all forbidden fields; future-data perturbation leaves earlier features/predictions unchanged; fitted preprocessing train-only; single-class calibration refusal; unavailable risk null; model feature order mismatch refusal; event weights/accounting reproducible. Run primary and exploratory label-distribution smoke reports before any performance claim.

## 15. Acceptance criteria

Target and censoring correct and versioned; causal allowlist enforced; chronological experimental baseline or explicit inability recorded; all operational gates enforced. Completing this phase may legitimately produce only unavailable operational forecasts. No probability claim without both-class time-separated evaluation, baseline improvement, calibration evidence and acceptable alert burden.

## 16. Expected behavior

Current supplied data generally retains operational INSUFFICIENT_VALIDATION. Research experiment can show honest next-hour proxy results with event scarcity. Current alarm/trip monitoring works regardless. Future sufficient confirmed data can replace target/artifact without architecture redesign.

## 17. Explicit non-goals

No current-event classifier presented as forecasting; no separate trip and MOG production models initially; no physical failure/RUL labels; no deep learning; no extensive hyperparameter search on roughly ten episodes; no guaranteed calibrated confidence.

## 18. Handoff to subsequent phases

Provide target definition, eligible/censored counts, event IDs, feature/preprocessing metadata, temporal predictions, release/calibration status and null-safe interface to 05–08. Phase 06 owns final evaluation report; rules already apply here.

## 19. Implementation-agent instructions

Do not bypass weak-label/evaluation limits to produce attractive probabilities. Build the usable interface and tests even if training/calibration remains blocked. Clearly separate implementation completion from model release eligibility.

## Implementation Agent Prompt

Read AUDIT_PLAN.md and 04_FAULT_PREDICTION.md. Inspect the existing repository, contracts, feature/twin outputs and any target/model code before editing. Implement ONLY phase 04 with the documented future-onset target, horizon, censoring, causal feature allowlist and experimental Logistic Regression approach. Preserve architecture/contracts; do not invent labels, thresholds, units, event-count gates or calibration evidence. Do not modify unrelated phases. Add/update tests, run relevant tests and chronological label/evaluation smoke checks. Report changes, tests/results, model eligibility and every unresolved configuration/confirmation requirement. Return null operational risk when unsupported. Stop after this phase.
