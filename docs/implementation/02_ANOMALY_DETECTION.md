# Phase 02 — Anomaly Detection

## 1. Phase objective

Implement the established hybrid statistical/engineering detector with explainable 0–1 abnormality severity, persistence-aware flag and reason evidence. The score is not fault probability.

## 2. Scope

Directional signal scoring, correlated-family aggregation, protection rules, missing coverage, statistical reference fitting and alert episode logic. Isolation Forest is an optional challenger only; do not make it a prerequisite or replace the selected primary method.

## 3. Dependencies

Depends on phase 00 quality/features/config and phase 01 ready thermal outputs/out-of-sample residuals. Produces score/flag/reasons and family severities for 03/05/06/07. Blocks HI/anomaly maintenance integration. Rule fixtures can be implemented independently; validate fitted thresholds before operational consumers.

## 4. Inputs

Approved canonical/features; positive and negative residual context; readiness/freshness; verified engineering limits when available; exact protection contacts; training-only reference population; elapsed-time persistence state. No raw source-name dependencies.

## 5. Outputs

anomaly_score in [0,1] or null; anomaly_flag Boolean or null; reason_codes[]; documented internal/versioned family severities, coverage, threshold provenance, trigger value/unit, persistence duration and source. Known protection evidence can trigger even with incomplete other sensors.

## 6. Technical specification

Reference fitting uses training-only valid, alarm-clear, adequately covered, stable-measurement segments excluding known sensor/encoding failures. Call this reference operation, not confirmed health. High historical current spread does not establish safe engineering imbalance.

| Signal | Direction/baseline | Validity and interaction |
|---|---|---|
| Current spread | Upper training tail or verified applicable limit | All phases, above configured low-load gate; not sequence-based standard threshold |
| Voltage spread | Upper tail | Separate missing/zero-voltage sensor or supply events |
| Neutral magnitude/ratio | Upper, conditional on load | No near-zero denominator; current-context dependence |
| Loading | Nameplate/operator limits; historical kVA tail separately | Historical high demand is not OVERLOAD |
| PF departure | Upper under verified PF meaning | Low apparent-power gate; preserve direction |
| Oil indicator | Upper tail now; physical level only if verified | Extreme indicator can also be quality issue |
| Temperature rate | Positive tail | Valid short interval and coverage |
| Thermal residual | Positive out-of-sample tail | Ready twin only; negative tail → mismatch |
| Oil frozen-reference departure | Lower tail or configured minimum | Direction/units must be verified before LOW_OIL_LEVEL claim |
| Oil trend | Falling tail | Temperature expansion/gauge changes are possible causes |
| Rolling variability | Upper reference tail | Context, not repeated independent vote |
| Current alarms/trips | Active known status | Direct state evidence, not learned probability |
| Alarm history | Recency/repetition | Context only; no extra independent vote for current event |

Negative residual evidence uses THERMAL_MODEL_MISMATCH and quality/model review. It must not become positive-heating severity. If scored as a separate mismatch/pattern diagnostic, document its allocation so it does not imply asset overheating.

Reason codes: HIGH_OIL_TEMP (physical only with verified unit/limit; otherwise UI says high oil indicator), RAPID_TEMP_RISE, CURRENT_IMBALANCE, VOLTAGE_IMBALANCE, HIGH_LOADING, OVERLOAD (rating required), THERMAL_RESIDUAL_HIGH, THERMAL_MODEL_MISMATCH, LOW_OIL_LEVEL (verified direction/threshold), OIL_LEVEL_DECREASING, OIL_TEMP_ALARM, OIL_TEMP_TRIP, MOG_ALARM, ANOMALOUS_PATTERN, DATA_QUALITY_ISSUE, RATING_UNAVAILABLE. New reason-code declarations must be explicit in contract docs.

## 7. Mathematical/formula specification

Upper-tail severity:

$$
s_j(x)=\operatorname{clip}\left(\frac{x-W_j}{C_j-W_j},0,1\right),\quad C_j>W_j
$$

Lower-tail severity:

$$
s_j(x)=\operatorname{clip}\left(\frac{W_j-x}{W_j-C_j},0,1\right),\quad C_j<W_j
$$

x,W_j,C_j share the signal unit; s_j is dimensionless [0,1]. W is the onset of reference exceedance, C the severe-reference point. Statistical C is not proof of physical criticality. clip bounds its scalar argument to [0,1].

Initial upper W=Q_0.95 and C=Q_0.995; direct lower-tail W=Q_0.05 and C=Q_0.005. Q is a training-reference quantile in signal units. Quantile levels are heuristic; resulting values are dataset-derived. If C=W, use an explicitly justified discrete/resolution-aware rule or mark detector unavailable; never divide by zero or invent an epsilon sensor scale.

$$
s_T=\max(s_{temperature},s_{rise},s_{positive\ residual})
$$

$$
s_E=\max(s_{current\ spread},s_{voltage\ spread},s_{neutral},s_{PF})
$$

s_L and s_O are analogous maxima of valid loading and oil evidence. All s terms are dimensionless. Exclude unavailable terms without treating them as healthy; retain family coverage.

$$
a=\max(s_T,s_E,s_L,s_O,s_{pattern},s_{protection})
$$

a is anomaly_score, dimensionless [0,1]. s_protection=1 for a verified active contact. Unavailable optional pattern detector is omitted, not required. Maximum prevents severe evidence dilution and correlated additive inflation. Maintenance independently assesses agreement across families.

Statistical flag compares a with validation-selected a_on, then requires the documented persistence. Exact boundary convention must be documented consistently and tested; the discussion established threshold crossing but no independent physical cutoff. Verified protection bypasses statistical persistence. No evidence at all → a and flag null.

## 8. Parameters and configuration

Reference selector; signal direction; W/C values and provenance; threshold unit; per-signal prerequisites; a_on; persistence/recovery state; optional challenger selection. Default entry/recovery: 3 valid observations spanning ≥30 minutes, with no qualifying gap >30 minutes. Initial validation target ≤1 unexplained episode per 7 adequately observed asset-days. These are configurable heuristics. No arbitrary 70/80/90% load cutoffs.

Operator limits, minimum-current gates, sensor accuracy and physical oil thresholds are CONFIGURATION REQUIRED. a_on is learned/tuned on validation, not an invented constant. Recovery score hysteresis beyond the established clear-observation rule was not assigned a numeric value; do not invent one silently.

## 9. Processing/algorithm flow

Validate each detector's prerequisites → retrieve frozen training reference/configured limit → compute directional severities → group correlated evidence → calculate max score and coverage → apply verified protection override or persistence-aware statistical flag → emit reasons with measurement/threshold/source → persist episode state. Fit/tune references and cutoff in separate time-safe training/validation steps; freeze for test/demo.

## 10. Data-quality and missing-data behavior

Missing phase invalidates phase spread. Low-load denominator invalidates ratio. Unready twin invalidates residual detector. Unknown level direction blocks physical low-oil claim. Missing contacts are not clear. Missing data cannot yield a confident false anomaly flag; null/partial status is explicit. A known trip still yields protection evidence. Quality anomalies remain distinguishable from asset-condition anomalies.

## 11. Edge cases

Constant features/tied quantiles; one valid family only; all missing; current/voltage zero; alarm with missing temperature; long gaps during persistence; irregular cadence; large negative residual; high predicted and observed temperature with near-zero residual; current imbalance statistically typical but physically unresolved; optional detector absent.

## 12. Leakage/safety constraints

Train-only thresholds. Use out-of-sample residuals for learned residual baselines. No test-driven threshold tuning. Same-event alarms may contribute current anomaly monitoring but are excluded from fault-model features. Score is not calibrated risk. No emergency loading authorization or switching command.

## 13. Integration requirements

Preserve required outputs. Supply six health/maintenance evidence inputs with units, coverage and persistence; do not require phases 03–05 to reconstruct raw formulas. Keep anomaly_score distinct from fault_risk. Document proposed metadata additions and reason codes. Dashboard presents source-unit warnings accurately.

## 14. Testing requirements

Upper/lower endpoint and monotonicity tests; score bounds; C=W handling; missing-phase/zero-denominator cases; ready versus unready residual; negative mismatch reasons; protection immediate trigger; three-point elapsed-time persistence and gap reset; recovery; max grouping avoids repeated votes; all-missing null; partial coverage; threshold provenance reproducibility. Smoke replay historical validation to count alert episodes per observed time, not just positive rows.

## 15. Acceptance criteria

Explainable scores and reason evidence reproduce exactly. Persistence uses elapsed time. No arbitrary engineering thresholds or healthy missingness. Reference/validation splits recorded. Alert burden and any inability to meet the heuristic budget are reported, not hidden by tuning on test.

## 16. Expected behavior

Normal reference evidence maps to low score; severity increases monotonically beyond reference thresholds. A isolated statistical spike may be WATCH without a persistent anomaly flag. Active verified protection is immediate evidence. Correlated thermal features remain one family.

## 17. Explicit non-goals

No failure probability, fault-label invention, mandatory Isolation Forest, HI implementation, automatic trip or full harmonic-loss calculation. Do not promote optional raw fields.

## 18. Handoff to subsequent phases

Phase 03 receives severities/coverage; phase 05 receives reasons, persistence and independent-family identity; phase 06 receives frozen thresholds/predictions/episode accounting; phase 07 receives stateful API semantics.

## 19. Implementation-agent instructions

Implement only documented detection and evidence support. If statistical thresholds cannot be fitted reliably, retain explicit unavailable status and completed deterministic tests rather than inventing measurement thresholds.

## Implementation Agent Prompt

Read AUDIT_PLAN.md and 02_ANOMALY_DETECTION.md. Inspect the existing repository, feature/twin outputs, contracts and any detector code before editing. Implement ONLY phase 02 using the established grouped statistical-plus-rule approach and exact documented formulas. Preserve architecture/contracts; do not invent missing thresholds, units, ratings or contact semantics, and do not modify unrelated phases. Add/update tests, run the relevant tests and a persistence/alert-episode validation smoke replay. Report changed files, tests and results, fitted threshold provenance, and unresolved configuration/confirmation requirements. Stop after this phase.
