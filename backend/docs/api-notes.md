Default Compose base URL: `http://127.0.0.1:8001`; local uvicorn can use another port.
Interactive documentation: `/docs`; JSON contract: `/openapi.json`; alternative UI: `/redoc`.
The endpoint table below is generated from the running service's OpenAPI, including
path/query/header parameters and defaults. Runtime-configured caps below still apply.

## Canonical data and interpretation

All timestamps require an explicit timezone and normalize to UTC ISO-8601. TIMESTAMPTZ
is used in PostgreSQL. Null means missing and stays null; measured zero stays zero.
Only the exact canonical names in [CONTEXT.md](CONTEXT.md), plus source_name and scenario_id
metadata, are accepted. The three line-to-line voltage fields identified as excluded
in CONTEXT.md, raw source names and unknown keys are rejected. Canonical protection
flags accept 0/1/true/false/null; floats must be finite; phase power factors use [-1,1].
Thermal and oil units are unverified; the backend performs no unit conversion or numeric
range checks on those measurements. No transformer rating is supplied by default.

Risk and predicted-fault labels mean **proxy risk (alarm/trip-based prediction)**.
The stub's numbers are placeholders. Stress without protection flags remains healthy
in the stub; it does not estimate a physical thermal twin. Missing oil_temperature or
oil_level produces INSUFFICIENT_DATA and null analytics. MISSING_CRITICAL means at least
one of oil_temperature, three currents or three phase voltages is null; it is a data
completeness warning, not a protection indication. Single ingestion returns this warning;
batches report completeness in run statistics rather than per-row warnings.

`latest` attaches only the newest telemetry row's own analytics, and exposes data_source,
demo_mode and schema/feature/model versions. For an empty known asset, telemetry and
analytics are null. Demo mode is true for non-null scenario_id or configured case-insensitive
source prefixes (defaults simulator,replay,demo,seed,mqtt,mqtt-simulator,analytics-backfill).
Use it to label the dashboard. These source labels do not change ingestion or ML rules.

## Windows, paging, trends and limits

For telemetry/health/analytics/trends and alert/maintenance lists, use `anchor=latest`
for historical demo data. Default anchor is now. Without explicit from/to, latest
anchoring ends at the asset's newest telemetry timestamp. Explicit bounds take precedence.
Without bounds, the default window is 24 hours (DEFAULT_WINDOW_HOURS); from alone ends
at now, to alone starts 24 hours earlier. Bounds are inclusive, from < to, maximum
MAX_WINDOW_DAYS=31. Literal + in query timestamps must be encoded; use client params.

Pages contain items,total,limit,offset; default limit=500, MAX_PAGE_LIMIT=5000, offset>=0.
Time series use order=asc by default, with deterministic timestamp/ID ties; desc is allowed.
Alerts and maintenance lists ascend by timestamp/ID. Their optional severity/status filters
apply before counts/paging. Scenarios are all-time, sorted by scenario_id. Page totals
are filtered counts before pagination. Concurrent writes can shift offset pages.

Telemetry fields projection accepts canonical identity/measurements plus id, source_name,
scenario_id,is_missing_critical,data_quality_score. Timestamp is always retained; selected
nulls are preserved. schema_version appears in full records but is not selectable.
Unknown, excluded, raw or empty selections are 422. Health/analytics series omit internal
IDs and error_detail and retain null insufficient results.

Trends require comma-separated signals (maximum 8), canonical numeric measurements
excluding protection flags, or anomaly_score,health_index,fault_risk,thermal_residual,
loading_percent. window defaults 24h; presets 1h/6h/24h/7d use 15/120/300/3600-second
buckets. Explicit windows adapt bucket width to at most 301 buckets. Each bucket has
bucket_start,avg,min,max,count. Count is non-null observations; gaps stay null, never
zero-filled. no_data_signals identifies entirely missing signals. protection_events
are separate flagged records, ascending, capped at 500; flags are never averaged.

MAX_BATCH_SIZE defaults 5000. Batch records validate individually, valid rows still
persist, and at most 20 rejected samples identify row_index/field/message without full
payloads. Protection/power-factor failures count as out_of_range_count; non-finite values
and other schema errors count as parse_error_count. Chunks commit 1000 valid records;
a later failure retains committed chunks and marks the run FAILED.

## Writes, lifecycle and replay

POST telemetry returns 201 for new rows, with telemetry_id, analytics and warnings;
an existing (transformer_id,timestamp) returns 200 with duplicate=true and the original
ID, without repeating ML/hooks. run_ml=false stores telemetry only. Batch source_name
query defaults api and fills missing per-record metadata. Single source defaults api.
ML failures still persist telemetry and insufficient analytics, with ML_UNAVAILABLE and
short error_detail. Hook failures preserve telemetry/analytics and report ALERT_HOOK_FAILED.

Transformer POST requires id/name; duplicate IDs are 409. Nameplate fields are nullable
and optional. PATCH distinguishes omitted fields from explicit nulls; name cannot be null.

Alert timestamp is the first occurrence, last_seen_at the last triggering evidence.
Repeated evidence only escalates severity and resets clear_count. OPEN/ACKNOWLEDGED
participate in dedupe. Five eligible clear records resolve by default; late evidence
cannot rewind active alerts. Protection still evaluates insufficient rows; ML rules do
not. Acknowledge OPEN -> ACKNOWLEDGED; repeated acknowledgement is 200, RESOLVED -> 409.
Resolve is idempotent. Latest open_alerts_count counts OPEN only. PLAN/URGENT maintenance
persists once per open priority/reason set; URGENT can coexist with PLAN. Maintenance
remains open after alerts resolve; DONE/DISMISSED requires OPEN, otherwise 409.

Replay POST requires exactly one of records/from_stored, returns 202 run_id and runs in
BackgroundTasks. speed_multiplier=0 avoids delays; positive values scale gaps capped at
five seconds each. Records sort chronologically and commit individually. from_stored
fills only missing analytics, retaining telemetry and existing results. GET replay status
also accepts batch run IDs. See [ingestion.md](ingestion.md) for run quality/gap fields.

## MQTT and reset

Compose broker: localhost:51885, topic `transformer/TX-001/telemetry`, QoS 1. The consumer
subscribes transformer/+/telemetry. Publish canonical JSON object or array; a missing
transformer_id comes from the topic wildcard, and a present ID must match it. Explicit
source_name/scenario_id stay unchanged; missing source defaults mqtt. Invalid array
members reject the whole message before writes. Retries must retain the same timestamp.
The status endpoint reports connection, queue depth, counters and recent sanitized
rejections. Acknowledgement precedes database commit; retain source records for replay.
Counters reset on process restart, and demo database reset does not reset them.

POST /api/v1/admin/demo/reset is 404 unless DEMO_RESET_ENABLED=true. When enabled it
requires X-Admin-Token matching non-empty DEMO_ADMIN_TOKEN; missing/bad/unconfigured token
is 403. ENV=production always refuses reset (403). Optional include_transformers=true
deletes assets too; default false. It deletes all telemetry/analytics/alerts/maintenance/
runs across all assets in one transaction. Stop publishers and finish replays before reset.
This token protects only this destructive demo operation; other endpoints have no auth.
CLI reset requires --yes and also refuses production. See [docker.md](docker.md).

## Errors and readiness

Errors use {error:{code,message,details}}. Validation is 422 with code VALIDATION_ERROR
and a list of location/message/type objects, followed by request_id. Expected HTTP errors
use HTTP_ERROR (404 missing asset/run/id, 409 lifecycle/config conflict). Unexpected errors
are 500 INTERNAL_ERROR with a generic message and no exception/traceback text. All responses
carry X-Request-ID; a safe supplied ID is accepted, otherwise generated. Request logs
contain metadata only. Detail objects contain request_id; null/string details are safely
wrapped. CORS exposes X-Request-ID and allows configured Streamlit origins.

/health returns 200 even when its database check is degraded. /health/ready returns 200
only after startup with working DB, matching Alembic heads and ML ready/explicitly unchecked;
failures are 503 with sanitized details. Stub is ready, Python checks entrypoint importability,
HTTP probes bounded HEAD/GET without inference/body download. MQTT connectivity is reported
separately and is not a readiness requirement. See [hardening.md](hardening.md).

Regenerate the complete reference and captured samples after resetting with
-IncludeTransformers and reseeding:

```powershell
./scripts/demo.ps1 reset -Yes -IncludeTransformers
./scripts/demo.ps1 seed
.venv/Scripts/python.exe scripts/capture_samples.py --base-url http://127.0.0.1:8001
```

This intentionally creates TX-CAPTURE for write/lifecycle examples. Reset including transformers, then reseed before
running it again; it refuses to reuse that asset. The default 2000-row demo is required
for the fixed segment samples.
