# Phase 08 — Model Metadata and Release

## 1. Phase objective

Package the implemented ML/Twin layer as a reproducible, versioned, demonstrable release candidate with truthful engineering/ML limitations and compatibility rules. Release documentation does not turn unsupported capabilities into validated ones.

## 2. Scope

Artifact metadata, model/configuration compatibility, source/split/threshold provenance, model card/methodology/runbook, final contract checks and release checklist. Metadata should already have been accumulated in earlier phases; reconcile it rather than reconstructing values from memory.

## 3. Dependencies

Depends on 00–07 acceptance/evaluation/integration evidence. Produces reproducible ML release bundle and handoff for backend/dashboard/simulator and future adapters. Blocks final ML release signoff. Metadata scaffold can be created earlier; final signoff requires completed gates. Do not publish/deploy/merge unless separately authorized by the repository workflow/task.

## 4. Inputs

Source hashes, canonical artifact provenance, contracts, configuration sources, fitted model/preprocessing/threshold artifacts, state format, training/evaluation reports, phase acceptance reports, demo scenario definitions and open organizer questions. Existing project develop/main policy must be inspected and respected.

## 5. Outputs

Versioned bundle/manifest and existing repository-appropriate methodology, model card, ML README, integration guide and demo runbook updates. Use established repository locations rather than creating redundant files. Include release checklist and unresolved-capability status. This specification does not mandate additional package files beyond the user's phase documents; coding-agent outputs follow repository conventions.

## 6. Technical specification

Required existing metadata: schema_version, feature_version, model_version, training_dataset_version, training_date, target_definition, feature_names, feature_order, preprocessing_version, evaluation_metrics.

Also record:

- raw/canonical hashes, source identity and duplicate/quality policy;
- actual train/validation/test boundaries, exclusion/censoring counts and independent episodes;
- target horizon/eligibility and feature cutoff policy;
- model family/hyperparameters/constraints and preprocessing fit provenance;
- calibration status, decision threshold and allowed operational use;
- thermal mode, units, b_0/b_A/b_J/τ and state warm-up/gap policy;
- threshold values/units/source/status, weights/cap/persistence and configuration version;
- rating/measurement side/CT/PT/cooling/liquid/insulation verification state;
- selected standards edition/applicability and lack of full compliance certification;
- state compatibility and reset/rollback behavior;
- synthetic scenario provenance and separation from empirical results;
- limitations, organizer questions and supported/unavailable outputs.

Semantic version policy follows project: MAJOR for breaking name/meaning/type changes, MINOR for backward-compatible fields, PATCH for clarification. Feature/model/preprocessing/config versions must change when their meaning or behavior changes. Exact version numbers depend on repository state and are not prescribed here.

A source-unit change or thermal coefficient change may invalidate persisted state. Declare compatibility or require reset/warm-up. Never reuse stale feature order or mix model and threshold versions. Keep rollback bundle and compatible configuration/state policy under repository conventions.

## 7. Mathematical/formula specification

No new numerical methodology. Metadata must preserve these identities without confusing scales:

$$
loading\_percent=100\,apparent\_power\_utilization
$$

Only when both use S/S_r with verified rated kVA; first percent, second dimensionless.

$$
\sum_j w_j=1,\qquad (w_T,w_E,w_L,w_O,w_P,w_A)=(0.30,0.20,0.10,0.15,0.20,0.05)
$$

Weights are heuristic dimensionless original weights; partial HI separately renormalizes available components and reports coverage. Store alarm=40 points, persistent cap allowance=20 points, verified trip HI=0 as policy provenance, not engineering standards.

Store τ in hours and all forcing coefficient units exactly; no sampling-dependent alpha surrogate. Store forecast horizon h=1 hour and target interval (t,t+h]. Store 30-minute gap, three valid observations spanning ≥30 minutes and warm-up influence tolerance 0.05 as configurable heuristics. Store statistical quantile choices separately from their fitted signal-unit W/C values.

RUL is unavailable. Future equivalent ageing integration/laws are retained in AUDIT_PLAN.md as deferred prerequisites only, not enabled release calculations.

## 8. Parameters and configuration

All configuration values must have unit, source/status, scope (asset/model/demo), effective date and version. Unknown nameplate, temperature/level semantics, contact interpretation and standard applicability stay CONFIGURATION REQUIRED/NEEDS CONFIRMATION. No production artifact inherits fictional demo settings. No unestablished release accuracy, latency or minimum-event numeric requirement is invented.

## 9. Processing/algorithm flow

Collect existing phase artifacts → correlate hashes/versions/interfaces → verify feature order and preprocessing/model/config compatibility → reconcile formula/threshold provenance → carry forward evaluation eligibility and limitations → run integration/demo release checks → update methodology/model card/runbook → mark ready or capability-limited with blockers → hand off. If metadata conflict is found, resolve from authoritative artifact/config source, never choose a plausible value.

## 10. Data-quality and missing-data behavior

Unavailable fields/capabilities are documented with reason and prerequisite. Missing metadata required to reproduce a model blocks that model's promotion, not justification to invent it. Missing physical configuration keeps source-unit/relative monitoring labels. Null predictions remain null in examples and demo screenshots.

## 11. Edge cases

Model artifact absent because validation failed; changed feature order; old state with new thermal parameters; source re-export changed hash; benchmark all-negative test; incomplete standards access; unknown timezone; demo constants accidentally in asset config; identical field name with changed semantics; partial capability release.

## 12. Leakage/safety constraints

Do not alter model selection using test results while labelling evaluation untouched. Do not hide few-event limitations. No proxy prediction marketed as confirmed failure. No certification/CPRI-approved claim without evidence. No RUL/HI lifetime conversion or autonomous control. Future CPRI adapter mapping requires domain-shift validation/retraining assessment even when schema names align.

## 13. Integration requirements

Bundle and API expose compatible schema/feature/model/config versions and inference eligibility. Backend persists versions with analytics. Dashboard uses documented units, statuses, coverage, evidence and simulation labels. Simulator documents fictional parameters and fault injection separately. Runbook reproduces startup/reset, replay, healthy/stress/abnormal/explanation/action and unavailable-risk behavior under declared versions.

Standards provenance: IS 2026 Part 7:2009 versus IEC 2018 are distinct; IS 6600 historical/withdrawn; IS 1180 rise limits are test-context references not alarms; IS 3639/10028 are contextual, no invented settings/intervals. Actual CPRI asset reports and full clause verification remain prerequisites for stronger claims.

## 14. Testing requirements

Manifest completeness and cross-artifact hashes; exact feature order; units/threshold/weight consistency; model/config/state incompatibility handling; deterministic versioned replay; null-risk/rating/unready thermal serialization; no excluded raw fields or WTI temperature feature; no target-derived predictors; no fake RUL. Execute established relevant module tests and final canonical→analytics→API/dashboard smoke, without broad unrelated test expansion. Verify runbook can reproduce declared scenarios.

## 15. Acceptance criteria

All required metadata and provenance available for enabled capabilities; unsupported ones explicitly disabled. Formula/threshold meanings match master and phase specs. Relevant tests/integration pass. Model card reports actual temporal support and calibration limits. Release checklist completed without claiming missing evidence. Repository release workflow followed; no unsolicited deployment/merge.

## 16. Expected behavior

Another team member can reproduce the same inference and understand each number's provenance. A source-unit monitoring release can be complete while nameplate loading, calibrated fault risk and RUL remain unavailable. Future data replacement has a clear adapter/config/validation/version path.

## 17. Explicit non-goals

No new model training methodology, new standard thresholds, rewriting completed phases, forced probability/RUL output, production certification, automatic publishing or unrelated repository cleanup.

## 18. Handoff to subsequent phases

Final handoff to team includes bundle/interface versions, runbook, evaluation/model card, unresolved asset/organizer questions and exact supported capabilities. Future work is explicit configuration/evidence acquisition and domain validation, not a silent schema change.

## 19. Implementation-agent instructions

Reconcile metadata against actual artifacts. Any upstream mismatch is a release blocker to report and narrowly fix only if within this scope; do not revise physics or ML decisions to make metadata agree. Stop with a reviewable release candidate and clear capability status.

## Implementation Agent Prompt

Read AUDIT_PLAN.md and 08_MODEL_METADATA_AND_RELEASE.md. Inspect the existing repository, contracts, artifacts, evaluation reports, metadata and release workflow before editing. Implement ONLY phase 08, preserving architecture/contracts and all established formulas, thresholds and limitations. Do not invent missing configuration, standards evidence, validated risk or RUL; do not modify unrelated phases. Add/update relevant metadata/compatibility tests, run the relevant tests and final integration/demo smoke validation. Report changed files, tests/results, release eligibility and unresolved configuration/organizer requirements. Do not publish, deploy or merge without separate authorization. Stop after this phase.
