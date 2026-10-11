# H02 — Backend contracts and transactional state

Implemented locally on 2026-10-09 on `develop` for manual team review.
**Acceptance remains BLOCKED on disposable PostgreSQL and live-broker evidence.**
The available backend tests pass; this is not a declaration that the SQL gate
passed or that H02 is fully accepted. H00/H01 approval is established by the user.
No H03/H04/H05/H06 implementation, commit, push or merge was performed.

## Repository state and preservation

Read-only preflight commands returned exit 0:

```text
git branch --show-current
develop

git rev-parse HEAD
29dcfaf5e12ef50446d1106c4994a721dc802476

git status --short
```

The initial status contained eight modified ML files and the pre-existing
untracked H00/H01 contract, fixtures, runtime, tests and execution report.
A SHA-256 baseline of all 38 pre-existing changed/untracked files was captured
before backend edits in `$env:TEMP/h02-existing-baseline.json`.
Preservation verification reported **38 checked, zero changed**.
The final branch and HEAD remain those above. Backend files had no pre-existing
changes. No earlier migration, H00 artifact or H01 source/report was edited.
Frontend, simulator, Modbus services and root Compose remain untouched.

## Exact changed paths

The following 57 backend paths were created or modified; the 58th path is this
new report, `docs/hackathon_readiness/execution/H02_BACKEND_CONTRACTS_AND_TRANSACTIONAL_STATE.md`.

```text
backend/.env.example
backend/alembic/versions/0004_hackathon_contracts_and_state.py
backend/app/api/v1/lossless_json.py
backend/app/api/v1/receipts.py
backend/app/api/v1/router.py
backend/app/api/v1/telemetry.py
backend/app/core/config.py
backend/app/main.py
backend/app/ml_client/python_client.py
backend/app/models/__init__.py
backend/app/models/analytics.py
backend/app/models/processing.py
backend/app/models/telemetry.py
backend/app/models/transformer.py
backend/app/mqtt/consumer.py
backend/app/mqtt/message_handler.py
backend/app/repositories/analytics_repo.py
backend/app/repositories/processing_repo.py
backend/app/repositories/telemetry_repo.py
backend/app/repositories/transformer_repo.py
backend/app/schemas/analytics.py
backend/app/schemas/common.py
backend/app/schemas/hackathon.py
backend/app/schemas/ingestion.py
backend/app/schemas/mqtt.py
backend/app/schemas/query.py
backend/app/schemas/state.py
backend/app/schemas/telemetry.py
backend/app/schemas/transformer.py
backend/app/services/hooks.py
backend/app/services/ingestion_diagnostics.py
backend/app/services/ingestion_service.py
backend/app/services/quality_stats.py
backend/app/services/query_service.py
backend/app/services/readiness_service.py
backend/app/services/replay_service.py
backend/app/services/runtime_lease.py
backend/app/services/semantic_payload.py
backend/app/services/transactional_ml.py
backend/H02_INGESTION.md
backend/pyproject.toml
backend/tests/hardening/test_readiness.py
backend/tests/ingestion/test_batch.py
backend/tests/ingestion/test_replay.py
backend/tests/ingestion/test_single.py
backend/tests/mqtt/test_consumer.py
backend/tests/mqtt/test_message_handler.py
backend/tests/read_api/test_latest.py
backend/tests/test_analytics_schemas.py
backend/tests/test_config.py
backend/tests/test_h02_contracts.py
backend/tests/test_h02_http_and_diagnostics.py
backend/tests/test_h02_postgres.py
backend/tests/test_h02_transactional_adapter.py
backend/tests/test_migrations.py
backend/tests/test_models.py
backend/tests/test_telemetry_contract.py
```

## Contract, persistence and migration

Contract 1.1.0 is consumed additively; valid legacy 1.0.0 remains accepted.
Canonical measurements and nulls are preserved. Protection accepts only bool
or integer 0/1 and normalizes to integer; analytics anomaly flags remain boolean.
Aware event timestamps are normalized to UTC, with at most microsecond precision.
Source receipt time cannot be forged. Absent acquisition/configuration metadata
remains unknown, rather than inferred from MQTT or a positive rating.

Typed acquisition captures source/lineage, timestamp/timezone status, units and
verification, side/map, snapshot, sequence and cadence. Replay assumptions and
synthetic verification are validated against their source kind. New nameplate
fields include frequency, vector group, impedance, rise limits, CT/PT, side,
insulation, losses and configuration provenance. New 1.1 configurations require
positive finite ratings/ratios; legacy 1.0 nonpositive values remain readable and
operationally ineligible as H00 specifies. PATCH validates the merged registry
before mutation; explicit null removes nullable values.

Migration **0004**, after untouched 0003, adds nullable acquisition/hash/canonical
payload/ingestion outcome/ML availability fields; nullable configuration and
analytics metadata/RUL JSONB; a legacy-default asset envelope version; and
`ingestion_receipts`/`ml_checkpoints` tables. Existing measurements, identities and
constraints remain. Old acquisition, configuration, metadata and hashes stay null.
Legacy rows without hashes are compared semantically rather than trusted as exact
retries. JSON fields have no shared mutable object defaults. RUL has a typed,
persistable shape only; no H05 estimator or energy algorithm is implemented.

`parse_ml_result` now recognizes metadata through the additive MLResultIn fields:
it no longer drops supported H00 metadata. ORM uses `ml_metadata` for the SQL
column `metadata` to avoid SQLAlchemy's reserved attribute. Metadata survives
ML parsing, ORM serialization, latest and analytics/health history. Extra reasons
stay typed strings in metadata, without expanding incompatible legacy enums.
Latest exposes analytics' own event timestamp and explicit availability; missing
ML produces null analytics, not a fabricated healthy result or borrowed old result.

## Runtime dependency and deployment

The backend declares the established `transformer-ml-runtime==0.1.0` dependency
because hashing uses its authoritative serializer even with inference disabled.
The approved pre-existing H01 wheel was installed; it was not rebuilt or retested.
Install that wheel before installing the backend when it is not published on a
package index. See [backend instructions](../../../backend/H02_INGESTION.md)
and [the existing H01 report](H01_ML_RUNTIME_AND_STATE.md).

Strict fitted readiness now checks actual H01 bundle construction, not just
Python callable importability. Missing strict artifacts yield not-ready.
Demo mode is explicit and labelled DEMO_UNVERIFIED_CONFIG/UNVERIFIED.
The new backend readiness unit test uses an empty artifact directory and does
not re-run H01's release suite or audit original artifacts. Operational forecast
outputs remain gated by existing release evidence.

One Python runtime process per database is supported. Settings reject multiple
declared workers; app startup holds a dedicated PostgreSQL advisory session lease
`(19002,110)`, and a second Python owner fails startup. Use `--workers 1`.
Lease acquisition/rejection is unit-tested; actual PostgreSQL lease concurrency
remains blocked. This guard is not horizontal synchronization of ML singletons.
Root Compose and deployment were not changed or tested.

## Candidate state and SQL transaction order

The adapter calls the existing H01 `PipelineSession.prepare`, `discard`,
`import_checkpoint`, `export_checkpoint` and
`install(candidate, database_committed=True)`; it defines no new checkpoint protocol.

1. Validate source inputs and preserve pre-coercion numbers.
2. Hold per-asset process locks and existing PostgreSQL asset row locks.
3. Compare semantic identity, then prepare a private H01 candidate.
4. Persist telemetry, analytics, alert/maintenance effects, receipt and candidate
   checkpoint in the same SQL transaction.
5. SQL commit events authorize installation only after commit.
6. Rollback discards the candidate; locks are released after state handling.

Every transaction reads the durable checkpoint before preparing, including after
a possible commit/install crash. The adapter uses H01's actual
`committed_event_time` envelope field. Incompatible/corrupt/configuration-changed
checkpoints retain the prior committed owner context, while newly retained telemetry
has null analytics and CHECKPOINT_RESTORE_FAILED/coverage loss. No unresolved trip
latch is implicitly cleared. Post-commit memory install failures are logged; the
next transaction restores durable state.

Batches commit chunks of 1,000. Intermediate candidates hydrate only a private
speculative branch. Rollback removes the whole failed chunk's writes/state, while
earlier committed chunks remain durable. Histories are loaded once per asset per
chunk, bounded by one hour plus its preceding observation and a 4,096 count cap.
At five-second cadence the query retains 720 prior in-hour observations plus
one boundary. H01 reports sparse/capped/gapped coverage. Rows accepted without
analysis after a checkpoint are not implicitly replayed into forward state.

The old bulk-write shortcut is bypassed for identity checks and the shared
transaction path. PostgreSQL performance and lifecycle equivalence are unverified
until their existing benchmark/regression tests execute.

## Receipts, retries, conflicts, late observations and replay

Semantic identity delegates to H01's canonical UTF-8 serializer and SHA-256,
verified against the frozen hash vectors in focused backend tests. Decimal input
precision survives HTTP/MQTT decoding; canonical text is stored alongside floats
and used to reconstruct history identities. Hashing excludes snapshot_id,
received_at and retry-only transport data exactly as H00 specifies.

Exact retry returns prior accepted analytics, without inference or repeated
effects/state advancement. Changed asset/time or supplied identity produces HTTP
409; the accepted observation/checkpoint/effects remain unchanged. A separately
committed conflict receipt uses the attempted canonical hash and accepted hash
when an already durable accepted asset/time row is available. The original
receipt is not overwritten.

`GET /api/v1/ingestion/receipts/{snapshot_id}` returns H00 COMMITTED/CONFLICT fields.
Independent connections cannot observe an uncommitted receipt; the route also
suppresses staged receipts on the writing session. Missing accepted receipt returns
404 with RECEIPT_NOT_COMMITTED. Server receipt marker timestamps are transaction
time, not measured physical commit instants; visibility after SQL commit is the
durability evidence. MQTT PUBACK remains separate.

Late records are auditable with REJECTED_LATE_OBSERVATION and no new forward
analytics/effects; they receive no accepted receipt because H00 has no committed
late receipt variant. POST returns the explicit outcome; the stored internal
outcome and latest availability reasons retain sequencing/ML failure evidence.

HTTP and MQTT share ingestion. Topic/payload mismatch, malformed source identity,
invalid timestamps/nonfinite numbers/contacts are rejected with sanitized reasons.
Queues and recent-rejection evidence stay bounded. MQTT status adds validated,
committed and conflicted record counters; existing error_count counts failures.
`GET /api/v1/ingestion/status` exposes process-local validated-attempt counters,
not a durable ledger or broker-delivery proof.

Replay requires a separate registered `replay_transformer_id`, distinct from
all origins. It preserves event times and origin asset/run/units, and unknown
legacy provenance remains unknown with an explicit replay assumption. A fresh
run needs fresh destination identity if event times overlap: changed run lineage
is a conflict. Live history, checkpoints and latches are not backfilled.

The legacy stateless stub remains for legacy clients/tests, but contract 1.1
ingestion does not treat its outputs as operational analytics. Remote HTTP
ingestion remains explicitly unavailable until a compatible candidate-state
protocol exists; its existing client API/probe tests still work.

## Actual commands and outcomes

Environment: Windows, Python 3.13.7. Verification Python was
`$env:TEMP/h02-backend-verification/venv/Scripts/python.exe`.
All pytest/pip/alembic commands below ran from `backend/` using that interpreter.
The environment installed FastAPI 0.143.0, Pydantic 2.14.0, SQLAlchemy 2.0.54,
psycopg 3.3.6, Alembic 1.20.0 and pytest 9.1.1.
No H00 fixture suite, H01 regression/release/packaging suite was rerun.

### Passed

- `python -m venv "$env:TEMP/h02-backend-verification/venv"`: exit 0.
- `python -m pip install -e '.[dev]'`: exit 0, initially and after declaring the
  H01 runtime dependency.
- `python -m pip install "$env:TEMP/h01-runtime-verification/wheels/transformer_ml_runtime-0.1.0-py3-none-any.whl"`:
  exit 0; existing approved wheel SHA-256
  `72e5fdeec50b56915d2f8624c1e2b07f38fffd10f9aae9eca9eebb99a3df5e89`.
- Requested focused command, exit 0, **345 passed**:

```text
python -m pytest tests/test_telemetry_contract.py tests/test_transformer_schemas.py tests/test_analytics_schemas.py tests/ml_client tests/mqtt/test_message_handler.py
```

- Final affected command, exit 0, **384 passed, 33 skipped, 45 warnings**:

```text
python -m pytest tests/test_telemetry_contract.py tests/test_transformer_schemas.py tests/test_analytics_schemas.py tests/ml_client tests/mqtt/test_message_handler.py tests/test_h02_contracts.py tests/test_h02_transactional_adapter.py tests/test_h02_http_and_diagnostics.py tests/test_config.py tests/test_models.py tests/ingestion/test_quality_stats.py tests/ingestion/test_lifespan.py tests/hardening/test_readiness.py -q
```

- Earlier affected run before adding readiness checks: **382 passed, 15 skipped**.
  New contract/adapter/HTTP-only and readiness check: **14 passed, 18 skipped**.
- After correcting advancement flags to refer only to successfully installed
  H01 state, `python -m pytest tests/test_h02_transactional_adapter.py tests/test_h02_http_and_diagnostics.py -q`:
  exit 0, **7 passed**. Stateless stub outputs do not claim state advancement.
- `python -m ruff check app tests/test_h02_contracts.py tests/test_h02_transactional_adapter.py tests/test_h02_http_and_diagnostics.py tests/test_h02_postgres.py --select F --output-format concise`:
  exit 0 after unused-import cleanup. This is a focused F-code check, not full lint.
- `python -m alembic upgrade head --sql`: exit 0; generated PostgreSQL DDL
  through 0004. **Offline compilation only**, no database upgrade occurred.
- `git diff --check`: exit 0 (existing CRLF warnings were informational).
- SHA-256 preservation/scope verification: exit 0, all 38 pre-existing files
  unchanged; all new edits confined to backend and this report.
- Final scope count: 58 H02 paths, zero outside scope. New documentation link
  check: exit 0, zero broken links. Final PostgreSQL-module collection:
  `python -m pytest tests/test_h02_postgres.py -q`, exit 0, six infrastructure skips.
- Actual normalization/hash example below: exit 0.

Tests demonstrate H00 acquisition/metadata serialization, null legacy input,
release gating, registry provenance/ratios/removal, exact hash vectors including
UTF-8, high-precision HTTP/MQTT decoding, invalid JSON/duplicate keys, real H01
candidate discard/install/private batch staging/restart/corrupt-checkpoint behavior,
single-owner lease rejection and bounded MQTT diagnostics. Adapter persistence
and lease tests use mocks and manual event invocation: **unit evidence only**.

### Failed during development, then resolved

- First requested focused run: exit 1, **8 failed, 337 passed**. Failures were old
  exact field-set assertions, legacy source-label injection assumptions and MQTT
  nonfinite-token rejection categorization. Assertions were updated to explicitly
  test additive fields, unknown provenance and sanitized INVALID_JSON outcomes.
- First added boundary run: exit 1, **3 failed, 28 passed, 6 skipped**. UTF-8 fixture
  decoding, expected MLClientError wrapping and the old 60-row default assertion
  were corrected without changing the verified fixtures.
- A later affected run: exit 1, **2 failed, 380 passed, 15 skipped**; an initial
  targeted retry also had 2 failures. The new adapter referenced the wrong
  checkpoint timestamp key. It now reads actual H01 `committed_event_time`;
  final focused runs pass.
- Initial focused Ruff check: exit 1, 11 unused-import/variable findings;
  patched narrowly, final check passes.
- Some read-only path lookups returned exit 1 for absent guessed test paths;
  actual counterparts were located. Initial default sandbox shell execution
  encountered infrastructure failure; commands were run through approved execution.
- Automatic approval review rejected a truncation step intended before a service
  rewrite because it risked losing code. It did not execute. The service was
  subsequently changed with an explicit patch; no user/teammate files were lost.

### Skipped and blocked

Final database/broker command returned exit 0 but **13 passed, 60 skipped**:

```text
python -m pytest tests/test_migrations.py tests/ingestion tests/read_api/test_latest.py tests/read_api/test_transformers.py tests/read_api/test_maintenance_read.py tests/hardening/test_repository_recovery.py tests/alerts/test_lifecycle.py tests/alerts/test_concurrency.py tests/test_h02_postgres.py tests/mqtt/test_consumer.py tests/mqtt/test_broker.py -q
```

An earlier database-focused invocation reported 11 passed/50 skipped. All
SQL-dependent skips cite unset TEST_DATABASE_URL; passing cases are non-SQL checks.
The final focused run's 33 model/readiness skips have the same cause.
MQTT_TEST_HOST is also unset. No live broker or PostgreSQL acceptance proof exists.

`docker info --format ...` returned exit 1 because Docker's Linux-engine named
pipe was unavailable. TEST_DATABASE_URL was unset; local psql/postgres/initdb
executables were not available. No production/operator database was contacted.
No SQLite replacement was used. Deployment, database upgrade/downgrade execution,
actual commit visibility, concurrent lease enforcement, rollback/recovery API
round trips, performance, alert/maintenance SQL lifecycle and broker-to-SQL delivery
are **BLOCKED**, not passed. New disposable PostgreSQL tests are supplied for
those behaviors; no claim is made that their SQL assertions executed.

Warnings are FastAPI/Starlette TestClient deprecation and existing H01 NumPy/pandas
timedelta deprecations. H01 algorithms were not altered to suppress them.

## Concrete input/output

Actual local normalization/hash command created this input (legacy source unknown):

```json
{"transformer_id":"H02-EXAMPLE","timestamp":"2026-10-09T00:00:00Z","oil_temperature":42,"oil_temp_trip":0}
```

The normalized model has schema_version 1.0.0, acquisition/source_name null,
oil_temperature 42.0, oil_temp_trip 0, all omitted measurements null.
Its actual canonical snapshot hash is:

```text
c1f85854b1fbcbeffccb3ba48cf06ccd71ccf8def481b9aa6aa68f6e7e7429a7
```

Before any ingestion, the receipt API's defined response is HTTP 404:

```json
{"error":{"code":"RECEIPT_NOT_COMMITTED","message":"No committed receipt exists for this snapshot","details":{"snapshot_id":"c1f85854b1fbcbeffccb3ba48cf06ccd71ccf8def481b9aa6aa68f6e7e7429a7"}}}
```

After accepted SQL commit it returns the H00 receipt shape with that snapshot/hash,
asset/time, server timestamps, accepted hash, COMMITTED/ACCEPTED and explicit
analytics availability. This post-commit example is a specified API behavior,
**not an observed SQL response**. HTTP decoding/normalized hashes and H01 candidate
responses were actually exercised by unit tests.

## Remaining gates and risks

- Supply disposable PostgreSQL with CREATEDB permission, then execute migration,
  transaction visibility, rollback/retry, restart, concurrency, registry/history,
  existing lifecycle and benchmark tests. **H02 acceptance is not complete until
  this gate passes.**
- Supply a disposable MQTT broker and execute real transport-to-SQL tests; PUBACK
  alone is insufficient.
- Verify the application runtime lease against that PostgreSQL instance, including
  startup/reload/shutdown and connection-loss behavior.
- Measure batch performance after bypassing unsafe bulk writes. Source/batch
  identity ordering, partial-chunk commit recovery and lifecycle assertions remain
  unexecuted SQL gates even though adapter unit tests pass.
- Confirm deployment supplies the approved H01 wheel and its artifact directory;
  no release accuracy or operational validation has been inferred from demo tests.
- Configuration-changing checkpoints fail safely; owners need deliberate compatible
  state migration/reinitialization semantics rather than an implicit trip reset.
- Remote ML needs a candidate-state protocol before it can perform transactional
  ingestion. No horizontal ML-state deployment is supported.
- Existing legacy server-added source labels cannot be reverse-inferred as original
  source evidence; changed semantic legacy retries conflict rather than silently
  overwriting a contact.

The tested H01 candidate adapter is available to backend integration. Its actual
database transaction guarantee remains blocked. The exact next dependent phase
is **H03 (source simulator/Modbus/MQTT bridge and receipt consumption)**; H04 also
consumes the additive APIs. No next phase was started.

