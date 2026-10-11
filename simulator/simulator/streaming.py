"""
Streaming / live simulation — simulator_README §10.

Publishes canonical TransformerRecords over MQTT (or falls back to
HTTP POST to the backend API when MQTT is unavailable).

Conceptual flow:
  Simulator → MQTT → Backend Consumer → PostgreSQL → ML/Twin → Dashboard

MQTT topic convention (matches backend .env):
  transformer/{transformer_id}/telemetry
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Optional

import httpx

from .schema import TransformerRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MQTT publisher
# ---------------------------------------------------------------------------

class MqttPublisher:
    """
    Publishes canonical telemetry to an MQTT broker.

    Parameters match the backend's .env MQTT settings.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        qos: int = 1,
        timeout: float = 5,
    ) -> None:
        # Import lazily so the package is usable without paho if only HTTP is needed
        import paho.mqtt.client as mqtt

        self.host = host
        self.port = port
        self.qos = qos
        if qos != 1:
            raise ValueError("telemetry delivery requires QoS 1")
        self.timeout = timeout
        self.client_id = client_id or f"simulator-{uuid.uuid4().hex}"
        self._connection = threading.Event()

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )
        if username:
            self._client.username_pw_set(username, password or "")
        self._connected = False
        self._client.connect_timeout = timeout
        self._client.max_queued_messages_set(25)
        self._client.max_inflight_messages_set(1)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self._connected = not reason_code.is_failure
        self._connection.set()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._connected = False
        self._connection.clear()

    def connect(self) -> None:
        self._connection.clear()
        self._client.connect(self.host, self.port, keepalive=60)
        self._client.loop_start()
        if not self._connection.wait(self.timeout) or not self._connected:
            self.disconnect()
            raise ConnectionError("broker CONNACK was not successful")
        logger.info("MQTT connected to %s:%d", self.host, self.port)

    def disconnect(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
        self._connected = False
        self._connection.clear()

    def publish(self, record: TransformerRecord) -> None:
        """Publish one canonical record to the topic ``transformer/{id}/telemetry``."""
        if not self._connected:
            self.connect()

        payload = record.model_dump(mode="json")
        return self.publish_payload(payload)

    def publish_payload(self, payload):
        from ml.pipeline.identity import serialize
        if not self._connected:
            self.connect()
        topic = f"transformer/{payload['transformer_id']}/telemetry"
        info = self._client.publish(topic, serialize(payload), qos=1, retain=False)
        if info.rc != 0:
            raise ConnectionError(f"MQTT publish failed rc={info.rc}")
        info.wait_for_publish(timeout=self.timeout)
        if not info.is_published():
            raise TimeoutError("MQTT PUBACK timeout")
        return {"broker_acknowledged": True, "mid": info.mid, "committed": False}


# ---------------------------------------------------------------------------
# HTTP publisher (fallback when MQTT broker is not available)
# ---------------------------------------------------------------------------

class HttpPublisher:
    """
    Posts canonical telemetry to the backend's bulk-ingest endpoint.

    Matches the backend API at ``POST /api/v1/telemetry/batch?source_name=X``.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        source_name: str = "simulator",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.source_name = source_name
        self._client = httpx.Client(timeout=10)

    def publish(self, record: TransformerRecord) -> None:
        self.publish_batch([record])

    def publish_batch(self, records: list[TransformerRecord]) -> None:
        """Post a batch of canonical records to the backend.

        Backend endpoint: POST /api/v1/telemetry/batch?source_name=X
        Body schema: RawTelemetryBatchIn = {"records": [dict, ...]}
        """
        url = f"{self.base_url}/api/v1/telemetry/batch"
        payload = {
            "records": [
                json.loads(r.model_dump_json()) for r in records
            ],
        }
        try:
            resp = self._client.post(
                url,
                json=payload,
                params={"source_name": self.source_name},
            )
            resp.raise_for_status()
            logger.info("HTTP POST %d records -> %s (%d)", len(records), url, resp.status_code)
        except httpx.HTTPError as exc:
            logger.error("HTTP publish failed: %s", exc)
            raise

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Unified publisher
# ---------------------------------------------------------------------------

class StreamPublisher:
    """
    Thin wrapper that tries MQTT first, falls back to HTTP.
    """

    def __init__(
        self,
        mqtt_host: Optional[str] = None,
        mqtt_port: int = 1883,
        http_url: str = "http://localhost:8001",
        source_name: str = "simulator",
    ) -> None:
        self._mqtt: Optional[MqttPublisher] = None
        self._http: Optional[HttpPublisher] = None

        if mqtt_host:
            try:
                self._mqtt = MqttPublisher(host=mqtt_host, port=mqtt_port)
                self._mqtt.connect()
            except Exception:
                logger.warning("MQTT unavailable; explicit direct HTTP fallback. Modbus disconnected/not in this path.")
                self._mqtt = None

        if self._mqtt is None:
            self._http = HttpPublisher(base_url=http_url, source_name=source_name)

    def publish(self, record: TransformerRecord) -> None:
        if self._mqtt:
            self._mqtt.publish(record)
        elif self._http:
            self._http.publish(record)

    def publish_batch(self, records: list[TransformerRecord]) -> None:
        if self._http:
            self._http.publish_batch(records)
        else:
            for r in records:
                self.publish(r)

    def close(self) -> None:
        if self._mqtt:
            self._mqtt.disconnect()
        if self._http:
            self._http.close()
