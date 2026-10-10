# H02 backend integration

The authoritative interfaces are [H00](../docs/contracts/hackathon-v1.1.md)
and the established [H01 runtime instructions](../ml/RUNTIME_RELEASE.md).
H02 does not change either contract or any ML algorithm.

Install the approved H01 `transformer_ml_runtime-0.1.0` wheel first, then run
`python -m pip install -e '.[dev]'` from `backend/`. The backend now declares that
runtime dependency because semantic identity uses its exact serializer even when
inference is disabled. The wheel must be supplied by the H01 release workflow;
an unpublished package is not assumed available from PyPI. No raw data is packaged.

Set `ML_BACKEND=python`, `ML_PYTHON_ENTRYPOINT=ml.pipeline:analyze` and the approved
`ML_ARTIFACT_DIR`. `ML_RUNTIME_MODE=STRICT_FITTED` retains H01 readiness checks;
`DEMO_UNVERIFIED_CONFIG` is an explicit alternative with unverified configuration
and null operational risk. Run exactly one backend process with `--workers 1`.
`ML_RUNTIME_WORKERS` accepts only 1; `WEB_CONCURRENCY` must be 1. Application
startup obtains a dedicated PostgreSQL session advisory lease `(19002,110)` for
the Python runtime. A second owner of the same database fails startup. The lease
is released on shutdown. This is a single-owner deployment guard, not horizontally
synchronized Python state. A PostgreSQL connection failure prevents startup.
Hot reload must wait for the old worker's lease to be released.

## SQL and H01 state order

For every validated record, lock the asset in process and in PostgreSQL, compare
its semantic hash, prepare a private H01 candidate, then write telemetry,
analytics, alert/maintenance effects, receipt and checkpoint in one transaction.
SQLAlchemy's outer transaction commit event authorizes installation; rollback
discards candidates. Locks remain held through installation. Direct repository
writes are not a substitute for this common ingestion path.

Each transaction reads the durable checkpoint before preparing, so the database
is authoritative after a crash between SQL commit and memory installation. Failed
installation is logged and retried through checkpoint restore on the next record.
Incompatible/corrupt/configuration-changed checkpoints are not cleared: telemetry
can be retained with null analytics, `CHECKPOINT_RESTORE_FAILED`, and visible
coverage loss. Configuration changes need deliberate compatible-state handling;
H02 never silently resets unresolved trip context.

A batch commits in chunks of 1,000. Intermediate candidate checkpoints hydrate
only the transaction's private speculative branch. Public runtime state changes
after chunk commit; a failed chunk rolls back all its effects, while earlier
committed chunks remain durable. History is loaded once per asset per chunk,
retained for one hour plus a boundary observation, and capped at 4,096. Existing
H01 readiness/gap/coverage rules remain authoritative. Accepted-but-unanalysed
rows after a checkpoint are not implicitly replayed into forward state.

The former bulk-write shortcut is bypassed so every record receives semantic
comparison and the same transaction lifecycle. The existing 10,000-row benchmark
still needs PostgreSQL execution; no performance claim is made here.

## Identities, receipts and API outcomes

HTTP and MQTT decode numbers as Decimal before measurement coercion. Canonical
semantic UTF-8 text and the H01 SHA-256 are persisted alongside float measurement
columns; history hydration reconstructs that text to preserve precise identity.
The hash excludes its own snapshot ID and transport/server fields. Sources may
not submit `received_at`. Legacy rows without hashes undergo deterministic
comparison, including protection contacts. Exact retries return prior analytics
without inference or repeated side effects. Changed identities return HTTP 409;
MQTT counts/rejects them and retains only bounded diagnostic evidence.

`GET /api/v1/ingestion/receipts/{snapshot_id}` returns H00's committed/conflict
shape. A record's snapshot ID must equal its canonical hash. Conflicts use the
attempted hash and preserve the accepted hash; the original receipt is immutable.
The route returns H00 `RECEIPT_NOT_COMMITTED` with HTTP 404 until commit. The
receipt marker's server timestamp is transaction time, not a measured physical
commit instant. Receipt visibility is the SQL-commit evidence. MQTT PUBACK is
never that evidence.

Late observations can be retained for audit with
`REJECTED_LATE_OBSERVATION`, no fresh analytics, no forward effects and no accepted
receipt (H00 has no committed late-outcome receipt variant). Latest uses only the
selected telemetry row's analytics and exposes `analytics_availability`; it never
borrows older healthy analysis. Analytics retain their event timestamp. Missing
ML remains unavailable; the old stateless stub is retained for legacy tests,
but does not supply operational analytics for contract 1.1 inputs. Remote HTTP
inference is unavailable for ingestion until it supplies a compatible candidate
transaction protocol; the existing HTTP client boundary is otherwise unchanged.

`GET /api/v1/ingestion/status` exposes bounded process-local validated-record
attempt counters, not durable totals. MQTT status separately exposes message
received/rejected/dropped counters and record validated/committed/conflicted
counters; `error_count` counts failures. Credentials and raw payloads are absent.

Replay requires `replay_transformer_id`, a registered destination distinct from
every origin. `transformer_id` remains the origin selection filter. Source event
time is preserved, acquisition is REPLAYED with origin asset/run/units retained,
and previously unknown provenance remains UNKNOWN/UNVERIFIED with an explicit
replay timezone assumption. Register a fresh destination for a new run: changing
run lineage under an existing destination/time is a semantic conflict. Live rows,
checkpoints and latches are never backfilled through this endpoint.

## Verification boundary

Run the focused commands in [the H02 execution report](../docs/hackathon_readiness/execution/H02_BACKEND_CONTRACTS_AND_TRANSACTIONAL_STATE.md).
Set `TEST_DATABASE_URL` only to a disposable PostgreSQL instance with CREATEDB
permission: existing fixtures create/drop unique test databases. Set
`MQTT_TEST_HOST`/`MQTT_TEST_PORT` for the real broker test. SQL and broker gates
remain blocked until those tests actually execute; unit mocks and offline DDL
compilation do not replace them. RUL is typed/persistable only; H05 owns calculation.
