# H01 — ML runtime packaging and transactional state

Completed locally on 2026-10-09 for manual team review. H00 approval was explicitly
confirmed by the user. Contract `1.1.0` and all 19 H00 files remain unchanged.
No H02/H05 implementation, database integration, deployment, commit, push or merge
was performed. The next dependent phase is **H02** (backend persistence and
transaction integration); H05 subsequently consumes the versioned state extension.

## Preflight and changed paths

Actual pre-edit commands, each exit 0:

```text
git branch --show-current
develop

git rev-parse HEAD
29dcfaf5e12ef50446d1106c4994a721dc802476

git status --short
?? docs/contracts/
?? tests/
```

Those untracked directories were pre-existing verified H00 work and were preserved.

Modified:

- `ml/pipeline/__init__.py`
- `ml/pipeline/asset_config.py`
- `ml/pipeline/bundle.py`
- `ml/pipeline/orchestrator.py`
- `ml/pipeline/state.py`
- `ml/prediction/model.py`
- `ml/tests/test_pipeline.py`
- `ml/tests/test_release.py`

Created:

- `ml/pipeline/identity.py`
- `ml/pipeline/runtime.py`
- `ml/pipeline/session.py`
- `ml/pyproject.toml`
- `ml/requirements-runtime.lock`
- `ml/RUNTIME_RELEASE.md`
- `ml/tests/test_session.py`
- `ml/tests/test_bundle_runtime.py`
- `ml/tests/test_contract_compatibility.py`
- `ml/tests/verify_installed_runtime.py`
- `docs/hackathon_readiness/execution/H01_ML_RUNTIME_AND_STATE.md`

Packaging generated `ml/build/` and `ml/transformer_ml_runtime.egg-info/`; only
these newly generated directories were removed after verifying their absolute
paths stayed inside this workspace. Wheels, exported artifacts and the clean
virtual environment remain under `%TEMP%/h01-runtime-verification`, outside Git.
Backend, frontend, simulator, database models and Compose were untouched.

## Release and compatibility decisions

The original permitted fitted artifacts and release manifest **are present** in
`data/processed/`. `load_release_manifest().verify_artifact_hashes()` reported true
for all eleven declared raw/processed files. The original manifest/artifacts were
not edited or regenerated. No training or probability calibration ran.

`STRICT_FITTED` is the default. It requires the manifest and all three runtime
parameter artifacts; it verifies declared SHA-256 hashes, supported manifest and
artifact versions, forecast feature order/preprocessing, coefficients/scales,
and anomaly/thermal configuration encodings. Missing, corrupt or incompatible
releases raise `BundleNotReadyError`; no silent coded fallback remains.
The fitted bundle identity remains `processed_bundle_v1`; artifact, feature,
preprocessing and model versions remain `1.0.0`. Packaging version `0.1.0` is a
distribution version, not a new fitted model version. Input/output envelope
`1.1.0` is additive; valid legacy `1.0.0` remains representable and tested.

`DEMO_UNVERIFIED_CONFIG` requires an explicit loader argument or
`ML_RUNTIME_MODE`. It uses existing coded parameters, bundle
`demo_unverified_coded_config_v1`, model identity `DEMO_UNVERIFIED_CONFIG`,
configuration readiness `UNVERIFIED`, and explicit component/reason metadata.
It never claims a fitted/validated identity. Direct `PipelineBundle(...)`
construction is also explicitly unverified custom configuration. Operational
`fault_risk`, predicted fault and prediction confidence remain null.

The forecast loader now reads the real writer's **top-level** `preprocessing`.
It also accepts the old nested `primary_experiment.preprocessor` encoding,
rejecting contradictory encodings, incompatible order and malformed parameters.
The real experiment writer now delegates unchanged artifact serialization to
`write_prediction_artifact`, which is exercised in a round-trip test using the
original writer output; no experiment was retrained for testing. Experimental
proxy output is available only in research metadata. Operational release stays
`INSUFFICIENT_VALIDATION`: the original validation partition has no positive
onsets and calibration/threshold gates remain unmet. The manifest's historical
target alias `next_hour_abnormal_onset` refers to the artifact/code target
`new_oil_alert_within_1h`; runtime metadata uses the actual artifact/code name.

An additional hidden loader defect was repaired: `AnomalyDetectorConfig` has
no `from_json_file` method. The previous loader swallowed that error. The new
loader maps the real writer's `selected_a_on` and `persistence_config` to the
existing `from_dict` interface and uses the original fitted thresholds. This
restores full serialized precision rather than silently substituting rounded
coded thresholds. Owning thermal, anomaly, health and maintenance algorithms
and weights were preserved.

## Public session and checkpoint API

See [runtime release instructions](../../../ml/RUNTIME_RELEASE.md) and the
unchanged [H00 contract](../../contracts/hackathon-v1.1.md).

`PipelineSession.prepare(transformer, record, history=())` runs against an
isolated copy and returns `PreparedInference`: candidate token, asset ID,
`ACCEPTED|EXACT_RETRY|CONFLICT|REJECTED_LATE_OBSERVATION`, result, checkpoint and
the frozen ingestion outcome shape. Preparation never advances committed state;
its ingestion object has `forward_state_advanced=false`. Conflict/late outcomes
have null analytics/checkpoint, HTTP mapping 409 and a separate ingestion reason.
They do not invent a legacy `inference_status` or reason enum value.

The backend owns its asset lock and database transaction. It persists telemetry,
analytics, receipt and candidate checkpoint, then calls
`session.install(candidate, database_committed=True)`. This flag is caller
attestation; ML does not verify a database commit. Candidate installation is
single-use and rejects stale per-asset revisions. `discard(candidate)` handles
rollback without changing committed bytes or results. Returned review copies
cannot alter the private candidate state used for installation.

`export_checkpoint(asset_id)` exports committed state, or null before acceptance.
`import_checkpoint(checkpoint, transformer)` validates completely before replacing
it. H00 checkpoint/category versions remain `1.0.0`, envelope contract `1.1.0`.
Compatibility checks include bundle/model/feature/preprocessing/configuration
versions, original manifest digest, nameplate content fingerprint and actual ML
parameter fingerprint. Same named versions with changed parameters are rejected.
All seven required categories persist: thermal; time-covered history and bounded
retry/result identities; anomaly; health; maintenance/protection runs, trip latch,
clear policy and escalation; coverage; and nullable versioned synthetic degradation.
No H05 degradation/RUL algorithm is implemented. Timestamps and Decimal values
use explicit reversible JSON tags; enum/numpy values become JSON scalars.

Failed restores preserve existing committed state and quarantine further
preparation/installation until a compatible checkpoint loads. This also protects
a fresh worker from treating a failed restore as a clean healthy asset. Gaps and
analytical resets preserve unresolved trip latches and accepted time/hash identity,
while restarting appropriate thermal/persistence warm-up. Reinitialization and
coverage loss are visible. Checkpoint import is not a substitute for durable
database checkpoint/receipt storage or multi-worker transaction serialization.

`analyze(transformer, record, history)` remains callable. Cold history hydrates
once, oldest first. Later history is consistency evidence, not replayed again;
mixed assets, changed cached identities and unprocessed newer history are rejected.
This compatibility API eagerly commits **in memory** and offers no SQL guarantee;
H02 must use the candidate API. Backfill needs an isolated cold session. Replay
requires a distinct registered destination, origin ID/run ID and original event
time; H02 still owns durable registration and authorization.

History retains a trailing hour and boundary observation, capped at 4096 rows.
The actual 722-record five-second inference test retains 721 rows and reports
coverage fraction 1. Sparse/capped/gapped history reports deficient coverage.
Supported duration counts intervals within 1.5 declared sampling intervals;
unknown cadence cannot establish continuous covered duration. Existing thermal
gap/warm-up and statistical persistence methods remain intact.

The production semantic hash matches all unchanged H00 vectors, including
Decimal precision, Unicode, timestamp normalization, nulls and boolean-to-integer
protection normalization. Source inputs cannot forge `received_at`; noncanonical
fields and invalid protection/timestamps are rejected. Exact cached retries return
the original result, even after a later accepted sample. Changed identities,
including trip 0→1, return conflicts. Older uncached observations are rejected as
late; H02 must query durable receipts for older retry/conflict classification.

Loading requires evidenced kVA rating, matched measured kVA units/verification
and measurement side. Synthetic nameplates work only with simulated origin.
Unknown provenance and units remain unknown; a `LIVE` label proves no authorization.
Legacy camel-case kV conversion requires actual known unit/evidence; ambiguous
values are retained without conversion. WTI status remains a status.

## Actual verification evidence

Commands ran from repository root unless noted. `$env:PYTHONDONTWRITEBYTECODE='1'`
was used for focused checks. JSON Schema checks used the already available
`%TEMP%/h00-jsonschema` dependency via `PYTHONPATH`; this is test tooling only.
The clean installed-package verification explicitly removed `PYTHONPATH`.

| Check / actual command | Result |
| --- | --- |
| Preflight commands above | PASS, each exit 0 |
| `python -m unittest ml.tests.test_pipeline ml.tests.test_prediction ml.tests.test_thermal_twin ml.tests.test_anomaly ml.tests.test_health_index ml.tests.test_maintenance` | PASS, 120 tests; baseline and post-change runs exit 0 |
| `python -m unittest ml.tests.test_release` | PASS, 26 tests, final exit 0 |
| `python -m unittest ml.tests.test_session ml.tests.test_bundle_runtime ml.tests.test_contract_compatibility` | PASS, final 24 tests in 41.681 seconds, exit 0 |
| Additional targeted restart/configuration/schema tests after fingerprint repair | PASS, 4 tests, exit 0 |
| `python -c "from ml.pipeline.manifest import load_release_manifest; print(load_release_manifest().verify_artifact_hashes())"` | PASS, all eleven true, exit 0 |
| `python tests/fixtures/hackathon/validate.py` | PASS: 15 JSON syntax/strict parse files, 10 schemas, 57 positive/negative examples, 13 arithmetic/eligibility cases, 10 traces, 3 hash vectors, query semantics and 17 original links; exit 0 |
| `python -m venv "$env:TEMP/h01-runtime-verification/venv"` | PASS, clean isolated Python 3.13 environment created, exit 0 |
| `python -m pip wheel ./ml --no-deps --wheel-dir "$env:TEMP/h01-runtime-verification/wheels"` | PASS, wheel built; final SHA-256 `72e5fdeec50b56915d2f8624c1e2b07f38fffd10f9aae9eca9eebb99a3df5e89`, exit 0 |
| `<venv-python> -m pip install <wheel>` | PASS, installed wheel plus declared dependencies into clean venv, exit 0 |
| `<venv-python> -m pip freeze --exclude transformer-ml-runtime` saved as `ml/requirements-runtime.lock` | PASS, twelve actual dependency pins recorded, exit 0 |
| `<venv-python> -m pip install -r ml/requirements-runtime.lock` | PASS, pinned environment verified, exit 0 |
| `<venv-python> -m pip install --force-reinstall --no-deps <final-wheel>` | PASS, final wheel installed, exit 0 |
| `python -m ml.pipeline.runtime export --source data/processed --destination "$env:TEMP/h01-runtime-verification/artifacts"` | PASS, only original manifest and three parameter files exported, exit 0 |
| From `%TEMP%/h01-runtime-verification`, `<venv-python> <absolute-repo-path>/ml/tests/verify_installed_runtime.py <exported-artifacts>` with `PYTHONPATH` removed | PASS, import resolves to venv `Lib/site-packages/ml/__init__.py`; strict/demo gates, inference, compatible restart and exact retry verified, exit 0 |
| `<venv-python> -m pip check` | PASS, no broken requirements, exit 0 |
| ZIP inventory assertions against the actual wheel | PASS, 29 entries; no datasets/notebooks/tests/adaptors/evaluation/artifact JSON, exit 0 |
| SHA-256 comparison against pre-edit H00 baseline | PASS, all 19 H00 files byte-for-byte unchanged, exit 0 |
| Final local-link resolution assertions on both new Markdown documents | PASS, four links resolve, exit 0 |
| Final Git changed/untracked-path scope and Python AST assertions | PASS, exactly 19 H01 paths plus preserved H00 files; Python syntax valid; develop/HEAD unchanged, exit 0 |
| `git diff --check` | PASS after removing one extra EOF blank line, exit 0 |

The installed dependency lock is for the actually tested Windows Python 3.13
environment: numpy 2.5.3, pandas 2.3.3, scipy 1.18.1, scikit-learn 1.9.1 plus
their pinned dependencies. No repository-path hacks were used for the installed
package test. The source-tree regression suite used the existing project Python;
the clean venv ran the installed runtime smoke/transaction round-trip test, not
the complete source-tree unittest suite.

Intermediate failures were real and corrected, not hidden:

- One PowerShell/Python inline-edit quoting error exited 1 before writing; an
  apply-patch context mismatch also prevented that attempted patch. Both were
  corrected with focused patches.
- Early strict-loader pipeline runs errored on the nonexistent anomaly loader
  and one wrong forecast import path; actual writer/config mapping and the
  existing `ml.prediction.target` import fixed them.
- Three legacy pipeline assertions expected the old late response or unsupported
  positive-rating loading. Tests now assert the frozen ingestion shape and add
  explicitly fictional provenance to loading arithmetic; algorithm assertions
  remain present.
- One new hash test failed because Windows default text decoding changed Unicode.
  Explicit UTF-8 fixed it; H00 vectors were never changed.
- An initial schema-output test failed because ingestion `reason` was omitted.
  The runtime now emits H00's required nullable reason field. The combined shell
  command's final exit was 0 because the following H00 validator passed; the
  unittest subcommand itself failed and was subsequently rerun successfully.
- The release reset test expected accepted timestamp/history erasure. It now
  strengthens the H00 identity/latch/warm-up assertions. A missing pandas import
  in that test caused one subsequent error and was fixed. No artifact readiness,
  forecast gates or algorithm assertions were removed to obtain green results.
- `git diff --check` initially failed on an extra EOF blank line; final check passed.

No required H01 check was skipped or remains blocked. The historical H00 validator
footer still mentions pending owner review; the user's explicit approval supersedes
that old text, which was preserved rather than rewritten.

## Concrete verified input/output

The final installed-wheel verification submitted:

```json
{"transformer_id":"INSTALL-CHECK","timestamp":"2026-10-09T00:00:00Z","oil_temp_trip":1,"schema_version":"1.1.0"}
```

Preparation returned an `ACCEPTED` candidate with `inference_status=INSUFFICIENT_DATA`,
`health_index=0`, `maintenance_priority=URGENT`, a latched trip, null `fault_risk`
and prediction confidence, and a JSON checkpoint. Before installation, committed
checkpoint export was null. Caller-confirmed installation made it available;
JSON export/import preserved it, and an identical retry returned `EXACT_RETRY`.
This is protection-contact behavior with unknown legacy provenance, not a
physical-life prediction or proof of a database commit.

## Regression comparison, remaining risks and acceptance

Before editing: 120 algorithm/pipeline and 26 release tests passed. After H01:
the same 120 and 26 pass, with explicitly revised assertions only for H00-required
late/config/reset behavior. New tests cover rollback bytes, single install,
stale candidates, restart/trip equivalence, incompatible schemas/versions/content,
one-hour full inference coverage, sparse/capped coverage, older retries, changed
contacts, late isolation, two assets, replay isolation, original artifact values,
strict missing/corrupt gates, demo opt-in, real writer round-trip and H00 schemas.
This is regression/contract evidence, **not empirical fitted-model accuracy**.

H02 now has a tested candidate-state interface. Its owner still must implement
database checkpoint/receipt persistence, asset locking across workers, crash
recovery after SQL commit, durable old-key conflict lookup, and retained telemetry
with null analytics/coverage loss when inference is unavailable. No SQL, broker,
deployment or frontend integration tests were claimed or run.

No original fitted artifacts or H01 owner inputs are missing locally. Operational
forecast release remains blocked by existing validation prerequisites; verified
physical units/nameplates and real-source life-history inputs remain source/owner
dependent. Original artifacts must be transferred through the permitted owner
channel for another machine; they are ignored locally and intentionally absent
from the source-only wheel. The trusted manifest must travel with the export.

H01's assigned implementation and verification criteria are met. End-to-end
database atomicity, operational fault-risk release, real RUL and energy outputs
are intentionally not H01 acceptance claims. Stop here for manual review;
**H02 is the next dependent phase**. No H02 or H05 work was started.
