# ML integration boundary

Backend ownership is limited to canonical validation, transport and response contracts.
This phase adds no application endpoints, persistence, ML packages or feature engineering.

## Exact backend call signature

```python
class MLTwinClient(Protocol):
    def analyze(
        self,
        transformer: TransformerOut,
        record: TelemetryIn,
        history: list[TelemetryIn],
    ) -> MLResultIn: ...
```

Callers select an adapter through `get_ml_client()` and invoke
`safe_analyze(client, transformer, record, history)` when ingesting telemetry in Phase 4.
The factory is cached; `ML_BACKEND=stub|python|http` selects the implementation.
The Settings Literal rejects other values during application startup configuration.
Switching backend requires configuration changes and a process restart, not caller changes.

## History-window semantics

The ingestion/query layer must supply the last `ML_HISTORY_WINDOW` prior rows for this
transformer, ordered oldest to newest and excluding the current record. Default window: 60.
Only timestamps strictly before the current timestamp are valid; duplicate timestamps,
other transformer identities, reversed windows and oversized windows are rejected.
An empty or shorter history is valid. Adapters preserve the order, values and nulls and
never fetch, sort, truncate or store telemetry history themselves.

The backend keeps no ML feature state. The ML layer computes rolling statistics, rates
and time-since-alarm features from the provided window. Caching the imported callable or
HTTP connection pool does not retain telemetry or analytical state.

## Python adapter

Configure `ML_PYTHON_ENTRYPOINT=module.path:function`. The module and function are loaded
lazily on the first analysis call and the callable is cached on the adapter. The backend
can start with `ML_BACKEND=python` before the ML package is installed; its first invocation
will report an import failure through the safe wrapper if the entrypoint is unavailable.

The current proposed Person-1 function signature is:

```python
def analyze(
    *,
    transformer: dict[str, Any],
    record: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]: ...
```

Arguments use Pydantic Python mode: plain dictionaries with aware UTC datetime values,
not JSON strings. Every nullable field remains present as None. Only this adapter imports
the external callable; no pandas dependency or dataframe conversion is required.
The Person-1 callable signature is a proposal awaiting confirmation below.

## HTTP adapter

Configure `ML_HTTP_URL` to the complete external service URL (for example
`https://twin.example/analyze`). The adapter sends a synchronous POST using httpx.Client:

```json
{
  "transformer": {
    "rated_power_kva": null,
    "rated_voltage_hv": null,
    "rated_voltage_lv": null,
    "rated_current_a": null,
    "cooling_class": null,
    "oil_type": null,
    "id": "TX-001",
    "name": "Demo transformer",
    "created_at": "2026-10-06T09:00:00Z",
    "updated_at": "2026-10-06T09:00:00Z"
  },
  "record": {
    "transformer_id": "TX-001",
    "timestamp": "2026-10-06T09:00:00Z",
    "phase_voltage_l1": null,
    "phase_voltage_l2": null,
    "phase_voltage_l3": null,
    "current_l1": null,
    "current_l2": null,
    "current_l3": null,
    "neutral_current": null,
    "oil_temperature": 42.0,
    "winding_temperature": null,
    "ambient_temperature": null,
    "oil_level": 8.0,
    "oil_temp_alarm": null,
    "oil_temp_trip": null,
    "magnetic_oil_gauge_alarm": null,
    "active_power_total": null,
    "apparent_power_total": null,
    "reactive_power_total": null,
    "energy_kwh": null,
    "power_factor_l1": null,
    "power_factor_l2": null,
    "power_factor_l3": null,
    "source_name": "simulator",
    "scenario_id": "normal-demo"
  },
  "history": [
    {
      "transformer_id": "TX-001",
      "timestamp": "2026-10-06T08:59:00Z",
      "phase_voltage_l1": null,
      "phase_voltage_l2": null,
      "phase_voltage_l3": null,
      "current_l1": null,
      "current_l2": null,
      "current_l3": null,
      "neutral_current": null,
      "oil_temperature": 42.0,
      "winding_temperature": null,
      "ambient_temperature": null,
      "oil_level": 8.0,
      "oil_temp_alarm": null,
      "oil_temp_trip": null,
      "magnetic_oil_gauge_alarm": null,
      "active_power_total": null,
      "apparent_power_total": null,
      "reactive_power_total": null,
      "energy_kwh": null,
      "power_factor_l1": null,
      "power_factor_l2": null,
      "power_factor_l3": null,
      "source_name": "simulator",
      "scenario_id": "normal-demo"
    }
  ]
}
```

The full validated response for this normal demonstration record is:

```json
{
  "transformer_id": "TX-001",
  "timestamp": "2026-10-06T09:00:00Z",
  "inference_status": "OK",
  "missing_features": [],
  "loading_percent": null,
  "thermal_model_temperature": null,
  "thermal_residual": null,
  "thermal_state": null,
  "anomaly_score": 0.1,
  "anomaly_flag": false,
  "health_index": 90.0,
  "health_components": {
    "thermal": 90.0,
    "electrical": 90.0,
    "loading": 90.0,
    "oil": 90.0,
    "alarm": 90.0,
    "anomaly": 90.0
  },
  "health_reason_codes": [],
  "fault_risk": 0.05,
  "predicted_fault": null,
  "prediction_confidence": null,
  "maintenance_priority": "NORMAL",
  "maintenance_recommendation": "Continue routine monitoring.",
  "reason_codes": [],
  "schema_version": "1.0.0",
  "feature_version": "1.0.0",
  "model_version": "stub-0.0.0",
  "error_detail": null
}
```

Both adapter responses pass through the same parser. Unknown top-level result keys are
dropped with a warning listing only key names. Missing required identity/status/version
fields, invalid enum values, non-finite scores and out-of-range scores raise MLClientError.
Nested health components retain strict schema validation. The result transformer identity
and timestamp must match the current record. The safe wrapper also revalidates typed
results, including objects created without validation or subsequently mutated.

`ML_TIMEOUT_SECONDS=5` sets the httpx operation timeout. `ML_MAX_RETRIES=2` means at most
three attempts, including the initial request. Only connection errors and 5xx responses
are retried, immediately. Timeouts (including connect timeouts), 4xx, redirects, malformed
JSON and schema/identity errors are not retried. Requests do not follow redirects.
Timeouts raise MLTimeoutError; other transport or response failures raise MLClientError.
HTTP timeout applies to connect/read/write/pool operations, not a single overall deadline
across all attempts. The service must make analysis requests safe to repeat after 5xx.

httpx is a backend runtime dependency. No remote service is needed for the tests:
httpx.MockTransport covers success, failures and retry behavior. The HTTP adapter's
`close()` releases its owned client; injected clients remain caller-owned. The Phase 4 app lifespan now
closes the cached HTTP adapter on shutdown through close_ml_client(). Clearing the
factory cache alone does not close its previous client.

## Deterministic stub rules

Evaluate these branches in order:

| Condition | Status | Priority | Reasons | Anomaly score / flag | Health index | Proxy risk |
| --- | --- | --- | --- | --- | --- | --- |
| Missing oil_temperature or oil_level | INSUFFICIENT_DATA | null | null | null / null | null | null |
| oil_temp_trip equals 1 | OK | URGENT | OIL_TEMP_TRIP | 0.95 / true | 25 | 0.9 |
| oil_temp_alarm equals 1 | OK | PLAN | OIL_TEMP_ALARM, HIGH_OIL_TEMP | 0.75 / true | 55 | 0.6 |
| magnetic_oil_gauge_alarm equals 1 | OK | PLAN | MOG_ALARM | 0.5 / true | 60 | 0.3 |
| Otherwise | OK | NORMAL | empty list | 0.1 / false | 90 | 0.05 |

Insufficient records list missing canonical names in `missing_features` and leave every
analytic output null. The stub checks only presence and protection flags, never thermal
or oil units, magnitudes, conversions or thresholds. It cannot establish a physical fault.
`predicted_fault=THERMAL_STRESS` appears only for proxy risk >= 0.5; otherwise it is null.
Prediction confidence is 0.8 for those proxy predictions and null otherwise. Thermal model
temperature, thermal residual and thermal state remain null because no physical twin is
implemented by the stub.

For OK records, thermal/alarm health components equal the branch health index; electrical
and loading components are 90; oil is 60 with the magnetic gauge alarm and 90 otherwise;
anomaly is `(1 - anomaly_score) * 100`. These are demonstration component scores, not
physical estimates. Health reason codes mirror reason codes. NORMAL recommends routine
monitoring, PLAN recommends an inspection, and URGENT recommends urgent inspection of
the trip indication using site procedures. The rules currently do not generate WATCH.

Loading percent is null when rated_power_kva or apparent_power_total is null. Otherwise it
is `apparent_power_total / rated_power_kva * 100`. A non-positive configured denominator
raises MLClientError and the safe wrapper returns an insufficient result; no replacement
rating is invented. Arithmetic output is revalidated for finite values.

Versions: schema_version comes from settings, feature_version is 1.0.0, and model_version
is stub-0.0.0. The stub does not mutate its input records or retain history.

## Failure behavior

`safe_analyze` catches analysis, transport, timeout, import and result-validation exceptions
and returns a valid MLResultIn with:

- The original transformer identity and current timestamp.
- `inference_status=INSUFFICIENT_DATA`, `missing_features=[]`, and all analytic outputs null.
- A short error_detail: ML analysis failed or ML analysis timed out; no exception text/traceback.
- schema_version from settings; feature_version and model_version both unavailable.

Logs contain transformer_id, timestamp and exception type; they do not expose upstream
exception text to API clients. If settings cannot be loaded during failure handling, the
wrapper uses the declared schema_version default to preserve failure isolation.
The wrapper expects already validated TransformerOut/TelemetryIn inputs. Phase 4 must
persist accepted telemetry even when this result reports an ML failure.

## Open questions for Person 1

1. Python function vs HTTP service and exact signature: confirm the proposed keyword-only
   dictionary callable or the HTTP URL and request envelope.
2. Do you want the supplied history window or keep state? The backend currently keeps no
   ML state and provides up to ML_HISTORY_WINDOW prior records, excluding the current row.
3. Confirm the final response JSON, including loading_percent, thermal_state, health_components,
   inference_status and missing_features, plus schema/feature/model versions and nullable outputs.
4. Is anomaly_score strictly 0..1? The current shared schema enforces that range.
