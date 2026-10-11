"""Read-only FC04 polling, durable QoS1 publish and H02 commit receipt checks."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from threading import Event, Thread, Lock
import httpx
from pymodbus.client import ModbusTcpClient
from ml.pipeline.identity import parse_record_json, utc
from .register_map import load_map, decode, VERSION
from .spool import DurableSpool, SpoolFull
from .streaming import MqttPublisher


class SnapshotError(RuntimeError):
    pass


class SnapshotPoller:
    def __init__(self, asset, gateway_id, timeout=2, retries=3, client=None):
        self.asset, self.gateway_id = asset, gateway_id
        if type(asset["unit_id"]) is not int or not 1 <= asset["unit_id"] <= 247 or not asset["transformer_id"]:
            raise ValueError("invalid asset/unit ID")
        if not math.isfinite(timeout) or timeout <= 0 or type(retries) is not int or not 1 <= retries <= 10:
            raise ValueError("bounded timeout/retries required")
        self.retries = retries
        self.spec = load_map()
        self.client = client or ModbusTcpClient(asset["host"], port=asset.get("port", 1502), timeout=timeout, retries=0)
        self.status = {"connected": False, "last_success_at": None, "failures": 0, "torn": 0, "reconnects": 0, "reason": None, "missed_snapshots": 0}
        self.last_sequence = None

    def _read(self, address, count):
        response = self.client.read_input_registers(address, count=count, slave=self.asset["unit_id"])
        if response.isError() or not hasattr(response, "registers") or len(response.registers) != count:
            raise SnapshotError("invalid FC04 response")
        return response.registers

    def poll(self):
        for attempt in range(self.retries):
            if attempt:
                time.sleep(min(.05 * 2 ** (attempt-1), .5))
            try:
                if not self.status["connected"]:
                    if not self.client.connect():
                        raise ConnectionError("Modbus disconnected")
                    self.status["reconnects"] += 1
                    self.status["connected"] = True
                before = self._read(2, 2)
                registers = []
                for address in range(0, self.spec["register_count"], 100):
                    registers.extend(self._read(address, min(100, self.spec["register_count"]-address)))
                after = self._read(2, 2)
                if before != after or before != registers[2:4]:
                    self.status["torn"] += 1
                    raise SnapshotError("TORN_SNAPSHOT")
                record = decode(registers, transformer_id=self.asset["transformer_id"], unit_id=self.asset["unit_id"],
                                gateway_id=self.gateway_id, expected_interval_seconds=self.asset.get("expected_interval_seconds", 5))
                sequence = record.acquisition["sequence"]
                if self.last_sequence is not None:
                    if sequence < self.last_sequence:
                        raise SnapshotError("SOURCE_SEQUENCE_REINITIALIZED; use a deliberate new source run")
                    self.status["missed_snapshots"] += max(0, sequence-self.last_sequence-1)
                self.last_sequence = sequence
                self.status["last_success_at"] = datetime.now(timezone.utc).isoformat()
                self.status["reason"] = None
                return record
            except (Exception,) as exc:
                self.status["failures"] += 1
                self.status["reason"] = str(exc)[:128]
                self.status["connected"] = False
                self.client.close()
        raise SnapshotError(self.status["reason"] or "bounded polling failed")

    def close(self):
        self.client.close()


class ReceiptClient:
    def __init__(self, base_url, timeout=3, client=None):
        self.last_receipt = None
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout)

    def outcome(self, entry):
        try:
            response = self.client.get(f"{self.base_url}/api/v1/ingestion/receipts/{entry['snapshot']}")
            if response.status_code == 404:
                return "NOT_YET_COMMITTED"
            if response.status_code != 200:
                return "TEMPORARY_RECEIPT_FAILURE"
            receipt = response.json()
            if receipt.get("receipt_status") == "CONFLICT":
                return "CONFLICT"
            if receipt.get("receipt_status") != "COMMITTED" or not receipt.get("committed_at"):
                return "INVALID_RECEIPT"
            expected = entry["hash"]
            if (receipt.get("schema_version") != "1.1.0" or receipt.get("snapshot_id") != entry["snapshot"] or
                receipt.get("payload_hash") != expected or receipt.get("accepted_payload_hash") != expected or
                receipt.get("accepted_snapshot_id") != entry["snapshot"] or receipt.get("transformer_id") != entry["asset"] or
                utc(receipt["timestamp"]) != entry["event_time"]):
                return "CONFLICT"
            if (receipt.get("ingestion_outcome") not in ("ACCEPTED", "EXACT_RETRY") or
                receipt.get("analytics_status") not in ("AVAILABLE", "INSUFFICIENT_DATA", "UNAVAILABLE") or
                type(receipt.get("state_coverage_loss")) is not bool):
                return "INVALID_RECEIPT"
            utc(receipt["received_at"])
            utc(receipt["committed_at"])
            self.last_receipt = receipt
            return "COMMITTED"
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return "TEMPORARY_RECEIPT_FAILURE"

    def close(self):
        self.client.close()


class DeliveryWorker:
    def __init__(self, spool, publisher, receipts, backoff=1, max_backoff=30, audit=None):
        if not 0 < backoff <= max_backoff <= 3600:
            raise ValueError("invalid bounded retry backoff")
        self.spool, self.publisher, self.receipts = spool, publisher, receipts
        self.backoff, self.max_backoff = backoff, max_backoff
        self.audit = audit

    def flush(self, stop=None):
        for entry in self.spool.pending():
            if stop is not None and stop.is_set():
                break
            self.spool.attempt(entry["snapshot"])
            delay = min(self.max_backoff, self.backoff * 2 ** min(entry["attempts"], 20))
            # Recovery may find an already committed row before republishing.
            outcome = self.receipts.outcome(entry)
            if outcome == "COMMITTED":
                self.spool.committed(entry["snapshot"])
                if self.audit:
                    self.audit("RECEIPT_CONFIRMED", entry, getattr(self.receipts,"last_receipt",None))
                continue
            if outcome == "CONFLICT":
                self.spool.outcome(entry["snapshot"], outcome, quarantine=True)
                continue
            try:
                ack = self.publisher.publish_payload(parse_record_json(entry["payload"]))
                if not ack or not ack.get("broker_acknowledged"):
                    raise ConnectionError("missing PUBACK")
            except (ConnectionError, TimeoutError, OSError, RuntimeError):
                self.spool.outcome(entry["snapshot"], "BROKER_FAILURE", retry_seconds=delay)
                continue
            self.spool.record_counter("broker_pubacks")
            if self.audit:
                self.audit("PUBACK", entry, None)
            outcome = self.receipts.outcome(entry)
            if outcome == "COMMITTED":
                self.spool.committed(entry["snapshot"])
                if self.audit:
                    self.audit("RECEIPT_CONFIRMED", entry, getattr(self.receipts,"last_receipt",None))
            else:
                self.spool.outcome(entry["snapshot"], outcome, puback=True,
                                   quarantine=outcome == "CONFLICT",
                                   # A healthy 404 is receipt visibility latency,
                                   # not a failed broker. Keep checking pending
                                   # FIFO heads at the base interval; exponential
                                   # delay still applies to transport failures.
                                   retry_seconds=self.backoff if outcome == "NOT_YET_COMMITTED" else delay)


def run_bridge(config_file):
    path = Path(config_file)
    from .fleet import load_runtime_config
    config = load_runtime_config(path, 'bridge')
    if config["map_version"] != VERSION:
        raise ValueError("unsupported bridge map version")
    if not config["gateway_id"] or len(config["gateway_id"]) > 128:
        raise ValueError("bounded stable gateway ID required")
    if config["spool"]["max_bytes"] < 8192:
        raise ValueError("bridge spool requires at least one reserved 8192-byte snapshot")
    mappings, assets = set(), set()
    for asset in config["assets"]:
        key = (asset["host"], asset.get("port", 1502), asset["unit_id"])
        if key in mappings or asset["transformer_id"] in assets:
            raise ValueError("conflicting asset/unit mapping")
        mappings.add(key)
        assets.add(asset["transformer_id"])
    interval = config.get("poll_interval_seconds", 5)
    if not math.isfinite(interval) or interval <= 0 or not mappings:
        raise ValueError("positive cadence and assets required")
    spool_config = dict(config["spool"])
    directory = Path(spool_config.pop("directory"))
    spool = DurableSpool(directory if directory.is_absolute() else path.parent / directory, **spool_config)
    mqtt_config = dict(config["mqtt"])
    # Even a configured display prefix cannot collide with another bridge.
    if mqtt_config.get("client_id"):
        import uuid
        mqtt_config["client_id"] += "-" + uuid.uuid4().hex
    publisher = MqttPublisher(**mqtt_config, timeout=config.get("timeout_seconds", 2))
    receipts = ReceiptClient(config["receipt_base_url"], timeout=config.get("timeout_seconds", 2))
    log_lock = Lock()
    def report(value):
        with log_lock:
            print(json.dumps(value), flush=True)
    def audit(stage, entry, receipt):
        report({"delivery": {"stage": stage, "snapshot": entry['snapshot'],
            "asset": entry['asset'], "event_time": entry['event_time'],
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "receipt_committed_at": receipt.get('committed_at') if receipt else None}})
    worker = DeliveryWorker(spool, publisher, receipts, config.get("backoff_seconds", 1),
                            config.get("max_backoff_seconds", 30),
                            audit if config.get('audit_delivery') else None)
    pollers = [SnapshotPoller(a, config["gateway_id"], config.get("timeout_seconds", 2), config.get("snapshot_retries", 3)) for a in config["assets"]]
    stopped = Event()
    def deliver():
        try:
            while not stopped.is_set():
                worker.flush(stopped)
                stopped.wait(.1)
        except BaseException:
            stopped.set()
            raise
    delivery = Thread(target=deliver, name="receipt-delivery", daemon=True)
    import signal
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    delivery.start()
    try:
        while not stopped.is_set():
            for poller in pollers:
                if not spool.can_acquire():
                    spool.record_counter("backpressure")
                    break
                try:
                    record = poller.poll()
                    outcome = spool.enqueue(record)
                    if outcome == 'QUEUED' and config.get('audit_delivery'):
                        report({"acquired": {"asset": record.transformer_id,
                            "snapshot": record.acquisition['snapshot_id'],
                            "sequence": record.acquisition['sequence'],
                            "event_time": record.timestamp.isoformat(),
                            "observed_at": datetime.now(timezone.utc).isoformat()}})
                except SpoolFull:
                    # Keep delivering pending rows while acquisition is paused.
                    break
                except SnapshotError:
                    pass
            report({"gateway_id": config["gateway_id"], "gateway_time": datetime.now(timezone.utc).isoformat(),
                              "counters": spool.counters(), "spool_usage": spool.usage(), "assets": {p.asset["transformer_id"]: p.status for p in pollers}})
            stopped.wait(interval)
    finally:
        stopped.set()
        delivery.join()
        for poller in pollers:
            poller.close()
        publisher.disconnect()
        receipts.close()
        spool.close()
