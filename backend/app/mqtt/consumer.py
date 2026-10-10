"""Non-blocking MQTT reception and one isolated PostgreSQL ingestion worker."""

import logging
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from queue import Empty, Full, Queue
from threading import Event, RLock, Thread
from time import monotonic
from typing import Any

import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.mqtt.message_handler import MessageRejected, parse_message
from app.schemas.telemetry import TelemetryIn
from app.services import ingestion_service
from app.services.mqtt_status_service import initial_status

logger = logging.getLogger(__name__)


class MqttConsumer:
    def __init__(
        self,
        client: mqtt.Client | None = None,
        *,
        settings: Settings | None = None,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = (
            client
            if client is not None
            else mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.settings.mqtt_client_id,
                clean_session=False,
                protocol=mqtt.MQTTv311,
            )
        )
        self._sessions = session_factory or SessionLocal
        self._queue: Queue[list[TelemetryIn]] = Queue(self.settings.mqtt_queue_max)
        self._lock = RLock()
        self._stopping = Event()
        self._abort = Event()
        self._accepting = False
        self._started = False
        self._worker: Thread | None = None
        self._values = initial_status(self.settings)
        self._rejections: deque[dict[str, Any]] = deque(maxlen=20)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_connect_fail = self._on_connect_fail
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(
            self.settings.mqtt_reconnect_min_s,
            self.settings.mqtt_reconnect_max_s,
        )
        if self.settings.mqtt_username is not None:
            self.client.username_pw_set(self.settings.mqtt_username, self.settings.mqtt_password)

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._accepting = True
            self._worker = Thread(target=self._work, name="mqtt-ingestion", daemon=True)
            self._worker.start()
        self.client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port)
        self.client.loop_start()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        with self._lock:
            self._values["connected"] = reason_code == 0
            if reason_code != 0:
                self._values["last_error"] = "BROKER_CONNECTION_REJECTED"
        if reason_code == 0:
            client.subscribe(self.settings.mqtt_topic, qos=self.settings.mqtt_qos)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        with self._lock:
            self._values["connected"] = False

    def _on_connect_fail(self, client: mqtt.Client, userdata: Any) -> None:
        with self._lock:
            self._values["connected"] = False
            self._values["last_error"] = "BROKER_UNREACHABLE"
        logger.warning(
            "MQTT broker unavailable host=%s port=%s; retrying",
            self.settings.mqtt_host,
            self.settings.mqtt_port,
        )

    def _on_message(self, client: mqtt.Client, userdata: Any, message: Any) -> None:
        with self._lock:
            if not self._accepting:
                return
            self._values["received_count"] += 1
            self._values["last_message_at"] = datetime.now(UTC).isoformat()
        try:
            records = parse_message(message.topic, message.payload)
        except MessageRejected as exc:
            with self._lock:
                self._values["rejected_count"] += 1
                self._values["last_error"] = exc.reason
                self._rejections.append(
                    {
                        "time": datetime.now(UTC).isoformat(),
                        "topic": message.topic,
                        "reason": exc.reason,
                        "field": exc.field,
                    }
                )
            logger.warning(
                "MQTT rejected topic=%s size=%s reason=%s",
                message.topic,
                len(message.payload),
                exc.reason,
            )
            return
        with self._lock:
            if not self._accepting:
                return
            self._values['validated_count'] += len(records)
            try:
                self._queue.put_nowait(records)
            except Full:
                self._values["dropped_count"] += 1
                self._values["last_error"] = "QUEUE_FULL"
                logger.warning(
                    "MQTT dropped topic=%s size=%s reason=QUEUE_FULL",
                    message.topic,
                    len(message.payload),
                )

    def _work(self) -> None:
        while not self._abort.is_set():
            if self._stopping.is_set() and self._queue.empty():
                return
            try:
                records = self._queue.get(timeout=0.05)
            except Empty:
                continue
            session = None
            record = records[0]
            try:
                session = self._sessions()
                # All assets are locked together in stable order for this transaction.
                if isinstance(session, Session):
                    ingestion_service.transactional_ml.lock_assets(session, [row.transformer_id for row in records])
                inserted = duplicates = 0
                for record in records:
                    result = ingestion_service.ingest_record(
                        session,
                        record,
                        run_ml=True,
                        _commit=False,
                    )
                    duplicates += int(result.duplicate)
                    inserted += int(not result.duplicate)
                session.commit()
                with self._lock:
                    self._values["ingested_count"] += inserted
                    self._values["duplicate_count"] += duplicates
                    self._values['committed_count'] += inserted + duplicates
            except Exception as exc:
                if session is not None:
                    try:
                        session.rollback()
                    except Exception:
                        pass
                if isinstance(exc, ingestion_service.telemetry_repo.SemanticConflict) and session is not None:
                    try:
                        ingestion_service._conflict_receipt(session, exc)
                    except Exception:
                        session.rollback()
                self._worker_error(record, exc)
            finally:
                if session is not None:
                    try:
                        session.close()
                    except Exception as exc:
                        self._worker_error(record, exc)
                self._queue.task_done()

    def _worker_error(self, record: TelemetryIn, exc: Exception) -> None:
        with self._lock:
            self._values["error_count"] += 1
            reason = getattr(exc, 'reason', 'INGESTION_FAILED')
            self._values["last_error"] = reason
            if reason == 'SEMANTIC_PAYLOAD_CONFLICT':
                self._values['conflicted_count'] += 1
                self._values['rejected_count'] += 1
                self._rejections.append({'time': datetime.now(UTC).isoformat(),
                    'topic': '', 'reason': reason, 'field': 'snapshot_id'})
        logger.error(
            "MQTT ingestion failed transformer_id=%s timestamp=%s error_type=%s",
            record.transformer_id,
            record.timestamp.isoformat(),
            type(exc).__name__,
        )

    def stop(self, timeout: float = 10) -> None:
        deadline = monotonic() + max(timeout, 0)
        with self._lock:
            self._accepting = False
        self._stopping.set()
        if self._worker is not None:
            self._worker.join(max(deadline - monotonic(), 0))
            if self._worker.is_alive():
                self._abort.set()
                with self._lock:
                    self._values["last_error"] = "SHUTDOWN_TIMEOUT"
                logger.warning("MQTT worker drain exceeded shutdown timeout")
                while True:
                    try:
                        self._queue.get_nowait()
                    except Empty:
                        break
                    self._queue.task_done()
                    with self._lock:
                        self._values["dropped_count"] += 1

        # paho loop_stop joins its network thread. Bound that join as well.
        def stop_network() -> None:
            try:
                self.client.disconnect()
                self.client.loop_stop()
            except Exception:
                with self._lock:
                    self._values["last_error"] = "DISCONNECT_FAILED"

        if self._started:
            closer = Thread(target=stop_network, name="mqtt-network-stop", daemon=True)
            closer.start()
            closer.join(max(deadline - monotonic(), 0))
        with self._lock:
            self._values["connected"] = False

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                **self._values,
                "queue_depth": self._queue.qsize(),
                "recent_rejections": [dict(entry) for entry in self._rejections],
            }
