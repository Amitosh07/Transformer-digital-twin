# Phase 4 acceptance results

Verified on 7 October 2026 using Python 3.12, synchronous psycopg/SQLAlchemy and real
PostgreSQL 16.15. Tests use disposable PostgreSQL databases; no SQLite substitute is used.

## Final checks

- ruff check: PASS.
- ruff format --check: PASS (94 Python files formatted).
- Full pytest suite: 435 passed, no skips, 78.51 seconds.
- Existing Starlette/httpx dependency deprecation warning remains; no failures.
- New-file scan: no raw source column names or excluded telemetry columns introduced.
- Telemetry insert call-site check: ingestion_service is the sole application caller.

## Required benchmark

MAX_BATCH_SIZE was configured as 10000 in the benchmark fixture; the default stays 5000.
The test sends 10,000 generated canonical records through the actual HTTP batch endpoint
with stub ML enabled, then sends the same batch again. Commits occur every 1000 valid rows.

| Request | Elapsed seconds | row_count | inserted_count | duplicate_count | parse_error_count | out_of_range_count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial load | 44.977 | 10000 | 10000 | 0 | 0 | 0 |
| Same batch again | 30.158 | 10000 | 0 | 10000 | 0 | 0 |

Both summaries had errors_sample=[]. Test run IDs were 8 and 9 in the disposable database.
The test verified exactly 10,000 telemetry and 10,000 analytics rows for that asset.
These timings describe this local setup, not a production latency guarantee.

## Acceptance coverage

- Single POST persists telemetry/analytics and returns HTTP 201 with all version fields.
- Re-post returns HTTP 200, the original ID and duplicate=true, with no second ML call.
- The 10,000-row load and idempotent reload pass with the summaries above.
- Out-of-order batches produce sorted, unique, strictly earlier ML history, using one
  preload query per asset and including interleaved pre-existing rows.
- Mixed invalid records are counted individually; valid records still persist and the
  error sample is capped at 20 without echoing payloads. NaN protection/power-factor values
  count as parse errors; invalid finite protection/power-factor values count as range errors.
- Missing critical data persists as SQL NULL, flags the row and returns insufficient analytics.
- ML exceptions, timeouts and client-factory errors preserve both telemetry and fallback
  analytics with unavailable feature/model versions and an ML_UNAVAILABLE warning.
- Python and SQL failures in the alert hook are isolated by savepoints.
- Auto-created assets have null nameplate configuration; zero telemetry values stay zero.
- run_ml=false stores telemetry only and avoids batch history queries.
- A failed chunk leaves earlier committed chunks intact and marks the run FAILED with
  the committed insert count. Batch quality and timestamp-gap statistics are persisted.
- Replay uses ingest_record with a separate session, zero-speed replay finishes promptly,
  gaps are scaled/capped, completed/failed status is reported and unknown IDs return 404.
- Stored replay fills analytics only where absent and never replaces existing telemetry
  or analytics. Invalid replay envelopes are rejected.
- Two parallel overlapping batches complete without deadlocks and produce exactly the
  unique timestamps with one analytics row each.
- Shutdown closes the cached HTTP ML client.
- All earlier migration, schema, ML-client, health and other regression tests pass.

Alembic's logging configuration now preserves existing application loggers; a regression
test verifies ML warnings/errors remain available after migrations. No database schema
migration or MQTT transport was added. See ingestion.md for endpoint and replay behavior.
