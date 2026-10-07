# Alerts and maintenance (Phase 7)

Read `CONTEXT.md`, `ingestion.md`, `ml-integration-notes.md` and `read-api-notes.md`
for the canonical contracts. Apply `alembic upgrade head` before starting this version.
Migration `0003` adds `alerts.clear_count INTEGER NOT NULL DEFAULT 0`, nullable
`alerts.resolved_at TIMESTAMPTZ`, and a partial unique index on
`(transformer_id, alert_type)` for OPEN/ACKNOWLEDGED alerts. No canonical fields change.

## Rules and severities

The pure `alert_candidates(record, analytics, settings)` function returns candidates
sorted by alert_type. Each includes severity, trigger, evidence, threshold_or_reason
and recommended_action. INFO < WARNING < CRITICAL. Candidates of the same type merge
at the highest severity, retaining both sources of evidence.

| Input predicate | Alert type | Severity |
| --- | --- | --- |
| oil_temp_trip == 1 | OIL_TEMP_TRIP | CRITICAL |
| oil_temp_alarm == 1 | OIL_TEMP_ALARM | WARNING |
| magnetic_oil_gauge_alarm == 1 | MOG_ALARM | WARNING |
| anomaly_flag is true | ANOMALOUS_PATTERN | CRITICAL when anomaly_score >= ALERT_ANOMALY_CRITICAL, otherwise WARNING (including a null score) |
| maintenance_priority == URGENT | MAINTENANCE_URGENT | CRITICAL |
| maintenance_priority == PLAN | MAINTENANCE_PLAN | WARNING |
| maintenance_priority == WATCH | MAINTENANCE_WATCH | INFO |
| health_index < ALERT_HEALTH_CRIT | LOW_HEALTH_INDEX | CRITICAL |
| Otherwise health_index < ALERT_HEALTH_WARN | LOW_HEALTH_INDEX | WARNING |
| fault_risk >= ALERT_FAULT_RISK_CRIT | PROXY_FAULT_RISK | CRITICAL |
| Otherwise fault_risk >= ALERT_FAULT_RISK_WARN | PROXY_FAULT_RISK | WARNING |
| reason_codes contains a configured reason | That reason code | ALERT_REASON_SEVERITY mapping |

Protection predicates run for both OK and INSUFFICIENT_DATA analytics, including ML
failure fallback rows. Every ML-derived rule is skipped unless inference_status is OK.
Protection reason codes OIL_TEMP_ALARM, OIL_TEMP_TRIP and MOG_ALARM are excluded from
reason mapping to prevent duplicate or inferred protection indications. ANOMALOUS_PATTERN
from both the flag and reason mapping produces one merged candidate.

With defaults, health 60 produces no alert, health 40 is WARNING, anomaly 0.9 is
CRITICAL, risk 0.5 is WARNING and risk 0.8 is CRITICAL. Rule thresholds come from settings.
No rule compares oil_temperature, winding_temperature, ambient_temperature or oil_level
with numeric thresholds or performs a unit conversion. None remains None; numeric
measurements are never replaced by zero. Only a protection flag equal to 1 triggers its
rule; 0 and null do not trigger it. The specified untriggered-record counter applies
to protection types for either inference status.

Risk alerts explicitly describe **proxy risk (alarm/trip-based prediction)**. The evidence
stores the actual fault_risk, predicted_fault and prediction_confidence, including nulls.
Other evidence stores the exact triggering flag, anomaly score/flag, health index,
maintenance output or reason_codes. Actions are specific to the alert type and direct
inspection of indications and review of available evidence.

## Configuration

Environment keys (also in `.env.example`):

| Key | Default |
| --- | --- |
| ALERT_HEALTH_WARN | 60 |
| ALERT_HEALTH_CRIT | 40 |
| ALERT_ANOMALY_CRITICAL | 0.9 |
| ALERT_FAULT_RISK_WARN | 0.5 |
| ALERT_FAULT_RISK_CRIT | 0.8 |
| ALERT_AUTO_RESOLVE_AFTER | 5 |
| ALERT_REASON_SEVERITY | Seven reasons mapped to WARNING below |

`ALERT_REASON_SEVERITY` is a JSON object. Supplying it replaces the whole default mapping;
an empty object disables mapped reason alerts while preserving all other rules. Allowed
keys are canonical ML reason codes; values are INFO, WARNING or CRITICAL.
Protection reason codes are accepted in configuration but always skipped by the mapper.

```dotenv
ALERT_REASON_SEVERITY={"HIGH_OIL_TEMP":"WARNING","RAPID_TEMP_RISE":"WARNING","OVERLOAD":"WARNING","CURRENT_IMBALANCE":"WARNING","VOLTAGE_IMBALANCE":"WARNING","LOW_OIL_LEVEL":"WARNING","ANOMALOUS_PATTERN":"WARNING"}
```

PowerShell example overriding the mapping:

```powershell
$env:ALERT_REASON_SEVERITY = '{"OVERLOAD":"CRITICAL","LOW_OIL_LEVEL":"WARNING"}'
```

Health thresholds must be finite and in [0,100], with CRIT <= WARN. Score thresholds
must be finite and in [0,1], with fault-risk CRIT >= WARN. AUTO_RESOLVE_AFTER must be
an integer >= 1. Invalid settings fail validation at startup.

## Lifecycle and transactions

Active means OPEN or ACKNOWLEDGED. The dedupe key is (transformer_id, alert_type) among
active rows. A new occurrence creates OPEN with telemetry/analytics references and both
timestamp and last_seen_at equal to the triggering telemetry timestamp. A recurring
occurrence refreshes evidence, trigger/reason/action, references and last_seen_at,
resets clear_count to zero, and can only escalate severity. timestamp remains the first
occurrence. An acknowledged alert keeps its status and acknowledged_at while evidence
continues to refresh; it is not re-raised as OPEN.

An untriggered active type increments clear_count once for each newly analyzed record
at least as new as last_seen_at. At ALERT_AUTO_RESOLVE_AFTER it becomes RESOLVED and
resolved_at is the clearing record's UTC timestamp. last_seen_at remains the last trigger.
An intervening trigger resets the counter. INSUFFICIENT_DATA does not increment ML
alert counters or change their evidence/status, while protection types still advance.

Older records cannot move last_seen_at backwards, replace newer evidence, reset the
counter, increment it or resolve that active alert. This guard is relative to the last
triggering evidence. After resolution a later trigger can create a new OPEN row.
Duplicates return before the hook and never advance counters. Reanalyzing a previously
stored row with missing analytics uses the same hook once when analytics is created.
`run_ml=false` retains Phase 4 behavior: telemetry only, without analytics or hook execution.

The unchanged `hooks.evaluate_alerts(session, telemetry_row, analytics_row)` signature
orchestrates alert_service then maintenance_service inside ingestion's existing savepoint.
Neither hook service commits. Failure rolls back all alert/maintenance mutations from
that invocation; telemetry and analytics still commit and ingestion returns ALERT_HOOK_FAILED.

Ingestion takes a transformer FOR NO KEY UPDATE lock **before telemetry insertion**.
This serializes lifecycle changes for that asset and remains compatible with foreign-key
KEY SHARE locks. Batches sort by (transformer_id, timestamp), rule types sort consistently,
and endpoints take the same parent lock before locking child rows. Overlapping batches
therefore cannot hold a conflicting telemetry row while waiting for an alert lock.
The partial unique index also protects active dedupe; insert conflicts fetch the existing
active row and the service refreshes it. Maintenance dedupe uses the same parent lock.

## Maintenance persistence

The pure `maintenance_candidate(analytics)` function returns a candidate only for OK
analytics with PLAN or URGENT priority. A matching OPEN record with the same priority and
**set** of reason codes prevents a duplicate; ordering and repeated reason codes do not
matter. Null reasons become an empty set for this comparison and persistence. Recommendation
uses the ML text when present, otherwise an inspection recommendation about proxy indications.

URGENT creates a new record alongside an OPEN PLAN record. Different reasons can create
a separate record at the same priority. NORMAL/WATCH and INSUFFICIENT_DATA create none.
Maintenance records stay OPEN when alerts resolve. Explicit DONE or DISMISSED closes them;
a subsequent matching occurrence can then create another OPEN record.

## Endpoints and examples

| Method and path | Behavior |
| --- | --- |
| GET /api/v1/alerts/{id} | AlertOut |
| PATCH /api/v1/alerts/{id}/acknowledge | OPEN -> ACKNOWLEDGED, acknowledged_at = UTC now; already acknowledged is unchanged 200; RESOLVED is 409 |
| PATCH /api/v1/alerts/{id}/resolve | OPEN/ACKNOWLEDGED -> RESOLVED, resolved_at = UTC now; already resolved is unchanged 200 |
| GET /api/v1/maintenance/{id} | MaintenanceOut |
| PATCH /api/v1/maintenance/{id} | OPEN -> DONE or DISMISSED; any already closed record is 409 |

Unknown positive ids return 404. Invalid body/extra keys return 422. Errors use the shared
`{"error":{"code":"...","message":"...","details":null}}` envelope (validation details
are a list). The existing asset alert/maintenance list endpoints include generated records.
AlertOut exposes last_seen_at, acknowledged_at and resolved_at; clear_count stays internal.
`/api/v1/transformers/{id}/latest` counts only OPEN alerts, so acknowledgement and resolution
reduce open_alerts_count. ACKNOWLEDGED alerts still participate in dedupe and auto-resolution.

Generate a protection alert through the existing ingestion endpoint (ML_BACKEND=stub):

```http
POST /api/v1/telemetry
Content-Type: application/json

{"transformer_id":"TX-001","timestamp":"2026-10-07T09:00:00Z","oil_temperature":42,"oil_level":8,"oil_temp_trip":1,"source_name":"simulator","scenario_id":"alerts-demo"}
```

This also generates ML-derived alerts and an URGENT maintenance record using the stub.
Read alerts with an explicit time window, then acknowledge or resolve the returned id:

```http
GET /api/v1/transformers/TX-001/alerts?from=2026-10-07T09:00:00Z&to=2026-10-07T10:00:00Z
PATCH /api/v1/alerts/1/acknowledge
PATCH /api/v1/alerts/1/resolve
```

No body is required for either alert mutation. A resolved AlertOut example:

```json
{"id":1,"transformer_id":"TX-001","telemetry_id":1,"analytics_id":1,"timestamp":"2026-10-07T09:00:00Z","severity":"CRITICAL","alert_type":"OIL_TEMP_TRIP","trigger":"oil_temp_trip","evidence":{"oil_temp_trip":1},"threshold_or_reason":"OIL_TEMP_TRIP","recommended_action":"Urgently inspect the trip indication using site procedures.","status":"RESOLVED","last_seen_at":"2026-10-07T09:00:00Z","created_at":"2026-10-07T09:00:00Z","acknowledged_at":null,"resolved_at":"2026-10-07T09:05:00Z"}
```

Closing a maintenance record:

```http
PATCH /api/v1/maintenance/1
Content-Type: application/json

{"status":"DONE"}
```

Use `{"status":"DISMISSED"}` to dismiss instead. All responses include the full Out model.
The PostgreSQL tests in `tests/alerts/` cover every rule and boundary, lifecycle, null
handling, concurrency, savepoint rollback, endpoint errors and the full HTTP stub scenario.
