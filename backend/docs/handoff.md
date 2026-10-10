# Backend handoff

All backend work is on feature/backend-api for merging into develop. Read the consolidated
[API reference](api.md), [demo runner](docker.md), [context](CONTEXT.md) and
[known limitations](known-limitations.md). No canonical fields or new migrations changed
in the final phase; apply existing head 0003. Default demo host URL is http://127.0.0.1:8001.

## For Person 1: ML / Digital Twin

The backend calls this exact protocol, synchronously, once per new analyzed record:

```python
analyze(transformer: TransformerOut, record: TelemetryIn,
        history: list[TelemetryIn]) -> MLResultIn
```

The caller uses get_ml_client() and safe_analyze. history contains at most
ML_HISTORY_WINDOW=60 rows for this asset, oldest first, strictly earlier than the current
record, excluding duplicates/current/future rows. Empty/short history is valid. The ML
layer computes features and twin state from this window; adapters do not fetch data or
keep feature state. Missing values remain None. Nameplate may be entirely null.

Three integration modes, configured in .env and applied after process restart:

| Mode | Environment | Contract |
| --- | --- | --- |
| Stub | ML_BACKEND=stub | Deterministic demo placeholders; no ML package/service |
| Python | ML_BACKEND=python; ML_PYTHON_ENTRYPOINT=your_module:analyze | Keyword-only transformer/record/history dictionaries in Python mode, UTC datetime objects; returns a dictionary or MLResultIn |
| HTTP | ML_BACKEND=http; ML_HTTP_URL=https://your-service/analyze | POST JSON {transformer,record,history}; timestamps ISO-8601 UTC; returns ML response JSON |

ML_TIMEOUT_SECONDS=5 and ML_MAX_RETRIES=2 bound HTTP operations/retries (connection errors
and 5xx only). Timeout is per operation, not an overall inference deadline. Python execution
has no forced timeout. Safe failures become INSUFFICIENT_DATA, null outputs and a short
error_detail, preserving accepted telemetry. HTTP service calls must be safe to retry.
The cached HTTP adapter closes after MQTT shuts down. Readiness imports the Python callable
or probes HTTP HEAD/GET without inference. Compose forces stub until deliberately overridden.

Required result identity/status/version fields: transformer_id,timestamp,inference_status,
schema_version,feature_version,model_version. inference_status is OK or INSUFFICIENT_DATA.
Output names are missing_features,loading_percent,thermal_model_temperature,thermal_residual,
thermal_state,anomaly_score,anomaly_flag,health_index,health_components,health_reason_codes,
fault_risk,predicted_fault,prediction_confidence,maintenance_priority,
maintenance_recommendation,reason_codes. error_detail is optional. Nullable outputs are
allowed; missing data stays null. Scores/confidence/risk use [0,1], health [0,100], all
floats finite. health_components keys are thermal,electrical,loading,oil,alarm,anomaly.
Maintenance priority uses NORMAL,WATCH,PLAN,URGENT. Exact reason-code enums, full JSON,
unknown-key handling and adapter signatures are in [ml-integration-notes.md](ml-integration-notes.md).
Identity/timestamp must match the current record; versions persist with every analytics row.

Open questions remain: confirm Python keyword-only callable vs HTTP URL; confirm whether
the supplied history is sufficient or a stateful ML service is needed; confirm final
nullable result shape/versions and anomaly normalization. Thermal/oil units are still
unverified, and no default transformer rating should be inferred. Fault outputs describe
proxy risk (alarm/trip-based prediction), requiring explicit interpretation in recommendations.

## For Person 3: dashboard

Use the API only; examples/client.py is a typed httpx client using the backend's Pydantic
models, with no database access. Install the backend package to reuse these models, or
use the JSON/OpenAPI contract in your own client. Connect Streamlit to the host URL above
(or http://backend:8000 within Compose). CORS defaults cover localhost:8501 and 127.0.0.1:8501.

| Dashboard section | API calls / presentation |
| --- | --- |
| Overview | GET /api/v1/transformers, then /transformers/{id}/latest; health, versions, open_alerts_count, demo_mode |
| Live monitoring | /latest plus /telemetry?anchor=latest&order=desc; poll the API, preserve null gaps and data_source |
| Digital Twin | /latest.analytics and /analytics?anchor=latest; thermal outputs can be null, loading requires configured nameplate |
| Trends | /trends?signals=oil_temperature,current_l1,health_index,fault_risk&window=24h&anchor=latest; protection events separately |
| Alerts | /alerts?anchor=latest with status/severity; individual GET, PATCH acknowledge/resolve; distinguish first timestamp from last_seen_at |
| Maintenance | /maintenance?anchor=latest; PLAN/URGENT recommendations, individual GET and PATCH DONE/DISMISSED |
| Historical | /telemetry,/health,/analytics with explicit UTC from/to, limit/offset/order; fields projection for telemetry |
| Demo mode | /scenarios plus /latest.demo_mode/data_source; label synthetic/replay data; anchor historical timestamps at latest |

Paths in table after /transformers/{id} are asset-scoped. Use configured MAX_PAGE_LIMIT
(default 5000), default limit 500 and offset pagination. Never treat null as zero or
interpolate missing samples silently. INSUFFICIENT_DATA is distinct from a healthy
result. MISSING_CRITICAL is completeness of seven canonical measurements and is distinct
from ML insufficient-input checks. Stub thermal model outputs stay null and stub scores
are placeholders. Stress alone does not cause stub alerts. Risk text must retain proxy
alarm/trip wording. Resolved alerts remain available with status=RESOLVED; open count is
OPEN only, even though ACKNOWLEDGED participates in lifecycle dedupe. API samples are real
captured responses; X-Request-ID correlates failures without exposing exception details.

## For Person 4: simulator / DevOps

Send canonical telemetry to POST /api/v1/telemetry or /telemetry/batch. For MQTT publish
JSON objects/arrays to transformer/TX-001/telemetry, host broker localhost:51885 (Compose
service mqtt:1883). Enable MQTT for local uvicorn explicitly; Compose already does.
Topic wildcard supplies omitted transformer_id; explicit identity must match. Arrays
validate atomically before writes and commit together; an invalid member rejects all.
source_name identifies the sender, scenario_id labels your simulation; keep both on
simulated rows. Reuse timestamps on retries for (transformer_id,timestamp) idempotency.
Committed duplicates skip inference and hooks. Keep original records for retry/replay
because MQTT receipt acknowledgement occurs before database commit.

Use the real seed examples in docs/samples/api-responses.json for field names, or
scripts/seed_demo.py.generate_records(). A canonical small MQTT payload is:

```json
{"timestamp":"2026-01-01T17:00:00Z","oil_temperature":42,"oil_level":8,"oil_temp_alarm":0,"oil_temp_trip":0,"source_name":"simulator","scenario_id":"SCN_HEALTHY"}
```

This minimal example will mark missing critical electrical fields; use the full generator
for complete data. /api/v1/ingest/mqtt/status reports delivery/error/drop/rejection counts.
Process restart resets counters; database reset does not. Broker sessions persist with a
stable unique client ID. See [mqtt.md](mqtt.md) for queue/shutdown limitations.

Demo procedure: scripts/demo.ps1 up, seed, inspect latest/health/alerts/maintenance, then
reset -Yes and seed. Optional --rows rescales segment lengths; use default 2000 for the
full chain. Seed is idempotent without reset. --no-ml omits analytics and hooks. Reset
removes all measurement/lifecycle/run data, optionally transformers, and refuses production.
The HTTP reset is disabled by default; enable it plus DEMO_ADMIN_TOKEN and send matching
X-Admin-Token only when needed. Pause publishers and finish replays first. Never expose
this unauthenticated demo stack directly to untrusted networks.

Expected default stub chain:

| Segment | Measurements/flags | Analytics and lifecycle |
| --- | --- | --- |
| SCN_HEALTHY, 800 | balanced phases, PF 0.95, flags 0; ten null oil readings | health 90, NORMAL; dropout INSUFFICIENT_DATA |
| SCN_STRESS, 600 | current/power/thermal values rise, flags 0 | stub stays health 90/NORMAL; actual ML behavior may differ |
| SCN_FAULT alarm, 240 | alarm=1 | health 55, proxy risk 0.6, WARNING oil alarm, PLAN maintenance |
| SCN_FAULT trip, 240 | trip=1 | health 25, proxy risk 0.9, CRITICAL trip/escalation, URGENT alongside PLAN |
| SCN_FAULT recovery, 120 | healthy values/flags | health 90; eligible alerts auto-resolve after five rows; maintenance remains OPEN |

The default final latest row is recovered, so review health history and resolved alerts
to see the chain. No physical temperature/oil units or fixed nameplate rating are implied.
Compose merge instructions and exact PowerShell commands are in [docker.md](docker.md).
