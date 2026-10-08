# Phase 07 — Unified ML/Twin Pipeline

## 1. Phase objective

Integrate the established modules into one deterministic, stateful, quality-aware canonical-to-analytics interface for backend and dashboard, without adding analytical methodology.

## 2. Scope

Orchestration, per-asset state, approved response schema, error/null/status handling, replay/idempotency, batch/stream equivalence and dashboard/API smoke integration. Module candidate evaluation comes from phase 06; end-to-end checks are performed here.

## 3. Dependencies

Depends on accepted 00–06 interfaces and evaluation eligibility. Produces stable inference integration for 08/backend/dashboard. Blocks release/demo integration. Contract harness can be built with fixtures independently; real promotion requires upstream gates. Must validate before release.

## 4. Inputs

Canonical TransformerRecord(s), verified or incomplete asset config, versioned model/preprocessor/threshold bundles, source quality metadata, per-asset feature/thermal/persistence state, event-time ordering and caller replay context. Never accept raw Kaggle source names at the ML interface.

## 5. Outputs

One stable analytical result per asset/timestamp using approved existing fields:

- transformer_id, timestamp;
- loading_percent when supported;
- thermal_model_temperature, thermal_residual, thermal_state;
- anomaly_score, anomaly_flag, reason_codes[];
- health_index, health_components, health_reason_codes[];
- fault_risk, predicted_fault, prediction_confidence;
- maintenance_priority, maintenance_recommendation;
- schema_version, feature_version, model_version and documented metadata.

Approved additive metadata must explicitly cover inference status/missing features, per-component validity/coverage/readiness, model mode/units, target/horizon/calibration eligibility, evidence thresholds/persistence and configuration/preprocessing versions. Do not silently treat an illustrative complete-response example as an exhaustive rejection of already documented component outputs; resolve contract fields explicitly with existing schema/version policy.

## 6. Technical specification

Execution dependency: validate → causal features/configured loading → thermal state/residual → anomaly and approved fault branch → HI → maintenance → response/evidence serialization. Fault branch does not consume HI, maintenance or alarm-derived anomaly. HI does not require forecast. Missing forecast must not block other analytics.

Maintain asset-isolated rolling history, thermal state, anomaly/maintenance persistence and trip-latch context. Support deterministic history replay and arbitrary batch boundaries. Retried identical asset/time observations must not integrate twice. Define repository-appropriate reject/replay policy for late observations; never integrate negative elapsed time. Configuration/model changes require explicit state compatibility check/reset, not silently mixing old state and new parameters.

Runtime knows source-unit mode versus verified physical mode. No °C, percent level or nameplate utilization appears without evidence. Preserve canonical excluded fields and WTI restrictions. Pipeline is advisory and has no electrical-control side effect.

## 7. Mathematical/formula specification

No new equations are authorized. The integration invariants are:

$$
loading\_percent=100\frac{S}{S_r},\qquad apparent\_power\_utilization=\frac{S}{S_r}
$$

S/S_r are kVA/kVA; first output percent, second dimensionless; both null without verified rating. Do not multiply twice or display the ratio as percent without conversion.

$$
r_t=T_t-\widehat T_t
$$

T/T-hat share the oil source/verified temperature unit; residual remains signed and unavailable during warm-up.

$$
0\le a\le1,\qquad0\le H\le100,\qquad0\le p\le1
$$

a is abnormality severity; H operating-condition points; p validated next-hour proxy probability only. These quantities are not interchangeable; null values do not enter these inequalities or become zero.

Thermal exponential recurrence is owned by phase 01, severity by 02, HI weights/cap by 03, target by 04 and maintenance rules by 05. Integration must invoke those implementations rather than copy/reimplement formulas independently.

## 8. Parameters and configuration

Bundle/config/schema/feature versions, state compatibility policy, approved metadata schema, replay mode, input availability/time semantics, missing-feature model rules. Shared locked values remain 1-hour horizon/window, 30-minute gap, 3 valid observations over ≥30 minutes, HI weights/cap/protection conventions. No new service latency target or extra numerical timeout was established; measure CPU inference and report instead of inventing a pass threshold.

## 9. Processing/algorithm flow

Resolve bundle/config → validate schema/time/identity → deduplicate/replay policy → load compatible asset state → build causal features with historical coverage → calculate only supported loading → integrate thermal prediction and residual → run available detectors and gated proxy inference → calculate partial/full HI → resolve maintenance priority with evidence → serialize finite values/nulls and versions → persist state/result atomically under repository conventions → return consistent response.

Failure policy must be explicit: a component's unavailable state does not produce global silent success; known critical protection still propagates. Do not obscure software errors as healthy missingness.

## 10. Data-quality and missing-data behavior

Missing numeric result serializes as JSON null, not NaN/Infinity/zero. Boolean unknown is null/status rather than false. No rating gives RATING_UNAVAILABLE and null loading. Unready thermal gives null residual/state readiness. Insufficient forecast validation gives null risk fields. Partial HI preserves component nulls and coverage. Missing critical data yields WATCH unless verified critical evidence overrides. Distinguish an ingestion error from a valid record with unavailable analytic capability.

## 11. Edge cases

One-row stream; multi-asset interleaving; restart mid-window; repeated message; late row; partial batch; empty history; long gap; source timezone unknown; daylight-saving-aware known zone; model/config swap; one component raises validation error; same timestamp two assets; no optional fault artifact; trip with missing temperature; no rated asset metadata.

## 12. Leakage/safety constraints

Online pipeline never refits from incoming future test outcomes. Event-time/availability policy prevents look-ahead. No result feedback into the forecast vector. No dashboard-side recalculation. No control commands. Synthetic scenario metadata is not a predictor. Replaying the same data under different speed must not change elapsed-time analytical results.

## 13. Integration requirements

Backend consumes stable response, not private internal dataframe columns. Persist analytics with data/config/model versions. Dashboard minimum: operating/data state, loading or actual kVA/current with unavailable rating, observed/model oil signals and units, signed residual/readiness, anomaly score/flag, HI/components/coverage, validated risk/target or unavailable, maintenance recommendation/reasons and trends.

Graphs must show gaps. Reason display includes actual value, unit, threshold/reference source, duration and model limitations. Historical replay and simulation are labelled.

Demo sequence: healthy ready reference → increased load with lagged thermal response → persistent observed/model divergence → validated or explicitly experimental/simulated risk view → inspect evidence → maintenance action. Trip may immediately give URGENT; recovery obeys persistence/latch policy. Fictional simulator ratings/constants must be declared separately. A simulator using the detector's same exact thermal law does not establish independent validation.

## 14. Testing requirements

Contract serialization including nulls/unknown Booleans; excluded-field absence; stable feature order; batch/stream/chunk equivalence; independent assets; deterministic replay speed; retry idempotency; late-row policy; restart state continuity; long-gap reset; incompatible bundle/config reset; no forecast artifact fallback; trip override despite missing inputs; observed/model/residual unit agreement; correct loading ratio/percent; dashboard/API smoke for all six demo stages and partial data. Rerun affected phase-06 checks after integration, preserving fixed splits.

## 15. Acceptance criteria

One canonical input path yields a traceable stable response with accurate status/units. Batch and stream agree under declared semantics. No duplicated calculations or target-derived feature feedback. Backend/dashboard can consume result without raw field knowledge. End-to-end smoke passes; unsupported forecast/RUL/physical quantities remain unavailable.

## 16. Expected behavior

A judge can follow measured signal → model expectation → reason/threshold → HI contribution → maintenance action. Unknown rating and unvalidated forecast are visible and do not break the demo. Long gaps/reset are not hidden as smooth valid predictions.

## 17. Explicit non-goals

No full dashboard redesign, backend schema overhaul unrelated to approved contract, retraining methodology change, new model family, automatic control or new RUL field/value. No deployment/publishing implied by this phase.

## 18. Handoff to subsequent phases

Give phase 08 stable interface/version map, state format/compatibility behavior, smoke results, demo trace and unresolved integration/configuration limits. Backend/dashboard teams receive field meanings and null/status behavior.

## 19. Implementation-agent instructions

Integrate existing phase implementations; do not duplicate algorithms to make outputs align. If an upstream gate fails, preserve unavailable semantics and report it rather than redesigning that phase within integration work.

## Implementation Agent Prompt

Read AUDIT_PLAN.md and 07_UNIFIED_ML_TWIN_PIPELINE.md. Inspect the actual repository, module APIs, contracts, state handling and backend/dashboard boundaries before modifying anything. Implement ONLY phase 07, preserving architecture/contracts and the documented formulas by calling their owning modules. Do not invent units, ratings, thresholds or validated model outputs; do not modify unrelated phases. Add/update integration tests, run relevant tests and the required batch/stream/replay/API smoke checks, including null forecast and missing rating. Report changes, tests/results and unresolved configuration/confirmation or upstream gates. Stop after this phase.
