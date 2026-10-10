# H03 local simulator and bridge

All supplied assets, ratings and measurements are fictional. The map is
`fictional-lv-v1`, envelope `1.1.0`; model/artifact versions are unchanged.
Original fitted ML readiness is outside this source package.

Install the team's approved H01 runtime wheel first, then, from `simulator/`:

```powershell
python -m pip install <approved-transformer-ml-runtime-0.1.0-wheel>
python -m pip install -e '.[dev]'
simulator generate --count 12 --interval 5 --seed 42 --transformer-id H03-ORIGIN --start-utc 2026-10-09T00:00:00Z --output origin.jsonl
simulator modbus-server --config simulator/config/server-demo-25.json
# In another terminal, with the actual broker/backend running:
simulator modbus-bridge --config simulator/config/bridge-demo-25.json
# Separately register H03-REPLAY-R1 before this HTTP fallback:
simulator replay-canonical --input origin.jsonl --transformer-id H03-REPLAY-R1 --run-id R1 --http-url http://127.0.0.1:8001 --speed 20
```

The server defaults to loopback port 1502; other loopback ports are configurable.
The supplied 25-asset file proves configuration support, not a load rehearsal.
Register exactly those IDs/configurations with the backend owner. The server's
local configuration status is `SYNTHETIC_CONFIG`. `rated_voltage_lv` is line-line
V; currents are line A; no CT/PT ratios are applied. Declared fictional defaults
for legacy generator calls are 500 kVA, 415 V and derived rated line current.
These values never establish verified physical nameplate data. No real thermal
limits, insulation parameters, fitted predictions or fault probabilities are
introduced. Scenario catalogue expectations remain illustrative, not release
guarantees. WTI is unavailable/null; it is never emitted as continuous °C.

Generation is lazy through `iter_records` / `next_record`. `generate` keeps its
finite list API. Set start, seed and configuration explicitly for repeatability.
Thermal lag is exponential in positive elapsed event seconds (fictional 1200s
time constant); the zero-duration initial sample adds no energy. Final perturbed
phase V/I/PF determine S and P, equivalent lagging Q satisfies S²=P²+Q², then
trapezoidal event-time integration advances the synthetic counter. Fault sensor
offsets do not change the underlying thermal lag state. Standalone FaultInjector
has no prior-counter history; use generator scenario processing to recalculate
energy. Every scheduled asset owns RNG, injector, clock, sequence and energy.

Read the [versioned map](simulator/config/register-map-v1.json) for every address,
count, scale, signedness, unit, quality bit and counter behavior. Addresses are
zero-based PDU offsets. Only FC04 input reads are permitted; protection contacts
are status values. All words/bytes are big-endian. Header carries wire version,
unit ID, uint32 sequence, uint64 source epoch microseconds, uint32 quality,
UTF-8 asset/scenario IDs. Body uses scaled signed int32 measurements and a uint64
energy counter (1e-6 kWh resolution). Sequence and counter overflow reject rather
than wrap. Counter decreases pass through as resets; the bridge never differences
them into energy. Missing fields have clear quality bits and zero stored words;
available zero has its bit set. Altered maps, unsupported units/assets, non-finite
values and malformed words fail. IDs are limited to 64 UTF-8 bytes by this map.
Historical unknown units cannot inherit this fictional encoding: canonical HTTP
replay retains unknown units. Replay-backed historical Modbus is not provided.

The 102-register snapshot is read in two blocks (100 + 2), guarded by sequence
reads before/after. A whole datastore swap is atomic; mismatching guards retry
at most the configured count (1–10), with bounded short backoff. Failure skips
the sample and preserves the last measurement event time. Diagnostics on stdout
carry separate gateway time, connection state, last successful poll, missed
sequence count, torn/failure/reconnect counts and delivery counters. They do not
publish fresh telemetry merely because the gateway is connected. A backwards
source sequence requires deliberate source-run recovery/new destination.

Spool directory is resolved relative to the bridge config. One process owns its
lock. SQLite here is **local durable delivery storage**, not backend SQL evidence.
FULL synchronous local transactions preserve payload/identity, attempts/PUBACKs,
retry deadline, quarantine reason and committed per-asset watermarks across
restart. Capacity limits bound retained payload bytes/records and physical page
count (2×payload allowance + 1024 bytes/record, at least 256 pages; rollback
journal is transient and bounded by database size). Quarantine consumes capacity.
Acquisition pauses before polling when there is insufficient reserved space for
an 8192-byte snapshot; old entries are never silently evicted. The continuously
running source may advance while acquisition is paused; missed source sequences
are counted on reconnection. This is not guaranteed capture of every source
sample during an outage. Pending/quarantined older observations prevent newer
ones for the same asset overtaking them. Conflicts require operator resolution;
there is no automatic delete/quarantine-clear command.

MQTT 3.1.1 QoS1 uses a unique generated client ID, bounded client queue/inflight,
successful CONNACK and explicit PUBACK check, always `retain=False`, on existing
`transformer/{id}/telemetry`. Retry metadata lives only in the spool. H01's
`semantic-sha256-v1` implementation supplies the snapshot ID/hash. PUBACK retains
the entry. H02's existing GET receipt route must return COMMITTED, aware commit
time and matching snapshot/hash/accepted identity/asset/event time before removal.
404, HTTP500, malformed response and connection errors retain/retry; semantic
conflict quarantines. Exponential retry delay is bounded by configuration.
Successful receipt recovery can remove a previously committed entry before
republishing. Persistent watermarks avoid reacquiring/counting the same latest
committed snapshot after restart. This does not assert broker/SQL availability.

JSONL replay preserves source event timestamps regardless of playback speed,
keeps Decimal precision, requires destination and immutable run ID, and refuses
an origin-equal destination or conflicting live/replay destination. Registered
destination lookup is mandatory; same-run resume relies on backend exact-retry
checks. No source assets/configurations are overwritten or auto-registered.
An HTTP error or REJECTED_LATE stops the run; the file can resume with the same
destination/run for exact retries. For legacy sources use explicit `--timezone
UTC` (or an IANA timezone); provenance records ASSUMED/REPLAY_ASSUMPTION and
units remain UNKNOWN/UNVERIFIED. Original verified or synthetic field evidence
is retained; replay never upgrades unknown units. Direct HTTP fallback explicitly
reports that Modbus is disconnected/not used. It does not claim the primary
Modbus→MQTT→SQL path was demonstrated.

Legacy `replay <CSV...>` flags remain, with additive `--timezone`, `--run-id`,
`--origin-transformer-id` and `--adapter-path`. CSV replay calls the existing
shared adapter's loading/duplicate/normalization/merge/validation functions;
KW/KVA/KVAR/KWH and WTI conflict semantics come from that adapter, not another
mapping. The approved H01 wheel omits `ml.adaptors`: raw replay therefore needs
the repository's adapter file or an explicit path. Canonical JSONL replay is
portable and needs no raw datasets. Missing/invalid source data is not imputed.

Focused checks from `simulator/`:

```powershell
python -m pytest tests/test_schema.py tests/test_generation_h03.py tests/test_replay_h03.py tests/test_modbus_h03.py tests/test_delivery_h03.py tests/test_cli_h03.py
```

The protocol test starts a real separate loopback server process and independent
FC04 clients. Receipt responses in unit tests exercise the real H02 shape but
are test doubles; only a real backend PostgreSQL commit can close that gate.
See [H03 execution evidence](../docs/hackathon_readiness/execution/H03_SIMULATOR_MODBUS_MQTT_BRIDGE.md).

## H06 integrated local runtime

The H03 evidence above remains historical. H06 now supplies a six-service
Compose configuration, actual Python ML backend, persisted RUL/projection and
bounded energy APIs, registration/pre-roll scripts and real native SQL/MQTT/
Modbus/browser evidence. Follow the [H06 runbook](H06_RUNBOOK.md) for current
ports, native PowerShell and Git Bash commands, receipt semantics and explicit
demo-unverified limitations. Docker Desktop storage prevented clean-container
acceptance in this execution; native acceptance does not prove that gate.
