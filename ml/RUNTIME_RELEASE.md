# H01 runtime installation and state ownership

H00 [contract 1.1.0](../docs/contracts/hackathon-v1.1.md) remains authoritative.
Packaging version `transformer-ml-runtime 0.1.0` does not change the existing
artifact, feature, preprocessing or fitted model versions (`1.0.0`).

From the repository root, build and export:

```powershell
python -m pip wheel ./ml --no-deps --wheel-dir <wheel-directory>
python -m ml.pipeline.runtime export --source data/processed --destination <new-artifact-directory>
python -m venv <new-venv-directory>
<venv-python> -m pip install -r ml/requirements-runtime.lock
<venv-python> -m pip install --no-deps <wheel-directory>/transformer_ml_runtime-0.1.0-py3-none-any.whl
```

The dependency lock records the clean Windows Python 3.13 environment actually
tested in H01. Other Python/platform combinations need their own installation
verification. The wheel includes eight explicitly selected runtime packages;
no datasets, notebooks, tests, evaluation reports or fitted JSON are included.
The separate export contains the original manifest and only thermal, anomaly
and forecast parameter JSON, copied byte for byte. Export never rewrites the
manifest. Its references to non-runtime provenance files remain historical;
full provenance verification is performed in the source repository. Runtime
verification checks the three required parameter hashes and compatibility.
Keep the manifest with the owner's trusted release; matching its declared
hashes is integrity verification, not a signature or evidence of physical units.

Set `ML_ARTIFACT_DIR` to the exported directory for the installed runtime.
`ML_RUNTIME_MODE=STRICT_FITTED` is the default: missing, corrupt, unsupported
versions or incompatible parameter/feature encodings raise `BundleNotReadyError`.
Original fitted artifacts are present locally and all eleven original provenance
hashes passed. This is a capability-limited research release: operational
forecast probabilities and confidence remain null. The previously swallowed
anomaly loader error is repaired by mapping the actual writer's
`selected_a_on`/`persistence_config` into the existing config class, preserving
the original fitted thresholds. Forecast preprocessing uses the writer's
top-level `preprocessing`; legacy nested `primary_experiment.preprocessor` is
also accepted when unambiguous. Neither artifact loading nor packaging releases
the forecast. No model was trained or recalibrated.

Explicit `ML_RUNTIME_MODE=DEMO_UNVERIFIED_CONFIG` (or the loader's `mode=` argument)
selects existing coded defaults with bundle `demo_unverified_coded_config_v1`,
model identity `DEMO_UNVERIFIED_CONFIG`, and unverified configuration readiness.
It never uses the fitted identity or enables operational forecast output.
Component metadata retains demo, coverage and unit reasons. Direct construction
of `PipelineBundle(...)` is an explicit unverified custom configuration, useful
for controlled tests; it is not a fitted release.

## Backend transaction integration

```python
from ml.pipeline import PipelineSession

session = PipelineSession()  # strict artifacts required
candidate = session.prepare(transformer, record, history)
if candidate.outcome in ("CONFLICT", "REJECTED_LATE_OBSERVATION"):
    return candidate.ingestion  # 409, null analytics, no checkpoint or mutation
# Backend locks the registered asset and persists its accepted observation,
# analytics, receipt and candidate.checkpoint in ONE database transaction.
try:
    backend_transaction(candidate)  # H02 owns this implementation
except Exception:
    session.discard(candidate)
    raise
session.install(candidate, database_committed=True)
```

The flag is the backend's attestation, not ML verification of a database commit.
Prepared ingestion outcomes have `forward_state_advanced=false`; preparation
alone never advances committed memory or proves a committed receipt. Returned
result/checkpoint objects are review copies. Installation uses the private
candidate state, requires a current per-asset revision, and consumes the token
once. Discard is safe to repeat. Export returns committed state only. Concurrent
candidates can become stale: H02 must serialize the asset transaction across
all workers before preparing, committing and installing. After a crash between
database commit and install, restore the database checkpoint. Do not install a
second stale candidate after its database transaction has already committed.

`session.export_checkpoint(asset_id)` returns the frozen H00 envelope, or null
before the first acceptance. `session.import_checkpoint(checkpoint, transformer)`
validates schema/category, contract, bundle, feature/model/preprocessing and
configuration versions, plus original manifest digest, configuration content
and ML parameter fingerprints, causal history and last semantic identity. Category payload
versions are `1.0.0`. Timestamp and Decimal payloads use explicit `$utc` and
`$decimal` JSON objects; enum values and numpy scalars use native JSON values.
The maintenance payload contains trip latch/time, clear policy, escalation
and every persistence run. The H05 synthetic degradation category is versioned
and null until its owning phase populates it; H01 implements no RUL algorithm.

Failed import leaves committed state intact and quarantines further prepare or
install for that asset until a compatible checkpoint restores successfully.
There is no automatic unsafe fallback after checkpoint failure. A cold asset
exposes unknown protection context and reduced coverage; protection contacts
and unresolved trip latches survive gaps and explicit analytical resets.
Reinitialization preserves accepted time/hash/retry identity. A changed contact
at that identity stays a conflict. Checkpoint persistence is required to retain
this context across process restarts.

`analyze(transformer, record, history)` remains available as the eager in-memory
compatibility API. It has no database transaction guarantee. On a cold asset,
prior history hydrates once in chronological order; subsequent supplied history
is checked against cached accepted identities without replay. Mixed assets,
changed cached history, and unprocessed newer history are rejected. Use a
separate cold session for backfill and a separate registered asset for replay;
H02 owns registration, authorization and durable receipt checks.

History retains the trailing hour plus one boundary observation, capped at
4096 rows. Five-second cadence retains 721 rows after the current observation,
providing approximately 720 prior observations on the next inference. Coverage
counts intervals within 1.5 times the declared cadence, clipped to the hour;
unknown cadence has unknown continuity and zero supported covered duration.
Sparse/gapped/capped history produces explicit coverage reasons. The existing
30-minute continuity and thermal warm-up algorithms remain in place.
Cached identical retries return their original result, including older retained
identities; changed payloads produce explicit conflicts. Older identities outside
the bounded cache are rejected as late: H02 must consult durable receipts to
classify old retries precisely. No late input mutates forward state.

If strict runtime loading or inference is unavailable, H02 may retain accepted
telemetry with null analytics and explicit coverage loss. It must preserve the
last compatible checkpoint/protection context and must not infer healthy status
from unavailable analytics. Database behavior is outside H01's tests.

Only field evidence can authorize loading: rating in kVA, suitable verified
evidence or explicitly synthetic config, power in matching verified/synthetic
kVA and matching measurement side. A positive legacy rating is insufficient.
Synthetic configuration is eligible only for simulated origin. Legacy camel-case
kV conversion requires known unit and verification evidence; ambiguous values
are retained without conversion. WTI remains a status field.

The [H01 execution report](../docs/hackathon_readiness/execution/H01_ML_RUNTIME_AND_STATE.md)
records actual tests and remaining H02 integration work.
