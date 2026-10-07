# Phase 7 acceptance results

Verified on 2026-10-07 in `C:/Transformer-backend/backend`, branch `feature/backend-api`.
All changes remain inside `backend/`. See [alerts.md](alerts.md) for the contract and
[FILES.md](FILES.md#phase-7-files) for all 14 created and 17 changed files.

## Checks

| Check | Result |
| --- | --- |
| `python -m ruff check .` | Passed |
| `python -m ruff format --check .` | Passed; 155 Python files formatted |
| Phase 7 PostgreSQL tests | 91 passed, no skips |
| Full `python -m pytest -q -s --tb=short` | 648 passed, no skips, 216.11 seconds |
| Migration 0003 -> 0002 -> head | Passed on disposable PostgreSQL database |
| Full migration head -> base -> head | Passed on disposable PostgreSQL database |
| `alembic check` | Passed; no new upgrade operations |
| Local development `alembic upgrade head`, `alembic current` | Applied; 0003 (head) |
| Canonical field/ORM consistency | Existing tests passed; telemetry schema unchanged |
| Canonical-name and proxy-wording scan | Changed/new files and generated OpenAPI passed |
| Git change scope and whitespace | backend/ only; `git diff --check` passed |

The only pytest warning is the existing Starlette/httpx TestClient deprecation.
Dependencies and test infrastructure are unchanged. The full suite includes all 557
previous tests and 91 new Phase 7 tests.

## Environment and commands

Python 3.12; synchronous SQLAlchemy 2/psycopg 3; PostgreSQL 16 in the existing local Docker
container `transformer-backend-phase1-pg`, loopback port 55432. The session fixture creates
and drops a uniquely named disposable database. The local Mosquitto broker is the existing
`transformer-backend-phase5-mqtt` container on loopback port 51883; broker integration tests
run without skips. No downgrade is performed on the local development database.

```powershell
cd C:\Transformer-backend\backend
$env:DATABASE_URL = "postgresql+psycopg://transformer:transformer@127.0.0.1:55432/transformer"
$env:TEST_DATABASE_URL = $env:DATABASE_URL
$env:MQTT_TEST_HOST = "127.0.0.1"
$env:MQTT_TEST_PORT = "51883"
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pytest -q -s --tb=short
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic check
```

The full run log is retained locally in `.pytest_cache/phase7-validation.log` (ignored).
Migration 0003 adds clear_count and resolved_at plus the active-alert partial unique index.
Before applying it to the local development database, a read-only query verified zero
existing duplicate active (transformer_id, alert_type) groups.

## Acceptance coverage

- Every protection, anomaly, maintenance-priority, health, proxy-risk and mapped-reason rule;
  exact health 60/40, anomaly 0.9 and risk 0.5/0.8 boundaries. Configurable thresholds and JSON
  reason-severity overrides are exercised, as are invalid setting values.
- Unverified thermal/oil measurements never trigger numeric threshold rules. Evidence
  preserves null scores, predictions, recommendations and reasons. Overlapping anomaly
  sources merge once at the highest severity; protection reason mapping is skipped.
- Protection still generates for INSUFFICIENT_DATA and ML exception fallback. All ML-derived
  rules are skipped for insufficient inference; its records do not clear active ML alerts.
- Twenty consecutive trips dedupe to one active OIL_TEMP_TRIP with refreshed last_seen_at
  and telemetry/analytics references. Severity escalates without downgrading; ACKNOWLEDGED
  remains active for dedupe. Duplicate telemetry never invokes the hook again.
- Resolution happens after exactly five qualifying clear records; an intervening trigger
  resets the counter. A custom resolve count is tested. Older records cannot clear alerts,
  rewind timestamps or replace newer evidence. A post-resolution trigger can create a new row.
- Maintenance dedupe compares priority plus reason-code sets, including reordered/repeated
  reasons. PLAN creates once; URGENT escalation creates another while PLAN remains OPEN.
  Different reasons create another record. NORMAL/WATCH/insufficient create none. Closed
  records allow later matching occurrences.
- Alert acknowledgement/resolution is idempotent as specified; acknowledging RESOLVED is
  409. Maintenance DONE/DISMISSED accepts OPEN only, then returns 409. All individual reads,
  unknown-id 404s, payload 422s and shared error envelopes are tested.
- Existing asset lists expose generated alerts/maintenance; latest state counts only OPEN.
  Out models expose last_seen_at/resolved_at and omit clear_count.
- Two parallel identical trip batches, and partially overlapping trip batches, complete
  without deadlock or duplicate active alerts/maintenance. The repository's partial-index
  conflict lookup returns the existing row. Existing ingestion overlap tests also pass.
- Python and SQL alert-repository failures after a partial hook mutation roll back the
  entire savepoint, preserve telemetry/analytics and return ALERT_HOOK_FAILED. A caller
  rollback proves the hook never commits independently.
- The real HTTP API with configured stub ML runs healthy -> alarm -> trip -> healthy.
  Health is 90 -> 55 -> 25, proxy risk 0.05 -> 0.6 -> 0.9, maintenance PLAN then URGENT,
  actions/recommendations are populated, severities escalate and all alerts resolve after
  sufficient healthy records. Maintenance remains OPEN until explicitly closed.

## Existing benchmark and query-plan regressions

The unchanged 10,000-row HTTP ingestion test passed with stub ML:

| Run | Inserted | Duplicates | Parse/range errors | Elapsed seconds |
| --- | --- | --- | --- | --- |
| Initial ingest | 10000 | 0 | 0 / 0 | 126.038 |
| Identical reload | 0 | 10000 | 0 / 0 | 61.105 |

Exactly 10000 telemetry and analytics rows persist for that fixture. This local run
includes per-transformer lifecycle serialization and hook evaluation; timings depend on
host/container load. No performance threshold is claimed.

The existing 20,000-row EXPLAIN fixture still naturally selects a Bitmap Index Scan on
`ix_telemetry_transformer_timestamp_desc` for its narrow time-window query. No planner
settings are forced. Read pagination, trends, demo metadata, ML, MQTT, schema validation,
error handling and all earlier migration checks pass unchanged in the full suite.
