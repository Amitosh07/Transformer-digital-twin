# Phase 05 — Maintenance Engine

## 1. Phase objective

Convert established condition evidence into deterministic advisory NORMAL/WATCH/PLAN/URGENT priority, recommendation and reasons, using severity, persistence, independent corroboration and verified protection overrides.

## 2. Scope

Decision precedence, persistence/recovery, trip latching, missing-data recommendations and explanation. No automatic electrical control, new engineering thresholds or retraining.

## 3. Dependencies

Depends on 00–03 valid condition/HI/anomaly evidence and phase 04 forecast interface/status. A trained forecast is optional; unavailable forecast must not block maintenance. Produces decisions for 06–08 and backend/dashboard. Rules can be tested on fixtures. Validate before end-to-end demo.

## 4. Inputs

health_index/components/coverage; anomaly_score/flag and family reasons; fault_risk/predicted_fault only with validated eligibility; loading/rating availability; thermal/oil condition; verified contact state; trend severity; freshness; persistence and prior decision state. No source-specific raw names.

## 5. Outputs

maintenance_priority exactly NORMAL, WATCH, PLAN or URGENT; maintenance_recommendation human-readable; reason_codes[] with approved evidence metadata. Preserve inference/data-quality status separately so a priority is not mistaken for a complete assessment. Record latch/clear history under operator policy.

## 6. Technical specification

Evaluate in precedence order:

| Priority | Established conditions |
|---|---|
| URGENT | Verified active trip; verified critical operational limit requiring immediate operator response; or persistent severe thermal evidence corroborated by independent condition/protection evidence |
| PLAN | Persistent active alarm/MOG; persistent severe single-family anomaly; persistent warning in at least two independent families; or validated high proxy-risk episode |
| WATCH | New/unconfirmed statistical exceedance; high loading with normal thermal response; unresolved sensor/model mismatch; missing critical fresh telemetry |
| NORMAL | Adequate fresh evidence, no active protection, no persistent concerning evidence and no applicable limit violation |

Temperature level, slope and residual belong to one thermal family. They are not three independent votes. HI and anomaly often summarize the same evidence and do not create independent corroboration. Low HI alone cannot command URGENT. Experimental forecast alone cannot cause PLAN/URGENT. Rating-relative overload and dataset-relative high demand must remain distinct.

Immediate verified trip overrides missing non-protection inputs and is latched until cleared under documented operator policy. Physical severe alarm escalation requires known contact semantics or corroboration. Do not invent a universal alarm-to-trip action.

Recommendations:

- High demand/load with expected thermal behavior: review load distribution and monitor thermal response.
- Current imbalance: verify measurement/phase allocation and plan balancing if confirmed.
- Positive residual: verify sensor, cooling, ventilation and operating configuration.
- Falling oil indicator: verify gauge and inspect for leakage; do not assert leakage as fact.
- MOG alarm: arrange oil-level/protection inspection under operating procedure.
- Trip: immediate operator review under site protection procedure.
- Sensor mismatch/missing critical telemetry: verify instrumentation/communication before diagnosing physical damage.

## 7. Mathematical/formula specification

Persistence is an elapsed-time predicate, not a sample-count-only test:

$$
P_{on}=\mathbf{1}\left\{n_{valid}\ge3\;\land\;(t_{last}-t_{first})\ge30\ \mathrm{min}\;\land\;\max\Delta t_{adjacent}\le30\ \mathrm{min}\right\}
$$

n_valid counts qualifying valid observations in a continuous evidence run; timestamps are observation times; gaps are adjacent qualifying observation intervals with intervening invalid/clear observations handled as breaks in the qualifying run. P_on is Boolean. This restates the established heuristic persistence. Use the same predicate on qualifying clear observations for recovery. Verified protection bypasses entry persistence.

No new weighted maintenance formula is authorized. HI weights/cap remain phase 03; anomaly score remains phase 02; validated proxy threshold remains phase 04/06. Decisions are the precedence table, not arbitrary HI/risk percentage bins.

## 8. Parameters and configuration

Entry/recovery: 3 valid observations spanning ≥30 minutes, no qualifying gap >30 minutes, heuristic. Site critical limits, protection semantics, latch-clear authority and operator action matrix are CONFIGURATION REQUIRED. Validated risk threshold comes from evaluation; no hardcoded 0.7/0.8/0.9. Emergency loading duration/envelope is not established and must not be invented.

## 9. Processing/algorithm flow

Validate freshness/status → inspect verified immediate protection/critical rules → update condition persistence and independent-family evidence → check PLAN rules → check WATCH/insufficiency → allow NORMAL only with adequate evidence → apply latch/recovery policy → attach recommendation/reasons → persist decision state. Score explanations may be displayed, but never feed the decision back into predictive features.

## 10. Data-quality and missing-data behavior

Unknown contact is not clear. Missing temperature/protection evidence produces WATCH with insufficient-data action unless a known critical condition overrides. Unavailable fault model is omitted rather than treated as zero risk. Missing rating prevents OVERLOAD reason. A source-unit temperature tail supports statistical concern, not a physical trip threshold. Stale evidence cannot silently sustain a claim of NORMAL.

## 11. Edge cases

Single spike; high predicted and observed temperature with small residual; negative residual; high load with no nameplate; correlated thermal signals; one severe family; two independent warning families; sensor-quality anomaly; trip with missing oil reading; cleared trip but no authorized latch clear; long gap during escalation/recovery; unvalidated high ML score.

## 12. Leakage/safety constraints

Advisory only: no relay/SCADA switching commands. No maintenance output or HI becomes a forecast feature/target. No unvalidated probability escalation. Do not call proxy prediction confirmed failure. Recommendations must match available evidence and operator-approved procedure.

## 13. Integration requirements

Preserve enum and existing recommendation/reason fields. Consume reason evidence and persistence from upstream with clear ownership; avoid multiple inconsistent timers. Define whether this module owns final priority/latch timer and reuse the same upstream event timestamps. Backend persists decision/evidence/version. Dashboard renders the action rather than recalculating priorities.

## 14. Testing requirements

Mandatory scenarios:

| Scenario | Expected priority |
|---|---|
| Complete clear reference operation | NORMAL |
| Historically high kVA, no rating, normal thermal behavior | WATCH |
| Above verified nameplate, normal temperature, no approved emergency envelope | WATCH; review duration/envelope |
| Isolated temperature spike without corroboration | WATCH |
| Persistent current imbalance | PLAN |
| Persistent positive residual with credible sensors | PLAN |
| Persistent MOG alarm | PLAN |
| Verified active oil-temperature trip | URGENT |
| Persistent severe heating plus confirmed low oil | URGENT |
| Experimental high risk alone | WATCH/research annotation |
| Missing temperature/protection coverage | WATCH/insufficient data |

Also test precedence, exact persistence time boundaries, invalid/clear observation breaks, gap reset, recovery, trip latching, correlated thermal evidence counted once, no automatic action side effects and deterministic replay. Run a synthetic sequence smoke test through available upstream interfaces.

## 15. Acceptance criteria

All scenarios and precedence pass. No single noisy statistic reaches URGENT. Protection override/clearing semantics explicit. Missing model/data does not create healthy zero risk. Recommendations trace to reasons and do not command unsafe automated operations.

## 16. Expected behavior

Evidence progresses NORMAL→WATCH→PLAN with persistence; verified trip can jump immediately to URGENT. Recovery needs qualifying clear evidence and trip operator policy. A high load alone does not imply asset failure.

## 17. Explicit non-goals

No new health score, predictor, protection setpoints, emergency loading authorization, maintenance calendar intervals or automatic switching.

## 18. Handoff to subsequent phases

Give evaluation the deterministic policy/scenarios and output trace. Give unified pipeline state/latch/contract requirements and reasons. Give release the operator configuration dependencies and advisory limitation.

## 19. Implementation-agent instructions

Implement only decision orchestration/recommendations and tests. Leave unresolved site policy explicit rather than using an invented safe-looking default. Synthetic test contact semantics are permitted only as labelled fixtures.

## Implementation Agent Prompt

Read AUDIT_PLAN.md and 05_MAINTENANCE_ENGINE.md. Inspect the repository, existing contracts, upstream evidence/state interfaces and any maintenance code before editing. Implement ONLY phase 05, preserving architecture/contracts and documented decision precedence, persistence and safety constraints. Do not invent operating limits, emergency permissions or validated probabilities. Do not modify unrelated phases. Add/update all scenario tests, run relevant tests and the required decision-sequence smoke check. Report changed files, tests/results and unresolved operator configuration/confirmation requirements. Stop after this phase.
