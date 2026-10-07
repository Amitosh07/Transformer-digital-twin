# Phase 8 acceptance

Implemented on feature/backend-api, with changes confined to backend/.
No canonical schema change or migration was needed. Production seed scripts, Docker
packaging and handoff work are outside this phase.

## Checks

- **693 passed, no skips**, in **223.85 s**, real PostgreSQL 16 and local Mosquitto.
  One existing Starlette/httpx TestClient deprecation warning remains.
- Independent line coverage: **app/services 98.99% (687/694)**,
  **app/repositories 98.44% (252/256)**. Both exceed 80%; the combined
  coverage report is 98.84%. The independent check_coverage.py gate passes.
- The first coverage run identified analytics conflict recovery as the largest gap
  (analytics_repo 81.48%). Added real conflict/missing-lookup and empty-bulk tests bring
  that repository to 100%. Added bulk lifecycle-conflict reconciliation and external
  duplicate safety tests bring batch_ingestion to 100% as well.
- Remaining uncovered lines are defensive missing-row/runtime guards and unavailable
  ML-client construction fallback branches; every service/repository remains above 95%.
  Readiness, query, replay and maintenance repositories have 100% line coverage.

- The previous 648 tests remain unmodified. All new cases are in tests/hardening/ and
  tests/performance/; the OpenAPI baseline is in tests/snapshots/.
- Two 500-row differential cases compare optimized chunks of 37 and 1000 against
  ordinary ingest_record in timestamp order, including late backfills, duplicates,
  insufficient data, escalation, clear counters, resolution and maintenance dedupe.
- Duplicate chunks bypass inference, history, analytics and lifecycle writes. SQL-count,
  hook rollback/recovery, analytics conflicts and forced generic prepared-plan tests pass.
- Request ID propagation, CORS, metadata-only logging and sanitized unexpected/HTTP 500
  errors pass. Ready/unready DB, migration, Python and HTTP ML cases pass, including
  startup readiness and header-only non-inferential probes. Existing MQTT-before-HTTP
  client shutdown checks remain unchanged and pass.
- OpenAPI backward compatibility, negative contract mutations, name and wording guards
  pass. Snapshot regeneration and the precise source allowlist are in [hardening.md](hardening.md).
- Concurrent HTTP batch, MQTT-style ingest_record and actual replay produce exactly
  120 telemetry rows and 120 analytics rows for 120 unique overlapping timestamps,
  without deadlock, loss, duplicated active alert types or failed replay status.
- The million-telemetry/million-analytics SQL fixture and all four dashboard read
  workloads pass. Setup and cold/median/max timings are in [performance.md](performance.md).
- Ruff check, Ruff format --check, git diff --check and Alembic schema checks pass.

## Performance

Paired standalone profiler, real PostgreSQL 16, stub ML, identical instrumentation;
setup is excluded and coverage is disabled. The earlier Phase 7 full-suite run measured
126.038 s initial and 61.105 s duplicates; the fresh paired baseline below differs with
host load. Raw counts and stage timing are committed alongside the documentation.

| 10000-row workload | Before seconds | Final seconds | Before SQL | Final SQL | Target |
| --- | ---: | ---: | ---: | ---: | --- |
| Initial stub ML load | 76.147 | 9.735 | 60014 | 94 | <20 s: met |
| Identical reload | 38.212 | 1.146 | 30015 | 41 | <3 s: met |
| run_ml=false | 29.299 | 4.068 | 20013 | 43 | <8 s: met |

The measured bottleneck was per-row SQL round trips, repeated conflict lookups and
savepoints. Chunk locks, duplicate filtering, telemetry/analytics bulk inserts and
cached lifecycle evaluation remove that cost while retaining ingest_record as the common
entry point. Remaining initial-load cost is bulk insertion/ORM materialization and ML.
Single HTTP/MQTT-style SQL falls from 8.99 to 8.01 statements per record, but their
wall times increased in the measured runs; no speedup is claimed for those paths.
Coverage-run benchmark times are separately reported in performance.md.

A regression exposed parameterized partial-index inference under PostgreSQL generic
prepared plans. Using the constant status predicate matching the existing index fixes
it without changing the index or lifecycle rules. Read timings do not justify an index
migration or query alteration.

## Files

The complete created/changed file list is the Phase 8 section of [FILES.md](FILES.md).
Commands for profiling, snapshot regeneration and independent package coverage gates
are documented in [performance.md](performance.md) and [hardening.md](hardening.md).
