# H01 — Deliver honest ML runtime and staged per-asset state

## AI CODING AGENT PROMPT

You are implementing one authorized phase of the Transformer Digital Twin on `develop`. Inspect the listed files and necessary imports/tests only; do not re-audit the repository. Read the phase prerequisites and the relevant F findings in `../GAP_ANALYSIS.md` (relative to this prompt). Verify the current branch and local changes before editing. Preserve teammate changes; stop on an ownership conflict rather than overwriting them. The planning baseline is develop `71c1b27200b91f3933c52692748935f4a62d63e8`; newer code requires a narrow relevant delta check.

Implement only the work below. Do not commit, push, merge, touch `main`, retrain existing models, rewrite valid thermal/anomaly/HI/maintenance algorithms, change frontend stack, or write to real transformer/protection controls. Do not change excluded canonical fields or turn missing values into zero. Preserve existing tests and honest null operational forecast. New future CLI/API paths below are implementation targets, not claims that they exist today.


### Objective, defects, owner and dependencies

Owner Person 1, ML/Digital Twin. Depends H00. Closes F03/P0, ML half of F13/P1 and F14/P1, and F18/P2; supplies checkpoint interface to H02 and state foundation to H05. H02 schema work, H03 and H04 may run alongside it. H02's transaction integration must wait for this interface's tests.

Inspect `ml/pipeline/{bundle,manifest,asset_config,state,orchestrator,__init__}.py`, existing `ml/tests/test_{pipeline,release,prediction,thermal_twin,anomaly,health_index,maintenance}.py`, `ml/ml_README.md`, existing Phase 00–08 plans under `docs/implementation/`, relevant parameter writers in `ml/`, and H00 addendum/fixtures. F03 is missing release files, not proof algorithms need retraining. F18 loader reads `primary_experiment.preprocessor` while the writer uses `preprocessing`.

### Exact work and expected files

1. Recover original fitted bundle/release manifest from the ML owner if available. Verify its declared hashes and feature ordering; package only permitted artifacts using a reproducible install/export mechanism. Add a narrowly scoped ML packaging manifest and dependencies for actual numpy/pandas/scipy/sklearn imports; do not copy every notebook/raw file into runtime. If artifacts are unavailable, implement an explicit opt-in DEMO_UNVERIFIED_CONFIG mode using existing coded parameters with distinct bundle id and metadata. Strict fitted mode must fail readiness for missing/corrupt files. Never emit processed_bundle_v1/model trained readiness for a fallback.
2. Repair forecast artifact loading by supporting the writer's actual serialized schema with validation and a round-trip test. Preserve the operational forecast release gate: loading a research model does not authorize fault_risk/confidence. No retraining or new probability calibration in this phase.
3. Implement H00's prepare/export/import/install state interface in a focused `ml/pipeline/session.py` (or equally small existing-state extension). Candidate processing must not mutate committed state. Persistable state includes dtype/time conversions, versions, last timestamp/payload hash, thermal state, anomaly persistence, trip/maintenance latches, time-covered history and a versioned extension area for H05 degradation. Reject incompatible checkpoints explicitly. Backward-compatible public `analyze(transformer, record, history)` remains callable; fix ignored history via documented hydration/consistency policy rather than replaying it twice on every sample.
4. Replace fixed 60-row retention as sole policy with time coverage for existing one-hour features plus a safe count cap. At 5-second cadence retain approximately 720 prior observations plus needed boundary; if capped or sparse, report reduced coverage. Preserve existing gap/warm-up methodology. Explicitly mark late live observations without changing forward state. Isolated replay/backfill uses a distinct session, not global live singleton.
5. Make identical same-key payload an idempotent return; changed same-key payload is a conflict, including trip 0→1. No stale last result for a changed contact. Preserve per-asset isolation. Interpret H00 verified/synthetic config eligibility correctly; convert explicit legacy camel-case kV only when its unit is known. Do not treat any positive number as verified real rating.

Expected changes: ML packaging/release instructions, narrow pipeline/bundle/state/asset config repair, new state/bundle tests, and execution report. Backend schemas/migrations, UI and simulator stay with their owners.

### Contracts, errors and safety

Use H00 metadata/config/provenance and staged checkpoint schema. Retain original thermal/anomaly/HI weights and null forecast. Missing oil/ambient unit cannot become °C; WTI contact cannot become hot spot. Failed state load yields visible readiness/coverage deficiency; no implicit clearing of protection context. Demo-unverified parameters remain visibly unvalidated even if unit tests pass.

### Acceptance and focused commands

From repository root, use `python -m unittest ml.tests.test_pipeline ml.tests.test_prediction ml.tests.test_thermal_twin ml.tests.test_anomaly ml.tests.test_health_index ml.tests.test_maintenance`; execute new session/bundle tests using their actual module names. Run `python -m unittest ml.tests.test_release` separately: if original release unavailable, report artifact-specific skips/errors and demo-mode gates truthfully; never delete assertions to green the suite. Install the new ML package into a clean venv and verify `from ml.pipeline import analyze` works without repo-path hacks; record actual package command created here.

Tests must demonstrate prepare/discard leaves committed bytes/result unchanged, prepare/install advances once, checkpoint round-trip and restart equivalence, incompatible versions fail, 1-hour history coverage at 5s, changed duplicate rejection, late record isolation and two assets with independent trip latches. Compare existing valid golden ML behavior before/after; no new empirical accuracy claim. H01 is done when H02 has a tested state API and strict versus demo-unverified runtime is distinguishable. Missing original artifacts block fitted release only; opt-in labelled runtime is the hackathon fallback.


### Completion report and stopping point

Report phase ID, changed paths, contract/version changes, actual commands and outcomes (passed/failed/skipped separately), unmet acceptance criteria, remaining inputs, and the exact next dependent phase. Include one concrete input/output example and any regression or integration evidence. Do not claim unavailable infrastructure tests passed. Update the phase execution evidence in `docs/hackathon_readiness/execution/` with a new phase-specific report; do not overwrite audit evidence. Stop after this phase's assigned outputs and focused checks. A blocked gate stays blocked; do not begin another phase or silently substitute stub results.
