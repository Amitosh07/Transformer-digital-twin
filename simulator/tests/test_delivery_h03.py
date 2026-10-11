from datetime import datetime, timezone
import httpx
import pytest
from simulator.generator import SyntheticGenerator
from simulator.schema import identify
from simulator.spool import DurableSpool, SpoolFull
from simulator.modbus_bridge import ReceiptClient, DeliveryWorker
from simulator.streaming import MqttPublisher
from ml.pipeline.identity import parse_record_json, payload_hash

START=datetime(2026,10,9,tzinfo=timezone.utc)


class Publisher:
    def __init__(self,fail=False): self.payloads=[]; self.fail=fail
    def publish_payload(self,payload):
        self.payloads.append(payload)
        if self.fail: raise ConnectionError("broker unavailable")
        return {"broker_acknowledged":True,"committed":False}


def committed_receipt(entry):
    return {"schema_version":"1.1.0","receipt_status":"COMMITTED","snapshot_id":entry["snapshot"],
        "payload_hash":entry["hash"],"transformer_id":entry["asset"],"timestamp":entry["event_time"],
        "received_at":"2026-10-09T01:00:00Z","committed_at":"2026-10-09T01:00:01Z",
        "accepted_snapshot_id":entry["snapshot"],"accepted_payload_hash":entry["hash"],
        "ingestion_outcome":"ACCEPTED","analytics_status":"UNAVAILABLE","state_coverage_loss":True}


def test_spool_restart_puback_not_commit_and_real_receipt_shape(tmp_path):
    spool=DurableSpool(tmp_path)
    record=SyntheticGenerator().generate(START,1)[0]
    assert spool.enqueue(record) == "QUEUED"
    assert spool.enqueue(record) == "EXACT_RETRY"
    entry=spool.pending()[0]
    replies=[httpx.Response(404,json={"error":{"code":"RECEIPT_NOT_COMMITTED"}})]
    client=httpx.Client(transport=httpx.MockTransport(lambda request: replies[0]))
    receipts=ReceiptClient("http://backend",client=client)
    publisher=Publisher()
    worker=DeliveryWorker(spool,publisher,receipts)
    worker.flush()
    assert spool.usage()[0] == 1
    assert spool.counters().get("committed",0) == 0
    row=dict(spool.db.execute("SELECT * FROM entries").fetchone())
    assert row["pubacks"] == 1 and row["attempts"] == 1
    assert spool.counters()["broker_pubacks"] == 1
    spool.close()
    spool=DurableSpool(tmp_path)
    row=dict(spool.db.execute("SELECT * FROM entries").fetchone())
    assert row["hash"] == payload_hash(parse_record_json(row["payload"]))
    assert row["attempts"] == 1
    with spool.db: spool.db.execute("UPDATE entries SET next_attempt=0")
    replies[0]=httpx.Response(200,json=committed_receipt(entry))
    DeliveryWorker(spool,publisher,receipts).flush()
    assert spool.usage()[0] == 0
    assert spool.counters()["committed"] == 1
    assert len(publisher.payloads) == 1  # restored receipt checked before republish
    assert spool.enqueue(record) == "EXACT_RETRY"
    assert spool.usage()[0] == 0
    assert spool.counters()["committed"] == 1
    spool.close(); client.close()


@pytest.mark.parametrize("response", [httpx.Response(500),httpx.Response(404),httpx.Response(200,json={"receipt_status":"COMMITTED","committed_at":None})])
def test_no_false_commit(response,tmp_path):
    spool=DurableSpool(tmp_path)
    spool.enqueue(SyntheticGenerator().generate(START,1)[0])
    with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
        DeliveryWorker(spool,Publisher(),ReceiptClient("http://backend",client=client)).flush()
    assert spool.counters().get("committed",0) == 0
    assert spool.usage()[0] == 1
    spool.close()


def test_http_connection_failure_and_broker_failure(tmp_path):
    spool=DurableSpool(tmp_path)
    spool.enqueue(SyntheticGenerator().generate(START,1)[0])
    def failed(request): raise httpx.ConnectError("unavailable",request=request)
    with httpx.Client(transport=httpx.MockTransport(failed)) as client:
        DeliveryWorker(spool,Publisher(fail=True),ReceiptClient("http://backend",client=client)).flush()
    row=dict(spool.db.execute("SELECT * FROM entries").fetchone())
    assert row["reason"] == "BROKER_FAILURE"
    assert row["pubacks"] == 0
    assert spool.counters().get("committed",0) == 0
    spool.close()


def test_changed_payload_quarantine_overflow_and_order(tmp_path):
    spool=DurableSpool(tmp_path,max_records=2)
    records=SyntheticGenerator(interval_s=5).generate(START,3)
    spool.enqueue(records[0]); spool.enqueue(records[1])
    assert len(spool.pending()) == 1
    with pytest.raises(SpoolFull): spool.enqueue(records[2])
    changed=records[0].model_copy(deep=True)
    changed.oil_temp_trip=1
    identify(changed)
    assert spool.enqueue(changed) == "CONFLICT"
    assert spool.pending() == []  # newer asset record cannot overtake quarantine
    original=dict(spool.db.execute("SELECT * FROM entries ORDER BY event_time LIMIT 1").fetchone())
    assert parse_record_json(original["payload"])["oil_temp_trip"] == 0
    assert original["reason"] == "LOCAL_SEMANTIC_CONFLICT"
    assert spool.counters()["backpressure"] == 1
    spool.close()


def test_mismatched_committed_receipt_quarantined(tmp_path):
    spool=DurableSpool(tmp_path)
    spool.enqueue(SyntheticGenerator().generate(START,1)[0])
    entry=spool.pending()[0]
    receipt=committed_receipt(entry)
    receipt["accepted_payload_hash"]="f"*64
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=receipt))) as client:
        DeliveryWorker(spool,Publisher(),ReceiptClient("http://backend",client=client)).flush()
    assert spool.pending() == []
    assert spool.usage()[0] == 1
    assert spool.counters()["conflicted"] == 1
    assert spool.counters().get("committed",0) == 0
    spool.close()


def test_unique_mqtt_clients_and_no_unconfirmed_publish():
    a,b=MqttPublisher(timeout=.1),MqttPublisher(timeout=.1)
    assert a.client_id != b.client_id
    assert not a._connected and not b._connected
    with pytest.raises(ValueError,match="QoS 1"): MqttPublisher(qos=2)


def test_spool_has_one_owner_and_bounded_reservation(tmp_path):
    spool=DurableSpool(tmp_path,max_bytes=8192)
    assert spool.can_acquire()
    with pytest.raises(RuntimeError,match="owner"):
        DurableSpool(tmp_path)
    spool.enqueue(SyntheticGenerator().generate(START,1)[0])
    assert not spool.can_acquire()
    spool.close()
    reopened=DurableSpool(tmp_path,max_bytes=8192)
    assert (tmp_path/"owner.lock").stat().st_size == 1
    reopened.close()
