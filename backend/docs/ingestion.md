# Phase 4 ingestion and replay

All telemetry writes go through `app/services/ingestion_service.py::ingest_record`.
Live HTTP, batch and replay share this service; a later MQTT integration can call it.
No MQTT transport or database migration was added in this phase.

## Live ingestion

`POST /api/v1/telemetry?run_ml=true` accepts TelemetryIn. Example:

```json
{
  "transformer_id": "TX-001",
  "timestamp": "2026-10-06T09:00:00Z",
  "oil_temperature": 42,
  "oil_level": 8,
  "source_name": "simulator",
  "scenario_id": "normal-demo"
}
```

A new row returns HTTP 201 with telemetry_id, analytics and warnings. Analytics contains
schema/feature/model versions. Set run_ml=false to store telemetry without analytics.
Missing optional measurements remain SQL NULL; zero is a present measurement. An unknown
asset is created with its ID as its name and every nameplate value null.

Repeating an asset/timestamp pair returns HTTP 200:

```json
{"duplicate":true,"telemetry_id":123}
```

The ID is the original ID. Ordinary duplicates run no ML and create no additional analytics.
source_name defaults to api; scenario_id is retained as metadata. Warnings can include
MISSING_CRITICAL, INSUFFICIENT_DATA, ML_UNAVAILABLE and ALERT_HOOK_FAILED. For insufficient
results, analytics.missing_features identifies the missing ML inputs. Fault predictions
retain the proxy-label interpretation in the project context.

Telemetry and analytics commit together. ML exceptions, timeouts, invalid results and
client-construction failures produce the Phase 3 insufficient fallback without losing
telemetry. The alert hook runs in a savepoint, so Python errors and failed SQL statements
inside it cannot abort the saved telemetry/analytics transaction.

## Batch ingestion

`POST /api/v1/telemetry/batch?run_ml=true&source_name=api` accepts an object with records,
a list of telemetry dictionaries. MAX_BATCH_SIZE defaults to 5000. Oversized envelopes
return HTTP 422 using the shared error format. Configure MAX_BATCH_SIZE=10000 before
starting the process to ingest 10,000 rows in one request; the benchmark uses this setting.

Each record is validated independently. Valid rows are ingested even when others fail.
The summary contains run_id, row_count, inserted_count, duplicate_count, parse_error_count,
out_of_range_count and errors_sample. At most 20 rejected rows are sampled, each with
its original zero-based row_index, field and message. Whole payloads are never echoed.

Protection and power-factor validation failures count as out_of_range_count. Other failures
count as parse_error_count, including extra/excluded fields, naive timestamps and non-finite
numbers. Non-finite values count as parse errors even on protection/power-factor fields.
A row with mixed failures is counted once as a parse error. The first validation detail
is used for its sample entry. Error counters count rejected rows, not fields.

The source_name query value labels the run and defaults missing per-record source_name;
explicit per-record source metadata is preserved. Records are grouped by asset and sorted
by `(transformer_id, timestamp)` for consistent insertion/lock ordering. Chunks commit
1000 valid rows with telemetry, analytics and run progress. A later database failure leaves
committed chunks intact, rolls back the current chunk, records FAILED and reports only
committed rows in inserted_count. The HTTP error uses the shared envelope.

With ML enabled, one history query per asset fetches the initial ML_HISTORY_WINDOW prior
rows plus existing rows within the incoming time span. A deque keeps the current window.
As timestamps advance, interleaved stored rows enter once; inserted rows enter after
successful insertion. Duplicate inputs never enter. Current/future rows never enter ML
history. This prevents per-row history queries and supports backfills interleaved with
stored telemetry. History uses the preload snapshot plus this batch's new rows and is not
refreshed for another writer's later commits. With run_ml=false, batch ingestion performs
no history queries and creates no analytics.

## Replay

`POST /api/v1/simulate/replay` returns HTTP 202 with run_id. Exactly one of records or
from_stored is required. A FastAPI BackgroundTask owns a separate database session.

```json
{
  "transformer_id": "TX-REPLAY",
  "source_name": "replay-demo",
  "records": [
    {"timestamp":"2026-10-06T09:00:00Z","oil_temperature":42,"oil_level":8},
    {"timestamp":"2026-10-06T09:00:01Z","oil_temperature":43,"oil_level":8}
  ],
  "speed_multiplier": 0,
  "run_ml": true
}
```

For provided records, optional transformer_id retargets all records to that asset.
Without it, each record needs its own ID. The request source_name is written on every
new replay row; scenario_id is preserved. Invalid rows count as in batch ingestion.
Valid records are sorted chronologically before replay. Zero speed introduces no delay;
positive speed sleeps for the timestamp gap divided by speed_multiplier, capped at five
seconds per gap. Replay commits each successful record and updates progress after each row.

Stored replay example:

```json
{
  "transformer_id": "TX-001",
  "source_name": "analytics-backfill",
  "from_stored": {
    "start":"2026-10-06T00:00:00Z",
    "end":"2026-10-06T23:59:59Z"
  },
  "speed_multiplier": 0,
  "run_ml": true
}
```

The window is inclusive. An omitted transformer_id selects all assets in the window.
Stored rows pass through ingest_record in analytics-backfill mode. Telemetry is never
rewritten; existing source/scenario metadata stays unchanged. Only rows without analytics
receive inference and a new analytics row. Existing analytics stays unchanged. Visited
stored rows count as duplicates, so inserted_count is zero and duplicate_count counts
visits. With run_ml=false, stored replay does not modify existing rows.

`GET /api/v1/simulate/replay/{run_id}` reads ingestion_runs and returns run_id,
RUNNING/COMPLETED/FAILED, progress/error counts, quality statistics, source/version and
start/finish timestamps. It also accepts batch run IDs. Unknown runs return HTTP 404 in
the shared error format. Empty replays complete with zero counts.

BackgroundTasks runs in the backend process, not a durable worker queue. A process restart
can leave a RUNNING row; automatic recovery is outside this phase.

## Quality statistics and lifecycle

Every batch/replay stores row/error/duplicate/insert counts, missing_count_by_field,
timestamp_gap_stats, source_name, schema_version and status/finished_at. Missing counts
cover parsed records including duplicates; required identity fields have zero missing
values. Rejected rows are excluded. Gaps use sorted unique timestamps separately per
asset and are pooled into min_s, median_s, max_s and count. With no gaps, values are null
and count is zero. No measurements are imputed or converted.

The app lifespan closes the created cached HTTP ML client without constructing one just
to close it. `/health` behavior is unchanged.

## Verification

```powershell
cd C:\Transformer-backend\backend
$env:DATABASE_URL="postgresql+psycopg://transformer:transformer@127.0.0.1:55432/transformer"
$env:TEST_DATABASE_URL=$env:DATABASE_URL
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pytest -q -s
```

TEST_DATABASE_URL must point to real PostgreSQL with a CREATEDB account. The benchmark
prints elapsed times and both summaries. Tests cover live/duplicate ingestion, quality,
null preservation, query counts, chunk failure handling, ML/hook isolation, replay,
concurrent overlap, shutdown and all prior phases.
