# Hackathon shared contract — 1.1.0 (H00)

Frozen software interfaces for owner review, 9 October 2026, inspected `develop`
`29dcfaf5e12ef50446d1106c4994a721dc802476`. This additive addendum preserves
[dataschema.md](../../dataschema.md) and [mlcontract.md](../../mlcontract.md).
It specifies future H01–H06 behavior; it does not claim those implementations
or routes exist. No model, feature, preprocessing or artifact version changes
merely because the wire contract becomes 1.1.0.

Inputs remain the flat canonical POST body. Absent `schema_version` means legacy
1.0.0; explicit 1.0.0 and 1.1.0 are accepted. Existing `source_name` and
`scenario_id` remain optional. Acquisition/configuration/metadata/RUL extensions
are optional on existing resources. New resources have explicit required fields.
Legacy fields and nulls retain their meanings; missing is never zero. New
schemas reject unknown fields rather than leaking raw CSV names. Old receivers
require H02's additive schema support before receiving new fields: compatibility
means the new interface accepts valid old inputs, not that old strict receivers
accept unknown fields.

Normative machine-readable types and valid/invalid examples are in
[the fixture directory](../../tests/fixtures/hackathon/README.md). Draft 2020-12
schemas specify types; the validator also enforces arithmetic, cross-field,
time, provenance and serialization invariants not expressible in JSON Schema.
These are interface/arithmetic oracles, not trained-model oracles.

## Ownership and boundaries

| Producer / owner | Consumer / responsibility |
|---|---|
| Person 4: canonical acquisition, immutable source snapshots, register decoding, replay | Person 2 validates identity/topic, provenance and hash; source spools until a committed receipt |
| Person 2: registry, server `received_at`, transactions, receipts, persisted latest/history and bounded energy resource | Person 1 consumes documented config/history without SQL access; Person 3 displays persisted results |
| Person 1: ML results, component metadata, RUL/energy calculation semantics, checkpoint format | Person 2 persists without dropping metadata; Person 3 preserves units/nulls/reasons |
| Person 3: React API types and display | Nullable numbers and integer protection contacts; no substitute UI inference or HI-to-risk/RUL conversion |

Person 1 leads contract review; Persons 2/3/4 review API/persistence, display,
and source/register shapes respectively. Each asset has independent state,
history, energy segments, degradation and latches. Current frontend camelCase
and `voltageHvKv` aliases are internal historical shapes, not the API contract.

## Canonical telemetry and acquisition

`transformer_id`: nonempty string, maximum 128 characters. `timestamp`: aware
ISO-8601 source event time, normalized UTC. Numeric measurements are finite JSON
numbers or null; absent measurements normalize to null. No strings or booleans
as numerical measurements. Protection input accepts boolean or integer 0/1;
`TelemetryIn.binary_protection` semantics normalize to integer 0/1, null stays
null. JSON `1.0`/strings are invalid protection inputs even though JSON Schema's
mathematical integer type alone cannot distinguish `1.0`. Analytics
`anomaly_flag` remains strict boolean/null, never integer.

| Canonical fields | Unit / interpretation |
|---|---|
| `phase_voltage_l1/l2/l3` | V when verified; preserve source reference and side, no inferred line/phase conversion |
| `current_l1/l2/l3`, `neutral_current` | A when verified; line currents, no extra division by sqrt(3) |
| `oil_temperature`, `ambient_temperature` | `DEG_C` only with verification or explicit synthetic convention; otherwise `SOURCE_UNIT`/unknown |
| `winding_temperature` | Source numeric indicator/status remains numeric/null; `STATUS` is not hot-spot °C |
| `oil_level` | Source unit; percent only if declared/verified |
| `oil_temp_alarm`, `oil_temp_trip`, `magnetic_oil_gauge_alarm` | Integer 0/1/null output contact states; null does not mean clear |
| `active_power_total`, `apparent_power_total`, `reactive_power_total` | kW, kVA, kVAr only with source evidence or synthetic convention; signed values retained |
| `energy_kwh` | kWh counter only with explicit cumulative/sign/reset semantics |
| `power_factor_l1/l2/l3` | Dimensionless number in [-1,1] or null |

No `VL12`, `VL23`, `VL31`, `DeviceTimeStamp`, or other raw source columns in
canonical downstream bodies. The optional `acquisition` object is nullable.
When populated it has all the following keys (unknown values are explicitly
null, unknown unit/verification entries use the sentinels below):

| Key | Type / allowed values |
|---|---|
| `source_kind` | `SIMULATED`, `REPLAYED`, `LIVE` |
| `source_name` | Nonempty string; must agree with flat `source_name` if both provided |
| `origin_kind` | `SIMULATED`, `LIVE`, `UNKNOWN`; replay lineage, not a transport |
| `origin_transformer_id`, `replay_run_id` | Nullable nonempty strings; both required non-null for replay; destination ID must differ from origin |
| `gateway_id` | Nullable nonempty string |
| `timestamp_origin` | `SOURCE_SNAPSHOT`, `SOURCE_EVENT`, `GATEWAY_POLL`, `REPLAY_ASSUMPTION` |
| `timezone_status` | `VERIFIED`, `DECLARED_UTC`, `ASSUMED`, `UNKNOWN` |
| `field_units` | Map over all 21 canonical measurement names; unit string or `UNKNOWN` |
| `field_verification` | Same 21 keys; `VERIFIED`, `UNVERIFIED`, `SYNTHETIC` |
| `measurement_side` | `HV`, `LV`, `UNKNOWN` |
| `map_version` | Nullable nonempty version string |
| `snapshot_id` | Nullable lowercase SHA-256 hex; producer may omit its value as null before calculating |
| `sequence` | Nullable nonnegative integer; source/run scoped, not global ordering |
| `expected_interval_seconds` | Nullable positive number |

`received_at` is a server-only aware UTC field added to stored/read telemetry,
never accepted in the source body or acquisition. HTTP retries/MQTT packet IDs,
PUBACK, retained flag, retry count and publication time are transport context,
not measurement fields. Preserve original event time on retry and replay.

Absent acquisition on legacy input yields unknown provenance, side, units and
verification, even if the flat source name says simulator or MQTT. Do not
materialize a false `LIVE` acquisition. A `LIVE` label alone establishes neither
authorization nor unit validity. `UNKNOWN` timezone data requires adapter staging
until evidence or an explicit documented replay assumption supplies an aware
timestamp. `ASSUMED` requires `REPLAY_ASSUMPTION` and replay mode; `DECLARED_UTC`
is restricted to simulated data or simulated replay origin. Field verification
`SYNTHETIC` is restricted to simulated source/origin. A synthetic convention is
not a real sensor certificate. WTI source status cannot inherit synthetic °C.

## Asset/nameplate configuration

Existing API `id`, `name`, optional ratings/cooling/liquid and read
`created_at`/`updated_at` retain their shapes. New nullable fields:

| Field | Type and units |
|---|---|
| `rated_frequency_hz` | Positive number, Hz |
| `vector_group` | String; no default |
| `impedance_percent` | Positive number, percent on documented base |
| `temperature_rise_limits` | Object with nullable `top_oil_k`, `winding_k`, `hot_spot_k`, `reference`; positive K rises and asset-specific applicability reference |
| `measurement_side` | `HV`, `LV`, `UNKNOWN` or null |
| `ct_ratio`, `pt_ratio` | Nullable object `{primary, secondary, unit}`; positive values, A for CT and V for PT, not an unexplained multiplier |
| `insulation_type` | Nullable string |
| `loss_parameters` | Nullable object `{no_load_kw, rated_load_kw, reference_temperature_deg_c, reference}`; nonnegative losses, nullable inputs/reference |
| `configuration_metadata` | Nullable `{version, status, field_metadata}` |

`field_metadata` maps field paths (including nested leaf paths) to
`{unit, verification, provenance, evidence_reference, effective_at}`. Unit is
nullable, verification is `SYNTHETIC_CONFIG`/`VERIFIED`/`UNVERIFIED`, provenance
is nonempty text, evidence/effective aware timestamp nullable. `status` has the
same enum. Missing per-field evidence means UNVERIFIED irrespective of aggregate
status. Synthetic provenance never qualifies for operational analysis. A
VERIFIED leaf needs a non-null evidence reference; a configured non-null leaf
under metadata needs its own entry. Mixed configurations cannot claim aggregate
VERIFIED or SYNTHETIC_CONFIG unless all populated leaves agree.

Existing ratings remain nullable. Newly configured positive ratings use kVA,
V (HV/LV), A (rated **line** current on the declared side). In legacy 1.0.0,
ambiguous voltage numbers remain byte-for-byte values with UNVERIFIED/unknown
unit; no automatic multiplication. Explicit conversion from a known kV source
must be documented in field provenance. Unknown ratings withhold operational
loading. Synthetic loading is eligible only on simulated source/origin and
synthetic config. Fictional fixture `HX-A` uses 100 kVA, LV line-to-line 400 V
and rated LV line current 144.337567 A; it is not a real nameplate. PF=1 and
S=120 kVA yields 120% loading for the synthetic overload oracle. No universal
thermal limit, insulation-life budget or standards compliance is supplied.

For compatibility, legacy registry values that the current backend accepts,
including nonpositive ratings, remain representable without new configuration
metadata. They are operationally ineligible. New 1.1.0 configuration rejects
nonpositive ratings; this does not reinterpret old readings as verified values.

Counter/source semantics live in a versioned register/source configuration,
not inferred from `energy_kwh`: cumulative/net/import/export meaning, units,
width/modulus or unknown, boundary/side, reset evidence and continuity evidence.

## Analytics and metadata

Preserve existing scalar names, nullable health components, ten legacy reason
codes, maintenance enum `NORMAL/WATCH/PLAN/URGENT`, and top-level
`inference_status=OK|INSUFFICIENT_DATA`. OK describes the overall legacy input
gate, not universal component readiness, real prognosis or healthy condition.
New optional `metadata` and `rul` must survive ML → SQL → latest/history → UI.
`schema_version` is the wire version; artifact versions remain truthful.

Every currently emitted metadata key remains with its existing meaning:

| Existing key | Type / meaning |
|---|---|
| `thermal_readiness` | Nullable `INITIALIZING/WARMING_UP/READY/GAP_RESET/INSUFFICIENT_FORCING/UNINITIALIZED` |
| `thermal_model_mode` | Nullable `PUBLIC_EMPIRICAL/VERIFIED_UNIT_EMPIRICAL/STANDARDS_INSPIRED_ELIGIBLE` |
| `thermal_temperature_unit` | Nullable unit string; no source-indicator to °C conversion |
| `apparent_power_utilization` | Nullable dimensionless S/rating (not percent) |
| `forecast_operational_status` | Nullable string, legacy bundle release gate preserved |
| `experimental_fault_risk` | Nullable number [0,1], research-only, never operational risk |
| `maintenance_trip_latched` | Nullable boolean |
| `maintenance_clear_policy_status` | Nullable string, preserve full operator-clear/configuration status text |
| `coverage_overall`, `health_coverage` | Nullable fractions [0,1], component input assessment, not automatically time coverage |
| `extended_reason_codes`, `extended_health_reason_codes` | String arrays retaining reasons absent from legacy enum |
| `reason_descriptions` | String map; preserve source-unit wording |

Add typed `components` keyed by `thermal/anomaly/health/maintenance/forecast/rul`.
Each value has `status=READY|WARMING_UP|INSUFFICIENT_DATA|UNAVAILABLE`, nullable
unit, coverage fraction and string reasons. Thermal native readiness above
remains authoritative detail. Add `units` map; `coverage` object with aware
nullable start/end, covered/expected seconds, fraction, gaps, missing fields;
`reason_evidence` array of `{code, trigger, value, unit, threshold,
reference_source, duration_seconds}`; `forecast` with target definition,
horizon hours, release status (`UNRELEASED/INSUFFICIENT_VALIDATION/RELEASED`),
operational eligibility and limitation codes; `versions` with bundle ID,
configuration version, preprocessing version and artifact schema version.
New metadata members are optional for legacy metadata compatibility, explicitly
populated in 1.1.0 fixtures. Extended unknown codes go here, never into legacy
`reason_codes`/`health_reason_codes`.

Without validated release and eligible input evidence, `fault_risk`,
`predicted_fault` and `prediction_confidence` stay null. Historical API examples
with stub proxy numbers remain schema-representable as legacy examples, not
evidence of operational release. The legacy compatibility fixtures preserve
their versions; new operational fixtures have null risk.

Unavailable ML is represented as null `analytics` on the existing latest shape,
with additive `analytics_availability={status, reasons, state_coverage_loss}`.
No invented HEALTHY status. An insufficient-data result may contain available
components, but absent inputs never generate values by default.

## RUL and energy resources

Proposed `GET /api/v1/transformers/{id}/rul`: 200
`{transformer_id, timestamp, rul, schema_version}` where timestamp is the latest
persisted RUL observation time, not request time. No saved result: timestamp/rul
null (200); unknown registered asset: 404 existing error envelope. `rul` uses
exact strategy names: `rul_status`, `rul_method`, `rul_target_definition`,
`rul_value`, `rul_unit`, `rul_lower`, `rul_upper`, `uncertainty_kind`,
`forecast_horizon_hours`, `future_duty_scenario`, `degradation_state`,
`end_threshold`, `equivalent_ageing_hours`, `source_kind`, `simulated`,
`model_version`, `config_version`, `required_inputs`, `assumptions`,
`limitation_codes`, `coverage_start`, `coverage_end`, `coverage_fraction`,
`timestamp`; add nullable `degradation_unit` and `degradation_rate_per_hour`
to make the scenario equation reproducible. Legacy unknown source uses null.

Statuses: `SIMULATED_ESTIMATE`, `CONDITIONAL_ESTIMATE`, `INSUFFICIENT_DATA`,
`NO_CROSSING_WITHIN_HORIZON`, `END_THRESHOLD_REACHED`. Internally `rul_unit=h`.
No-crossing/insufficient results have null value/bounds. END_THRESHOLD_REACHED
has zero. Numeric crossings must lie within declared horizon. Method strings
identify exact versioned algorithms (fixtures `SYNTHETIC_FIRST_PASSAGE_V1`,
`THERMAL_AGEING_ELIGIBILITY_V1`). Required real inputs include verified hot-spot
semantics/model, insulation/applicability, life budget, prior consumed exposure
and future duty; absent prerequisites keep operational value null. Recent stress
can supply eligible equivalent ageing without an absolute RUL.

Synthetic D=.2, D_EOL=1, g=.01/h gives `(1-.2)/.01=80h`, horizon 100h. Bounds
vary rate [.008,.012]/h → [66.6666666667,100] h; `uncertainty_kind=SCENARIO_RANGE`,
not a confidence interval. Without range, bounds and uncertainty kind are null.
Zero rate returns no crossing, null time; already at endpoint returns zero.
Missing D/rate/endpoint returns insufficient. Gaps withhold accumulated
degradation unless an explicit scenario assumption supplies it. These are
fictional scenario times; HI/anomaly never convert to remaining years and no
empirical accuracy or whole-transformer lifespan is claimed.

Proposed `GET /api/v1/transformers/{id}/energy?window=1h`: 200 energy object
defined by `energy.schema.json`. `window=1h|6h|24h|7d`, default 1h. Reuse aware
`from`/`to` and `anchor=latest|now`, default now, exactly following
`query_dependencies.time_window` and `query_service.resolve_window`:

1. Explicit `to` sets end. Otherwise latest is selected only if anchor=latest
   **and from is absent**; no telemetry falls back to captured UTC now.
2. With only from, end is captured now even with anchor=latest (existing behavior).
3. Explicit from sets start; otherwise start=end-window. Both bounds override
   window duration. Reject start>=end, naive bounds, unsupported window/anchor,
   and span exceeding configured MAX_WINDOW_DAYS with 422. Unknown asset: 404.
4. Calculate only event-time support within [start,end]. Endpoints at end can
   close the final interval; intervals compose without double-counting. Fetch
   required endpoints/context, not a silently capped first page. Clip power
   intervals with explicitly declared linear interpolation; exclude unproven
   boundaries for counters. No integration outside the window or indefinite hold.

Fields include `energy_method=MEASURED_COUNTER|CALCULATED_POWER|SIMULATED|UNAVAILABLE`
and independent **required** `calculation_method=COUNTER_DIFFERENCE|TRAPEZOID|NONE`.
Synthetic counters remain SIMULATED+COUNTER_DIFFERENCE, never measured real energy.
`source_kind` is source provenance (nullable unknown), not calculation method.
`energy_status=AVAILABLE|PARTIAL|INSUFFICIENT_DATA|UNAVAILABLE`,
`active_power_unit_status=VERIFIED|SYNTHETIC|UNVERIFIED|UNKNOWN`,
`energy_unit=kWh`, `window_start/end`, covered seconds/fraction, gap/reset counts,
missing intervals with reason, and assumptions/limitations/provenance are explicit.
Result timestamp is nullable last contributing event. Nullable consumption,
import/export, peak/time/profile, losses, efficiency and savings carry no zeros
for unknowns. Configuration/map/calculation versions and identity are preserved.

Counter differences use positive time and verified cumulative semantics. Exact
retries add nothing. Negative jump is an excluded reset interval, not abs(delta)
or negative consumption; begin a new segment. No inferred modulus. Long-gap
counter delta is eligible only with independent continuity evidence. Trapezoid
uses `0.5*(P0+P1)*seconds/3600`; exclude missing/invalid endpoints and intervals
exceeding declared maximum gap. Fixture arithmetic explicitly allows 1h steps;
it does not configure a 5s stream to accept a 2h hole. Report covered partial
energy separately from total: default minimum coverage 1.0 means a deficient
window has null `consumed_kwh`; nullable `covered_consumed_kwh` may report only
eligible segments with PARTIAL label. No valid segment or unknown units yields
both null. Never add counter and integrated power totals together.

Loss/efficiency/savings are null without compatible verified or synthetic
boundary/side, loss inputs and eligible service comparison. `loss_method` and
conservation recommendation/evidence are nullable. Same delivered service and
common duty/horizon are mandatory for simulated savings. Optional P0+Pr*K²
requires explicit assumptions; no measured savings or operating-control advice
from a single unknown meter. The basic golden examples deliberately withhold
losses, efficiency and recommendations rather than inventing parameters.

## Semantic hash, identity, receipts and late outcomes

Hash algorithm `semantic-sha256-v1`. Hash the normalized flat semantic telemetry
payload: transformer ID, UTC event timestamp, all 21 measurements, flat
source/scenario strings and acquisition provenance if present. Include sequence,
source units/verification, expected interval and map version. Exclude
`schema_version` (wire version), acquisition `snapshot_id`, server `received_at`,
and all retry-only transport context (never in source body). Absent/null
acquisition normalizes to null; absent optional flat source/scenario fields and
measurements normalize to explicit null. Do not fill missing acquisition with
inferred labels. Acquisition requires its declared keys, so no ambiguous defaults.

Serialization is normative and implemented only as a fixture oracle here:

- Parse JSON numbers as arbitrary-precision decimals, reject NaN/Infinity,
  duplicate object keys and booleans in numeric measurement slots. Equivalent
  numerical values 10,10.0,1e1 hash identically. Negative zero becomes 0. Emit
  minimal plain decimal (no exponent/trailing fractional zeros, no rounding).
  IEEE producers use shortest round-trip decimal strings before normalization;
  different numerical values remain different. Protection becomes integer 0/1.
- Aware timestamps accept offsets, normalize to UTC
  `YYYY-MM-DDTHH:mm:ss.ffffffZ` at microsecond precision; reject finer precision
  rather than silently truncating. No naive timestamps, epoch numbers or leap
  seconds. Equal instants hash equally.
- Recursively sort object keys by Unicode code point; preserve array order.
  JSON strings use UTF-8, no ASCII escaping of Unicode, standard JSON quote,
  backslash/control escapes, no Unicode normalization or whitespace trimming.
  Reject unpaired surrogates. No insignificant whitespace or trailing newline
  in the hashed byte stream. Null is literal `null` and remains distinct from 0.
- Lowercase SHA-256 hex of those UTF-8 bytes is `snapshot_id` and `payload_hash`.
  Backend recomputes; a supplied inconsistent hash is 422 invalid snapshot,
  rather than a receipt for a different payload. Known byte/hash vectors reside
  in `hash-vectors.json` for identical bridge/backend implementations.

Primary accepted-observation uniqueness remains `(transformer_id, UTC timestamp)`.
Exact semantic retry returns existing accepted receipt/result, no state/energy/
alert effect. Changed measurement **or semantic provenance** at the same key:
409 conflict, quarantine attempt evidence, no accepted-row overwrite. Reusing
an old snapshot ID with changed bytes fails hash validation; changed same-time
payload with its own correct new hash still conflicts on observation identity.

Proposed read-only `GET /api/v1/ingestion/receipts/{snapshot_id}`:

- 200 `{schema_version, receipt_status: COMMITTED|CONFLICT, snapshot_id,
  payload_hash, transformer_id, timestamp, received_at, committed_at,
  accepted_snapshot_id, accepted_payload_hash, ingestion_outcome,
  analytics_status, state_coverage_loss}`. Hash/identity describe the queried
  attempt. COMMITTED points accepted hash/ID at itself. Exact retry returns
  the original receipt times. CONFLICT points to the previously accepted hash;
  `committed_at` is null (the attempt was not accepted). A conflict receipt is
  queryable only after its quarantine record commits, without altering telemetry.
- 404 standard `{error:{code:RECEIPT_NOT_COMMITTED,message,details:{snapshot_id}}}`
  for absent, pending, rolled-back or rejected-late attempts. It means no
  committed receipt visible, not proof that the source never published. Malformed
  hash is 422. No PENDING receipt claiming durability.
- `ingestion_outcome=ACCEPTED|EXACT_RETRY|CONFLICT|REJECTED_LATE_OBSERVATION` is
  a distinct ingestion outcome schema, never a new inference_status. Late live
  observations are rejected/quarantined with null analytics and no forward-state
  advance; endpoint returns 409 sequencing outcome. Existing exact retries are
  checked before late ordering, so old accepted retries remain idempotent.
- MQTT publish acknowledgment only establishes broker delivery. Source polls
  receipt by hash to establish database commit; `received_at` alone is insufficient.

Replay registers a separate destination asset, records origin ID/kind/run ID,
keeps original aware source event time, and uses its own checkpoint/history.
SIMULATED→REPLAYED changes semantics and hash. Never relabel or overwrite accepted
live rows, and never share forward live state. Replay speed affects wall time
only. Asset/topic/unit-ID mismatches are rejected before accepted persistence.

## Checkpoint lifecycle

Backend owns the single-process per-asset lock, SQL transaction and installation
ordering; ML owns serialized state and compatibility/migration policy. Proposed
boundary: `prepare(asset,record,history,current_checkpoint)` returns candidate
result/checkpoint without mutating committed state; `install(candidate)` only
after SQL commit; `discard(candidate)` on rollback. These describe H01 targets,
not methods already implemented on the current `analyze` protocol.

1. Lock asset; validate/dedupe/conflict/late checks before inference.
2. Restore committed compatible state; prepare against a deep copy.
3. Persist accepted telemetry, analytics (or null), receipt and candidate
   checkpoint atomically with alert/maintenance effects in backend transaction.
4. Successful commit → install candidate under the same asset lock. If process
   dies after commit before install, restore the durable checkpoint before next
   prepare. Failed commit → discard, unchanged committed ML state.
5. Restart → rehydrate compatible checkpoint, or explicit WARMING_UP /
   REINITIALIZED with coverage loss and reasons. Preserve unresolved trip/latch
   evidence; inability to restore its status is unknown, never automatic clear.
6. ML unavailable → retain accepted telemetry/receipt with null analytics,
   `state_coverage_loss=true`, record missing interval in checkpoint coverage;
   do not advance degradation/thermal as if observed inference occurred.

Checkpoint envelope `checkpoint_version=1.0.0` is a new state-format version,
not a model bump: transformer identity; committed event time and last
snapshot/hash; bundle ID, contract/feature/model/preprocessing/config versions;
`lifecycle_status=READY|WARMING_UP|REINITIALIZED|COVERAGE_LOSS`; state categories
`thermal`, `history`, `anomaly_persistence`, `health_persistence`,
`maintenance_persistence`, `synthetic_degradation`, `coverage`.
Each stores `{state_version, payload}` (nullable payload if unavailable). ML
must freeze detailed owning-module payload in H01; H00 does not pretend opaque
module internals are a universal public API. Thermal includes dynamic value,
forcing, previous timestamp and warm-up/readiness; history is causal time-bounded
canonical records plus cadence/capacity/truncation (one hour at 5s needs ~720
prior rows, not 60); persistence includes counters/durations/previous states;
maintenance includes trip latch and clear-policy evidence; synthetic degradation
includes D/endpoint/rate/covered event history/seed/scenario version; coverage
includes skipped inference/time gaps and loss of known history. Last result and
observation count support idempotence. No pickle or unversioned arbitrary state
trusted at load. Envelope compatibility is necessary but not sufficient; module
payload compatibility and configuration changes are checked explicitly.

## Register-map interface and unknown inputs

`register-map.schema.json` freezes requirements and a fictional mapping, with
addresses/encoding intentionally blocked for Person 4 in H03. No guessed OEM
addresses. Each entry declares field, nullable zero-based address/count/type,
byte/word order, multiplier, unit/verification, side, missing sentinel and quality
bit. Control writes forbidden; FC04 for demo input registers. Map includes
sequence guard before/after multi-block reads, source event timestamp, version
and coherent snapshot requirements. Unknown quality never becomes a fresh zero.
Mapping `(endpoint, unit_id)` uniquely selects registered transformer ID and
side/CT/PT/config. Fixture HX-A→unit 1, HX-B→unit 2 at local port 1502 is fictional;
no production device claim. An incomplete map cannot be deployed until H03 fills
and tests encoding/counts/widths/scales/sentinels and snapshot reads independently.

Remaining owner inputs: Person 1 original artifact manifest and truthful bundle
identity/versions; Persons 1/2 compatible state payloads and safe latch restore;
Person 2 storage/API review of conflict and null outcomes; Person 3 null/source/
range display review; Person 4 tested register addresses/encoding and topic/unit
mapping. Real units/timezone/contact/side/nameplate, counter sign/reset continuity,
hot-spot/insulation/life history/loss parameters and live authorization remain
unknown or blocked pending operator/OEM evidence. They do not justify invented
ratings or prevent explicit insufficient-data software behavior.

## Evidence and stopping point

See [actual H00 validation evidence](../../tests/fixtures/hackathon/VALIDATION.md).
Owner review remains pending; documents and passing fixture checks do not mean
API/database/ML/protocol integration is complete. Production code is untouched.
H01 is the next dependent phase; H02–H04 may start from this contract after review.
No H01–H07 implementation, commits, pushes or merges are part of H00.

Supporting specifications:
[H00](../phases/00_CONTRACTS_AND_GOLDEN_FIXTURES.md),
[roadmap](../hackathon_readiness/IMPLEMENTATION_ROADMAP.md),
[acceptance](../hackathon_readiness/INTEGRATION_AND_DEMO_ACCEPTANCE.md),
[gap analysis](../hackathon_readiness/GAP_ANALYSIS.md),
[target](../hackathon_readiness/TARGET_ARCHITECTURE.md),
[traceability](../hackathon_readiness/REQUIREMENTS_TRACEABILITY_MATRIX.md),
[questions](../hackathon_readiness/OPEN_QUESTIONS_AND_ASSUMPTIONS.md),
[RUL/energy](../hackathon_readiness/RUL_AND_ENERGY_STRATEGY.md),
[connectivity](../hackathon_readiness/CONNECTIVITY_AND_REALTIME_OPTIONS.md).
