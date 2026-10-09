# Connectivity and real-time options

Actual state: MQTT consumer/publisher and HTTP ingestion/replay exist; Modbus/pymodbus/register map/bridge do not. The proposed Modbus-to-MQTT design fits the current backend because the bridge can publish canonical JSON to its existing `transformer/{id}/telemetry` topic and common validation/storage path. MQTT complements acquisition, not a replacement for the required Modbus demonstration.

## Options and necessary access

| Option | Equipment/software | Permission and readiness | Suitability |
|---|---|---|---|
| Modbus TCP simulator → bridge → MQTT | Laptop/containers, pinned stable pymodbus server/client, Mosquitto, backend/PostgreSQL, frontend | Team owns all components; no college telemetry dependency; must add server/map/bridge | Primary complete protocol demo |
| Modbus TCP authorized meter/gateway | Ethernet device, OEM register map/firmware, CT/PT scaling, approved isolated network | College/operator approval and readable registers required; presently unconfirmed | Future live read-only path |
| Modbus RTU | Meter with RS-485, isolated USB-RS485/approved gateway, correct wiring/termination, slave id/baud/parity, OEM map | Qualified operator access to existing communication port; avoid unauthorized panels/measurement wiring | Only if actual device requires it; unnecessary for software-only demo |
| MQTT-native simulator | Existing paho publisher and broker | Already present; fix delivery/coherence | Useful test transport, does not demonstrate Modbus |
| Canonical timestamped replay → HTTP | Existing backend batch/replay and approved adapter output | No hardware; source time/unit/provenance must be declared | Fallback for analytics/dashboard; explicitly say Modbus path unavailable |
| Replay-backed Modbus server | Historical canonical values exposed via same register map | Same server/bridge as primary; unknown source units remain qualified | Protocol demonstration plus preserved replay event time |

Official Modbus specifications define application function codes and TCP framing; a transformer is not inherently a Modbus endpoint—normally a meter/gateway/protection monitor exposes readings. Reference: https://modbus.org/modbus-specifications and https://modbus.org/file/secure/messagingimplementationguide.pdf (reviewed 9 October 2026). TCP simulation requires no RS-485 equipment. RTU equipment and register configuration are device-specific.

## Primary path contract

1. Existing seeded generator creates a canonical snapshot with declared fictional asset rating and units. Drive time-dependent scenarios before encoding.
2. Modbus TCP server exposes a versioned immutable snapshot as input registers (FC04) and read-only status bits. If a vendor uses holding registers, use FC03 read requests only. No FC05/06/15/16 control writes. Simulator updates its internal datastore; that is distinct from commanding real equipment.
3. Bridge polls per-asset unit id / endpoint, reads sequence/time and all values consistently, decodes scale/endianness, validates, then publishes canonical JSON QoS1.
4. Existing consumer checks topic id, payload schema and finite/boolean/time rules, then common ingestion persists telemetry and actual ML outputs.
5. REST exposes persisted results; React polling renders source-labelled measurements and analytics.

Use a nonprivileged local simulator port such as 1502 as a proposed demo configuration; actual devices often use the standard TCP port according to their operator map. Do not expose the server publicly. Pin and test a stable pymodbus version against its matching docs: stable server docs currently show 3.15.0, while `latest` shows development 4.0 changes. Reference: https://pymodbus.readthedocs.io/en/stable/source/server.html. Do not mix copied 3.x/4.x signatures.

The register map must enumerate address convention (zero-based vs human register numbers), field, read function, count, uint/int/float type, byte and word order, multiplier, physical unit, side/CT/PT ratio, missing sentinel plus quality bitmap, asset/unit id, sequence and map version. Proposed minimum: canonical phase voltages/currents/neutral, oil/ambient (winding only with valid semantics), oil level, P/S/Q/energy/PFs, protection bits. Simulated map may define Celsius/percent deliberately with SIMULATED provenance; historical source data cannot inherit these conversions without verification. Avoid using zero as universal missing sentinel.

Modbus does not supply a canonical observation timestamp automatically. Use source snapshot UTC timestamp/sequence registers when defined; otherwise bridge acquisition timestamp with `timestamp_origin=GATEWAY_POLL` explicitly. Read sequence before and after a multi-block snapshot and retry on change; this prevents mixing times and torn 32-bit counters. Long counters need enough width and documented resolution/rollover. Device id must map to registered transformer id and voltage/current side.

## MQTT and failure behavior

Current paho path defaults to MQTT 3.1.1 behavior; no MQTT5 capability is assumed. QoS1 permits duplicates and provides transport delivery, not proof of database commit. Retained messages are broker latest-value storage, not history. OASIS 3.1.1: https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html; 5.0 option: https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html. Keep historical telemetry non-retained; use separate retained status/last-will only with freshness checks. Publisher needs explicit connection/PUBACK failure tracking; consumer diagnostics need received versus accepted/committed/drop counters.

| Failure | Proposed behavior / verification |
|---|---|
| Modbus timeout/exception/invalid map | Bounded timeout/backoff; mark affected measurements unavailable, never reuse stale values as fresh; show gateway disconnect and last success |
| Scaling or non-finite value | Quarantine raw decode reason/map version; reject invalid canonical measurement; no silent plausible default |
| Torn snapshot | Retry bounded times using sequence guard; skip/increment inconsistency count if unresolved |
| Broker interruption | Bounded durable source spool, unique snapshot key, reconnect; operator may choose labelled HTTP fallback |
| Queue/SQL failure | Expose dropped/uncommitted counts; replay retained source records; current memory queue is insufficient for guaranteed delivery |
| Duplicate replay/retry | No second analytics/energy accumulation; changed payload at identical asset/time is conflict |
| Restart or late source data | Explicit reinitialization or validated checkpoint/replay; report sequencing status and preserve historical source time |
| Device count scale | Unique publisher ids and per-asset state; no unbounded pre-generation or shared fault-ramp state |

The backend known-limitations document already acknowledges transport ACK before SQL commit and process-local replay. Address these concretely; QoS2 would not fix application transaction durability by itself.

## Demonstration without live telemetry

Prepare a local environment with tested dependencies, existing ML bundle or clearly labelled demo config, registered simulated asset and canonical scenario trace. Show read-only Modbus requests with an independent client, then one matching stored record and dashboard timestamp. Demonstrate balanced load, rated overload, thermal divergence, simulated alarm/trip, missing register and broker recovery. Use accelerated wall playback while preserving event timestamps; pre-roll adequate thermal/persistence history instead of skipping warm-up.

Fallback: run the same canonical trace through existing HTTP batch/replay, visibly `REPLAYED` or `SIMULATED`, plus network status showing Modbus disconnected. This keeps analytics demonstrable but does not satisfy protocol demonstration alone; separately record/retain a successful Modbus trace if the live presentation fails. No automatic concealment of fallback as live data.

Before any future real connection, operator approves device/port/read requests, units/ratios and network window. Keep monitoring read-only, isolated and rate-limited. No recommendation here authorizes writes to controls or protection systems.
