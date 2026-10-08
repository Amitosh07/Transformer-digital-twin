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
import time
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
        client_id: str = "transformer-simulator",
        username: Optional[str] = None,
        password: Optional[str] = None,
        qos: int = 1,
    ) -> None:
        # Import lazily so the package is usable without paho if only HTTP is needed
        import paho.mqtt.client as mqtt

        self.host = host
        self.port = port
        self.qos = qos

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        if username:
            self._client.username_pw_set(username, password or "")
        self._connected = False

    def connect(self) -> None:
        self._client.connect(self.host, self.port, keepalive=60)
        self._client.loop_start()
        self._connected = True
        logger.info("MQTT connected to %s:%d", self.host, self.port)

    def disconnect(self) -> None:
        if self._connected:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info("MQTT disconnected.")

    def publish(self, record: TransformerRecord) -> None:
        """Publish one canonical record to the topic ``transformer/{id}/telemetry``."""
        if not self._connected:
            self.connect()

        topic = f"transformer/{record.transformer_id}/telemetry"
        payload = record.model_dump_json()
        info = self._client.publish(topic, payload, qos=self.qos)
        info.wait_for_publish(timeout=5)
        logger.debug("Published to %s", topic)


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
                logger.warning("MQTT unavailable — falling back to HTTP.")
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
