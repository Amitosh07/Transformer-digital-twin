# Phase 8 performance

## Baseline before optimization

Measured with scripts/profile_ingest.py on the unchanged Phase 7 implementation,
using the real HTTP batch endpoint, stub ML and a disposable PostgreSQL 16 database.
SQLAlchemy before/after cursor hooks count and time every SQL statement. Stage wall times
are inclusive (nested stage totals must not be added); SQL stage attribution uses the
innermost instrumented function. Database migration/setup is outside the measurements.

The earlier Phase 7 full-suite benchmark was 126.038 s initial / 61.105 s duplicate.
Fresh baseline timings differ with host load; the paired profiles below use the same
script, payload, event instrumentation and local container.

| Workload | Rows | Before seconds | SQL statements | SQL / row | SQL seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| initial | 10000 | 76.147 | 60014 | 6.0014 | 37.624 |
| identical_reload | 10000 | 38.212 | 30015 | 3.0015 | 18.546 |
| without_ml | 10000 | 29.299 | 20013 | 2.0013 | 13.233 |
| single_http | 100 | 1.552 | 899 | 8.9900 | 0.607 |
| mqtt_style | 100 | 1.457 | 899 | 8.9900 | 0.637 |

Initial load: 20,002 INSERT, 20,001 SELECT, 10,000 SAVEPOINT, 10,000 RELEASE and
11 UPDATE statements. Telemetry insertion took 20.868 s, analytics insertion 20.310 s,
the hook 17.179 s (including implicit savepoint creation), transformer locks 7.782 s,
and ML only 1.780 s. Validation/quality took 0.173 s. This establishes database round
trips and repeated statement/ORM work as the bottleneck, rather than ML inference.

Duplicate reload: 10,002 INSERT, 20,002 SELECT and 11 UPDATE statements; repeated
conflict inserts/lookups took 28.872 s and transformer locks 7.849 s despite zero ML
work. The batch also loaded 10,000 existing history records unnecessarily.

Single HTTP/MQTT-style ingestion averaged 8.99 SQL statements per new record. Existing
transformer upsert then fetch performed two queries each time. Engine/settings/client
construction is already cached; it is not the measured bottleneck.

Raw baseline stage counts and times are in [profile-before.json](profile-before.json).
No missing index is indicated by this profile; no migration is introduced.

Reproduce (TEST_DATABASE_URL needs CREATEDB; the profiler removes its temporary database):

```powershell
.venv/Scripts/python.exe scripts/profile_ingest.py --output docs/profile-before.json
```

## Optimized ingestion

Measured after differential verification, using the same profiler and disposable DB setup.

| Workload | Before seconds | After seconds | Before SQL | After SQL | Target seconds | Met |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| initial | 76.147 | 9.044 | 60014 | 94 | < 20 | yes |
| identical_reload | 38.212 | 1.265 | 30015 | 41 | < 3 | yes |
| without_ml | 29.299 | 3.747 | 20013 | 43 | < 8 | yes |

The first optimized attempt measured 18.039 / 2.196 / 8.335 s; see
[profile-after-first.json](profile-after-first.json). That profile identified avoidable
multi-row SQL compilation overhead: telemetry insertion spent 6.906 s, with only 1.960 s
in cursor execution. Switching to executemany/insertmanyvalues with render_nulls=True
reduced this cost while preserving missing values. Final stage metrics are in
[profile-after.json](profile-after.json). Remaining initial-load work is actual bulk
insertion/ORM materialization plus ML and lifecycle computation, rather than per-row SQL.

Each chunk locks each transformer once, prefilters all existing keys in one query,
deduplicates repeated input keys, and calls ingest_record for every new record. Its private
chunk context bulk-inserts telemetry when the first record enters that common write path,
collects sequential ML results using the existing history deque, then bulk-inserts analytics.
The ordinary single/MQTT/replay path retains per-record transactions and failure isolation.

Alert/maintenance services run their unchanged rules in timestamp order against a chunk
cache loaded once per transformer. New rows are buffered, existing changes flush once,
and one hook savepoint covers the chunk. If this fails, it rolls back and uses the ordinary
per-record savepoints/conflict path, retaining telemetry/analytics and isolating hook failures.
The partial unique index remains the safety net. No migration/schema change is introduced.

The 500-row differential runs at chunk sizes 37 and 1000 and compares all four tables,
including normalized foreign-key references. It ignores generated IDs and server-created
timestamps (created_at and telemetry ingested_at), and normalizes the two test asset IDs.
It covers healthy/alarm/trip/insufficient records, existing future evidence, descending
arrival order, duplicate timestamps, severity escalation, clearing and maintenance dedupe.

It also exposed a pre-existing generic-prepared-plan issue: parameterized ON CONFLICT
predicates sometimes failed partial-index inference during repeated alert episodes.
Constant status predicates now match the existing index under forced generic plans, with
a dedicated PostgreSQL regression test. Intended lifecycle semantics are unchanged.

The single/MQTT-style paths reduced SQL from 8.99 to 8.01 statements per new record by
looking up an existing transformer before attempting creation. Their wall times varied
with host load (1.552 -> 2.151 s HTTP; 1.457 -> 1.946 s MQTT-style, each 100 rows); no
wall-time speedup is claimed for these paths. Engine/settings/ML-client caches already exist.

```powershell
.venv/Scripts/python.exe scripts/profile_ingest.py --output docs/profile-after.json
```


## Final service measurement

After adding request logging, error correlation and readiness, the same standalone
profiler produced the following measurements without coverage instrumentation. The
readiness probe adjustment only changes /health/ready and does not change ingestion.
The complete stage report is [profile-final.json](profile-final.json).

| Workload | Rows | Before seconds | Final seconds | Before SQL | Final SQL | Target | Met |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Initial with stub ML | 10000 | 76.147 | 9.735 | 60014 | 94 | <20 s | yes |
| Identical reload | 10000 | 38.212 | 1.146 | 30015 | 41 | <3 s | yes |
| run_ml=false | 10000 | 29.299 | 4.068 | 20013 | 43 | <8 s | yes |
| Single HTTP | 100 | 1.552 | 2.963 | 899 | 801 | descriptive | n/a |
| MQTT-style loop | 100 | 1.457 | 2.747 | 899 | 801 | descriptive | n/a |

The final initial load averages 0.0094 SQL statements per row, versus 6.0014 before.
Bulk telemetry and analytics take 2.748 and 2.717 s respectively (4.135 s combined
cursor execution); ML takes 1.739 s and the cached lifecycle hook 0.821 s. Ten parent
lock calls take 0.028 s. The remaining bottleneck is bulk database insertion and ORM
materialization; ML is the next substantial cost. Duplicate reload does no inference,
analytics insertion, lifecycle evaluation or history loading. Single-row paths still
use individual transactions, and these measurements do not show a wall-time improvement.
Host load and middleware/test-client overhead affect these short-loop measurements.

Reproduce the final standalone measurement, with the same environment/database account:

```powershell
.venv/Scripts/python.exe scripts/profile_ingest.py --output docs/profile-final.json
```

## Million-row reads and test profiling

The full coverage run loads one million telemetry rows and one million corresponding
analytics rows using SQL generate_series in the disposable test database, then ANALYZEs
both tables. Tests query the HTTP API through TestClient, with a 24h window, page limit
500, and four trend signals: oil_temperature, current_l1, health_index and fault_risk.
Each workload is sampled five times; cold is the first sample. Setup is outside the
read timings. Coverage instrumentation remains enabled for this read experiment.

| HTTP workload | Cold ms | Median ms | Max ms |
| --- | ---: | ---: | ---: |
| telemetry_24h | 285.858 | 185.750 | 285.858 |
| latest | 20.310 | 13.028 | 20.310 |
| trends_24h_4_signals | 182.327 | 132.811 | 182.327 |
| health_24h | 57.718 | 57.718 | 63.022 |

SQL fixture loading took 28.954 s for telemetry and 30.856 s for analytics.

Every measured read stays below the 500 ms investigation threshold. The existing
transformer/timestamp indexes suffice for these workloads; the previous EXPLAIN/index
regression also passes. No read query or index change, and no migration, is justified
by these measurements. This fixture is test data only and adds no production seed script.

The full-suite --durations=20 report profiles the slow tests under coverage:

| Module / measured case | Seconds under coverage |
| --- | ---: |
| performance/test_million_reads.py: million-row fixture + reads | 62.33 |
| ingestion/test_performance.py: initial + duplicate benchmark | 34.79 |
| performance/test_differential.py: 500 mixed rows, chunk 37 | 26.59 |
| performance/test_differential.py: 500 mixed rows, chunk 1000 | 25.65 |
| read_api/test_trends.py: protection event cap/custom window | 7.96 |
| hardening/test_concurrency.py: three concurrent transports | 7.09 |
| performance/test_differential.py: forced generic plans | 5.01 |

This is the dominant-case profile from the duration report, not the total time of every
case in each module. The MQTT unreachable-broker test also takes 2.06 s intentionally
to exercise the reconnect budget.

These costs come from the required bulk fixture and row-by-row comparison oracle,
plus coverage overhead. Settings, engine and ML-client factories are already cached;
there is no repeated engine construction to remove. Differential coverage is retained
at both chunk sizes to check cross-chunk lifecycle equivalence.

The unchanged 10000-row benchmark under pytest-cov measured 32.584 s initial and
2.126 s duplicate in the final 693-test run (223.85 s total). All tests passed with no
skips. This instrumented initial-load measurement exceeds 20 s; the standalone profiler
measurement is 9.735 s. Coverage overhead is a material difference between these runs.

The standalone profiler table is the ingestion target measurement. Coverage-run times
are reported separately because tracing every service/repository line materially adds
work; the performance claims do not imply those instrumented runs meet the same targets.
