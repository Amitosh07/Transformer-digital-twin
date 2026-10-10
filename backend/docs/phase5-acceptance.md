# Phase 5 acceptance results

Verified on feature/backend-api on 2026-10-07. All changes are inside backend/.
The canonical context and both integration documents were read before implementation.
No schema migration or additional telemetry write path was introduced.

## Checks

| Check | Result |
| --- | --- |
| Ruff check | PASS |
| Ruff format --check | PASS |
| Full pytest with real PostgreSQL and MQTT_TEST_HOST | PASS, 486 tests, no skips, 142.71 seconds |
| Earlier regression coverage | PASS, all 435 previous tests |
| New MQTT coverage | PASS, 51 additional tests |
| Real Mosquitto publish into telemetry and analytics | PASS, including duplicate redelivery |
| Fresh disabled application import | PASS, neither app.mqtt.consumer nor paho imported |
| Canonical-name scan of new files | PASS |
| Single telemetry writer and no migration change | PASS |
| git diff --check | PASS |

The existing Starlette/httpx TestClient deprecation warning remains (one warning).
The initial focused run had one OpenAPI-example failure: FastAPI omitted null-valued
example fields. Populating those example values resolved it; the final full run passed.

## Acceptance coverage

- Parser: single/array messages, topic identity fallback, explicit matching/mismatching IDs,
  custom topic/source, fixed and multilevel patterns, excluded and unknown keys, naive times,
  offset-to-UTC conversion, NaN and both infinities, protection normalization/rejection,
  power-factor range, null preservation, invalid UTF-8/JSON, wrong types, empty payload/array,
  oversized array, whole-array rejection and payload-free errors.
- Fake paho and real PostgreSQL: assert the shared ingest_record call with run_ml=True;
  telemetry and analytics persistence; duplicate counters and one ML invocation; rejection
  counters with the last-20 ring; SQL rollback of an array; worker continuation after errors;
  non-blocking queue-full drops; configured backoff/credentials/QoS; reconnect subscription;
  paho v2 persistent-session construction; normal stop drains; stalled stop has a bounded wait
  and stops accepting new messages. Error logs omit exception content.
- Lifespan: disabled transport imports/starts nothing; enabled unreachable broker starts
  promptly and /health remains usable; MQTT stops before the HTTP ML client closes.
- Status: complete typed response, disabled configuration, live snapshot, HTTP 200 during
  disconnection, full OpenAPI example and a documented disconnection warning.
- Broker: Docker eclipse-mosquitto:2 (Mosquitto 2.1.2), localhost:51883; QoS 1 publish and
  duplicate delivery produce exactly one telemetry and one analytics row, with zero errors.
  This test ran against the actual broker, not a fake, both in the focused and full runs.

## Environment and reproduction

Python 3.12, paho-mqtt 2.1.0, PostgreSQL 16 via transformer-backend-phase1-pg at
localhost:55432. The test fixture migrates and drops a disposable PostgreSQL database.
The broker container is transformer-backend-phase5-mqtt, published on localhost:51883.
See mqtt.md for its Docker config and complete publish/setup commands.

```powershell
cd C:\Transformer-backend\backend
$env:DATABASE_URL="postgresql+psycopg://transformer:transformer@127.0.0.1:55432/transformer"
$env:TEST_DATABASE_URL=$env:DATABASE_URL
$env:MQTT_ENABLED="false"
$env:MQTT_TEST_HOST="127.0.0.1"
$env:MQTT_TEST_PORT="51883"
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pytest -q -s
```

MQTT_TEST_HOST was set for the reported run, so the broker test did not skip.
The application itself stays MQTT-disabled by default. tests/mqtt/test_broker.py explicitly
skips only when MQTT_TEST_HOST is absent; PostgreSQL fixtures require TEST_DATABASE_URL.

## Existing 10,000-row regression benchmark

| Operation | Seconds | Inserted | Duplicates | Parse errors | Range errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial stub batch | 83.191 | 10000 | 0 | 0 | 0 |
| Duplicate batch | 50.735 | 0 | 10000 | 0 | 0 |

This is the unchanged Phase 4 benchmark; timings reflect this local Docker run.

## Operational limits

The queue is in memory and MQTT acknowledgements precede database commit. Queue overflow
and database failures require source replay; duplicate replay is safe. Shutdown has a
10-second default budget, after which pending messages are counted as dropped; a stalled
in-flight Python thread cannot be forcibly cancelled. These behaviors are documented in
mqtt.md, along with the stable client-ID and broker persistence requirements.

## Files

See FILES.md, Phase 5 files, for the exact 18 created and 8 changed files.
