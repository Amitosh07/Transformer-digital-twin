# MQTT ingestion contract for Person 4

Enable `MQTT_ENABLED=true` and set MQTT_HOST/MQTT_PORT before starting the backend.
Defaults are localhost:1883, MQTT_CLIENT_ID=transformer-backend, MQTT_QOS=1 and
MQTT_TOPIC=transformer/+/telemetry. Each concurrently running backend instance needs
its own stable client ID: the broker disconnects an existing client with the same ID.
Optional MQTT_USERNAME/MQTT_PASSWORD configure authentication; empty values mean unset.
MQTT_SOURCE_NAME=mqtt labels records when the source_name key is omitted.
MQTT_QUEUE_MAX=10000 limits queued messages, not queued records. MAX_BATCH_SIZE=5000
limits records in one JSON array. Reconnect delays grow exponentially between
MQTT_RECONNECT_MIN_S=1 and MQTT_RECONNECT_MAX_S=30.

## Topic and payload

Publish UTF-8 JSON to `transformer/TX-001/telemetry`. Single-object example:

```json
{
  "transformer_id": "TX-001",
  "timestamp": "2026-10-07T09:00:00Z",
  "oil_temperature": 42,
  "oil_level": 8,
  "oil_temp_alarm": false,
  "source_name": "simulator",
  "scenario_id": "normal-demo"
}
```

Array example, using the topic identity fallback:

```json
[
  {"timestamp":"2026-10-07T09:00:01Z","oil_temperature":42,"oil_level":8},
  {"timestamp":"2026-10-07T09:00:02Z","oil_temperature":43,"oil_level":8}
]
```

When transformer_id is omitted, the single `+` segment supplies it. A present ID must
match that topic segment exactly. Custom patterns can move this wildcard, for example
site/telemetry/+; patterns permit at most one identity wildcard. Fixed topics or a
terminal # permit explicit IDs but cannot supply missing IDs. A mismatched topic is
rejected. Every array element must match the topic identity. Array order is preserved.

Only the canonical fields in CONTEXT.md and source_name/scenario_id metadata are valid.
Missing optional measurements stay null; zero is a present value. Timestamps require
an offset and normalize to UTC. Protection values accept only 0/1/true/false/null.
All floats must be finite; power factors use [-1,1]. Thermal/oil measurements have no
unit conversion or range check. Explicit source_name and scenario_id are preserved.
An invalid array element rejects the entire message before any database write.

## Delivery, transactions and shutdown

The network callback validates and enqueues without accessing PostgreSQL or ML.
One worker owns a fresh SessionLocal session per JSON message. Every row calls the
existing ingest_record service with run_ml=True; telemetry and analytics for the
message commit together. A database failure rolls back the whole message, including
previous array elements. The session closes and the worker processes the next message.
ML failures use the existing safe insufficient-result fallback and still save telemetry.

The paho v2 client uses MQTT 3.1.1, CallbackAPIVersion.VERSION2, clean_session=False,
and a fixed client ID. It subscribes after every successful connection and reconnect.
Connection happens asynchronously; an offline broker does not delay FastAPI startup.
QoS 1 with a persistent broker session supports delivery across short disconnects.
Duplicates remain possible. An existing (transformer_id,timestamp) is counted without
rewriting telemetry or rerunning ML. Broker persistence must be enabled for broker restarts.
Use the same timestamp when retrying a record.

The application queue is memory-only. MQTT acknowledgement confirms transport reception,
not a PostgreSQL commit. Queue-full messages are dropped immediately, and failed ingestion
messages are counted, with no automatic database retry. Person 4 should monitor counters
and retain source records for replay after overflow/failure/process loss. Retrying committed
rows is safe through ingestion idempotency.

Shutdown stops accepting, drains queued messages, then disconnects and joins threads before
closing the shared HTTP ML client. stop(timeout=10) bounds the total wait. On timeout,
pending messages are dropped and SHUTDOWN_TIMEOUT is recorded. Python cannot cancel a
stalled in-flight DB/ML call; its daemon worker may finish later. Configure upstream
operation timeouts for the desired shutdown budget. Normal shutdown drains all messages.

## Status and rejection reasons

`GET /api/v1/ingest/mqtt/status` is HTTP 200 even when enabled but disconnected.
The OpenAPI operation includes a full example. Disabled status is:

```json
{
  "enabled": false, "connected": false,
  "host": "localhost", "port": 1883, "topic": "transformer/+/telemetry", "qos": 1,
  "queue_depth": 0, "received_count": 0, "ingested_count": 0, "duplicate_count": 0,
  "rejected_count": 0, "dropped_count": 0, "error_count": 0,
  "last_message_at": null, "last_error": null, "recent_rejections": []
}
```

received_count counts accepted-for-parsing MQTT messages; rejected_count, dropped_count,
and error_count count messages/failures. ingested_count and duplicate_count count committed
records, so an array can add several. queue_depth excludes the currently processing message.
Counters reset when the process restarts. last_message_at and rejection time use aware UTC.
last_error is the most recent error code and can remain after recovery. recent_rejections
contains at most 20 objects: time, topic, reason and nullable field. Credentials, raw payloads,
unknown key names and exception details are never exposed in status/logs/rejection errors.

| Reason | Meaning |
| --- | --- |
| EMPTY_PAYLOAD | Zero bytes or whitespace only |
| INVALID_UTF8 / INVALID_JSON | Invalid encoding or JSON syntax |
| INVALID_TOP_LEVEL | JSON is neither an object nor an array |
| EMPTY_RECORDS / INVALID_RECORD | Empty array or non-object element |
| BATCH_TOO_LARGE | Array exceeds MAX_BATCH_SIZE |
| TOPIC_MISMATCH / TOPIC_ID_MISMATCH | Topic does not match, or ID disagrees |
| EXCLUDED_FIELD | Excluded measurement field supplied |
| VALIDATION_ERROR | Extra key, missing identity/time, naive time, non-finite or invalid value |
| QUEUE_FULL | Valid message dropped due to queue saturation |
| INGESTION_FAILED | Worker error; transaction rolled back |
| BROKER_UNREACHABLE / BROKER_CONNECTION_REJECTED | Broker offline or refused connection |
| SHUTDOWN_TIMEOUT / DISCONNECT_FAILED | Drain budget exceeded or disconnect error |

## Local Mosquitto and verification

From PowerShell with Docker Desktop running:

```powershell
cd C:\Transformer-backend\backend
docker run --detach --name transformer-backend-phase5-mqtt --publish 127.0.0.1:51883:1883 --mount "type=bind,source=$PWD/tests/mqtt/mosquitto.conf,target=/mosquitto/config/mosquitto.conf,readonly" eclipse-mosquitto:2
# On later runs, use docker start transformer-backend-phase5-mqtt.
$env:MQTT_ENABLED="true"
$env:MQTT_HOST="127.0.0.1"
$env:MQTT_PORT="51883"
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The checked-in Mosquitto config enables an anonymous listener and broker persistence
for local tests. Docker publishes it on localhost. Database setup follows README.md.

Python publisher (paho-mqtt v2 is installed with the backend):

```python
import json
from uuid import uuid4
import paho.mqtt.client as mqtt

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"simulator-{uuid4().hex}")
client.connect("127.0.0.1", 51883)
client.loop_start()
try:
    message = {
        "timestamp": "2026-10-07T09:00:00Z",
        "oil_temperature": 42,
        "oil_level": 8,
        "scenario_id": "normal-demo",
    }
    delivery = client.publish("transformer/TX-001/telemetry", json.dumps(message), qos=1)
    delivery.wait_for_publish(timeout=5)
    assert delivery.is_published()
finally:
    client.disconnect()
    client.loop_stop()
```

Use the Mosquitto CLI inside the test container:

```powershell
docker exec transformer-backend-phase5-mqtt mosquitto_pub -h localhost -p 1883 -q 1 -t transformer/TX-001/telemetry -m '{"timestamp":"2026-10-07T09:00:01Z","oil_temperature":42,"oil_level":8}'
Invoke-RestMethod http://127.0.0.1:8000/api/v1/ingest/mqtt/status
```

Run the real broker test or the entire suite:

```powershell
$env:DATABASE_URL="postgresql+psycopg://transformer:transformer@127.0.0.1:55432/transformer"
$env:TEST_DATABASE_URL=$env:DATABASE_URL
$env:MQTT_ENABLED="false"
$env:MQTT_TEST_HOST="127.0.0.1"
$env:MQTT_TEST_PORT="51883"
.venv/Scripts/python.exe -m pytest tests/mqtt/test_broker.py -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pytest -q -s
```

Without MQTT_TEST_HOST the broker test explicitly skips; acceptance runs set it.
PostgreSQL tests also require TEST_DATABASE_URL and an account with CREATEDB.
No schema migration is needed for MQTT.
