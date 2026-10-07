# Dashboard read API for Person 3

All routes below use /api/v1. The dashboard consumes JSON API responses exclusively.
Fault risk and predicted-fault outputs describe proxy alarm/trip risk, not an established
physical fault. Measurements remain canonical and nullable, with no thermal/oil unit
conversion. OpenAPI at /docs includes typed responses, tags and response examples.

## Endpoint contracts

| Method and path | Response / parameters |
| --- | --- |
| GET /transformers | Page[TransformerOut]; limit, offset; sorted by transformer ID |
| POST /transformers | TransformerOut, HTTP 201; duplicate ID returns 409 |
| GET /transformers/{id} | TransformerOut; unknown asset returns 404 |
| PATCH /transformers/{id} | TransformerOut; only supplied fields change |
| GET /transformers/{id}/latest | LatestStateOut, including data_source and demo_mode |
| GET /transformers/{id}/telemetry | Telemetry page; from, to, limit, offset, order, fields, anchor |
| GET /transformers/{id}/health | Page[HealthPoint]; from, to, limit, offset, order, anchor |
| GET /transformers/{id}/analytics | Page[AnalyticsPoint]; from, to, limit, offset, order, anchor |
| GET /transformers/{id}/alerts | Page[AlertOut]; severity, status, from, to, limit, offset |
| GET /transformers/{id}/maintenance | Page[MaintenanceOut]; status, from, to, limit, offset |
| GET /transformers/{id}/trends | TrendOut; signals, window, anchor; optional explicit from/to |
| GET /scenarios | Page[ScenarioOut]; limit, offset; all-time distinct scenario metadata |

Every unknown transformer returns 404 on every asset route. Invalid input returns 422.
Shared errors use {"error":{"code":"...","message":"...","details":...}}.
Routes delegate to services, which use repositories for database reads and configuration writes.
The read surface introduces no additional telemetry write path or ML inference calls.

## Transformer configuration

Create example:

```json
{"id":"TX-001","name":"Demo transformer","cooling_class":null,"oil_type":null}
```

All nameplate fields are optional and default to null: rated_power_kva, rated_voltage_hv,
rated_voltage_lv, rated_current_a, cooling_class and oil_type. No rating is invented.
PATCH uses exclude_unset: an omitted field stays unchanged; explicit null clears a nullable
nameplate value. name may be updated but cannot be cleared to null. Empty PATCH is valid.
Created/updated timestamps use UTC. ID cannot be patched.

## Shared windows and paging

from/to require ISO-8601 strings with an explicit offset, for example
2020-01-01T05:30:00+05:30. Query strings must percent-encode a literal +; HTTP clients should
use their query-parameter mapping. All response timestamps normalize to UTC. Naive values
return 422. Window bounds are inclusive, start <= timestamp <= end; from must be earlier
than to. A window larger than MAX_WINDOW_DAYS (31 by default) returns a clear limit error.

When to is omitted, it defaults to now(UTC). When from is omitted, it defaults to to minus
DEFAULT_WINDOW_HOURS (24 by default). from alone ends at now; to alone starts the configured
number of hours earlier. DEFAULT_WINDOW_HOURS must fit MAX_WINDOW_DAYS. Trend presets use
their selected duration instead of DEFAULT_WINDOW_HOURS.

Use anchor=latest on telemetry/health/analytics/trends when neither from nor to is supplied.
The window then ends at the asset's latest telemetry timestamp. This is essential for older
replayed/public-dataset demo data: anchor=now would otherwise show an empty current window.
Explicit from or to takes precedence over anchoring. For an empty transformer, latest anchoring
falls back to now and returns an empty page (or null trend buckets). Shared dependencies also
accept anchor on alert/maintenance reads; their default remains now.

```text
GET /api/v1/transformers/TX-001/telemetry?anchor=latest&limit=500
GET /api/v1/transformers/TX-001/health?anchor=latest
GET /api/v1/transformers/TX-001/analytics?anchor=latest&order=desc
```

Pages are {items,total,limit,offset}. total is the filtered count before pagination, limit
defaults to 500 and is capped by MAX_PAGE_LIMIT (5000); offset is non-negative. If configured
below 500, supply an explicit limit within the cap. Series are ascending by timestamp and then
ID; order=desc reverses both for telemetry/health/analytics. Alerts and maintenance ascend by
timestamp then ID. Scenarios sort by scenario_id. No row-returning query is unbounded.
Offset paging is deterministic for a stable dataset; concurrent writes can shift page offsets.
Health and analytics points omit internal database IDs and exception details.

## Telemetry fields projection

Without fields, items contain the full TelemetryOut contract, including schema_version.
With fields=a,b,c, each item contains only the selected fields plus timestamp, which is always
included. TelemetryPoint extends the Out contract to represent this optional projection in
OpenAPI. Serialization omits unselected fields while preserving selected null values.

Allowed fields are the ordered canonical telemetry names plus id, source_name, scenario_id,
is_missing_critical and data_quality_score. schema_version is part of the full response but
is not a selectable field. Unknown, raw or excluded names return 422 listing allowed names.
Names are case-sensitive. Duplicate names are deduplicated. Empty selections are invalid.

```text
GET /api/v1/transformers/TX-001/telemetry?anchor=latest&fields=oil_temperature,current_l1,source_name
```

Example projected item:

```json
{"timestamp":"2020-01-01T00:00:00Z","oil_temperature":null,"current_l1":0,"source_name":"replay"}
```

Missing is null, never zero. A measured zero stays zero.

## Latest state, demo mode and scenarios

latest selects the newest telemetry row by timestamp, then ID, and only that row's analytics.
It does not attach older analytics to a newer row awaiting inference. An existing empty
transformer returns 200 with null telemetry/analytics, null source metadata and feature/model
versions, configured schema_version, zero open alerts and demo_mode=false.
open_alerts_count counts status=OPEN across all time, excluding acknowledged/resolved alerts.
Versions come from that analytics row when present, otherwise telemetry/configuration as available.
error_detail permits only the short Phase 3 messages; unexpected stored text becomes
"ML analysis failed". Health and analytics series do not expose error_detail.

The shared demo rule is true if scenario_id is not null (including an empty string), or
source_name has a case-insensitive prefix in DEMO_SOURCE_NAMES. Defaults:
simulator,replay,demo,seed,mqtt,mqtt-simulator,analytics-backfill.
Thus replay-public-data, SIMULATOR-NORMAL and historical analytics-backfill sources count.
Absent metadata and an ordinary plant source produce false. Configure comma-separated prefixes
before startup. latest exposes data_source={source_name,scenario_id} so the dashboard can label it.

scenarios groups non-null scenario_id values across all transformers and all time, reporting
scenario_id, first_timestamp, last_timestamp and row_count. The paged result is sorted by
scenario_id and does not add database IDs. Health/analytics pages include INSUFFICIENT_DATA
rows with null outputs so charts preserve missing results.

## Trends and protection events

signals is required, comma-separated, with at most 8 entries. It accepts numeric canonical
telemetry measurements, excluding protection flags, plus anomaly_score, health_index,
fault_risk, thermal_residual and loading_percent. Unknown/empty names return 422 with the
allowlist. Duplicate entries count toward the cap and are deduplicated for output.
window accepts 1h, 6h, 24h or 7d and defaults to 24h; anchor defaults to now.

| window | Duration | bucket_seconds | Full-window bucket count, including endpoint |
| --- | --- | ---: | ---: |
| 1h | 1 hour | 15 | 241 |
| 6h | 6 hours | 120 | 181 |
| 24h | 24 hours | 300 | 289 |
| 7d | 7 days | 3600 | 169 |

Aggregation runs in PostgreSQL date_bin, with origin equal to the resolved window start.
Each bucket is [bucket_start,bucket_start+bucket_seconds), clipped to the query window;
the inclusive end may create a final partial bucket. Explicit from/to override the preset
bounds. For a longer explicit window, bucket_seconds grows to at least ceil(duration/300),
so there are at most 301 buckets per signal. No raw rows are loaded for aggregation.

Each signal returns bucket_start, avg, min, max and count. count counts non-null values;
zeros count as observations. Empty/all-null buckets have count=0 and avg/min/max=null.
The service builds these null gaps explicitly. It never zero-fills or interpolates.
no_data_signals names signals with no non-null observations across the window.
Telemetry and analytic signals aggregate their own tables without join multiplication.

```text
GET /api/v1/transformers/TX-001/trends?signals=oil_temperature,health_index,fault_risk&window=1h&anchor=latest
```

TrendOut includes start, end, bucket_seconds, signals (mapping of signal to bucket list),
no_data_signals and protection_events. Protection events contain only timestamp and the three
protection flags, only when at least one flag is 1. They sort by timestamp/ID and cap at 500;
if more exist, the first 500 are returned. Flags are not averaged as numeric trends.
Proxy risk and predicted-fault labels cannot establish a physical failure.

## Alert and maintenance filters

Alert severity accepts INFO, WARNING or CRITICAL; status accepts OPEN, ACKNOWLEDGED or RESOLVED.
Maintenance status accepts OPEN, DONE or DISMISSED. Filters combine with the asset/window and
apply before total and pagination. Omitting them includes every status in the time window.

## CORS, indexing and migration

pydantic-settings now requires >=2.7 for the NoDecode marker used by comma-separated
configuration ([upstream export](https://github.com/pydantic/pydantic-settings/blob/v2.7.0/pydantic_settings/__init__.py)).
CORS_ORIGINS is comma-separated and defaults to http://localhost:8501 and
http://127.0.0.1:8501. Legacy JSON-array configuration also works. Credentials are false.

All time-series predicates constrain transformer_id and timestamp directly, allowing the
composite indexes to serve reads/SQL aggregates. Migration 0002 adds the missing maintenance
index on (transformer_id,timestamp DESC). It is required because that table previously had no
such index; no columns or canonical schema change. Apply it before using maintenance windows:

```powershell
cd C:\Transformer-backend\backend
.venv/Scripts/python.exe -m alembic upgrade head
```

The planner test bulk-seeds 20,000 telemetry rows in a disposable database, ANALYZEs the table,
and EXPLAINs the production repository statement for a selective window. It asserts a composite
index scan without enable_seqscan=off. Migration round-trip/check tests validate the new index.

## Verification

```powershell
cd C:\Transformer-backend\backend
$env:DATABASE_URL="postgresql+psycopg://transformer:transformer@127.0.0.1:55432/transformer"
$env:TEST_DATABASE_URL=$env:DATABASE_URL
$env:MQTT_TEST_HOST="127.0.0.1"
$env:MQTT_TEST_PORT="51883"
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pytest -q -s
```

PostgreSQL fixtures create/migrate/drop disposable databases and require CREATEDB.
MQTT_TEST_HOST includes the prior real-broker regression so acceptance has no skipped tests.

## Phase 7 generated records

Alert and maintenance lists now include rows generated by the ingestion hook. AlertOut
includes last_seen_at and nullable resolved_at; clear_count remains private. Latest state
continues counting OPEN alerts only; acknowledging or resolving updates this count.
ACKNOWLEDGED rows still participate in alert dedupe. The new individual read and lifecycle
endpoints, rules and maintenance semantics are documented in [alerts.md](alerts.md).
