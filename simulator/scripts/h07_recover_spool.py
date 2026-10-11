"""Recover existing H07 spool through unchanged receipt-aware DeliveryWorker; no acquisition."""
import json,time,os
from pathlib import Path
from simulator.spool import DurableSpool
from simulator.modbus_bridge import DeliveryWorker,ReceiptClient
from simulator.streaming import MqttPublisher
config=json.loads(Path(os.environ.get('H07_RECOVERY_CONFIG','/config/h07-dfb1b1/bridge.json')).read_text())
spool=DurableSpool(**config['spool']);publisher=MqttPublisher(**config['mqtt'],timeout=2);receipts=ReceiptClient(config['receipt_base_url'],timeout=2)
worker=DeliveryWorker(spool,publisher,receipts,1,30);original=spool.pending
stages=[];checks=[];begin=time.monotonic(); duration=int(os.environ.get("H07_RECOVERY_SECONDS","30")); selected={a["transformer_id"] for a in (config["assets"] if os.environ.get("H07_RECOVERY_ALL") else config["assets"][:3])}
publish=publisher.publish_payload;outcome=receipts.outcome

def timed_publish(payload):
 start=time.monotonic();result=publish(payload);stages.append(dict(stage='publish_puback',seconds=time.monotonic()-start,snapshot=payload['acquisition']['snapshot_id'],wall=time.time(),ack=result));return result

def timed_receipt(entry):
 start=time.monotonic();result=outcome(entry);checks.append(dict(stage='receipt',seconds=time.monotonic()-start,snapshot=entry['snapshot'],wall=time.time(),outcome=result));return result
publisher.publish_payload=timed_publish;receipts.outcome=timed_receipt
try:
 while time.monotonic()-begin<duration and spool.usage()[0]:
  elapsed=time.monotonic()-begin
  # First 45 seconds measures at most three existing fictional asset heads;
  # afterward use the unchanged worker's bounded default of 25.
  spool.pending=lambda:[e for e in original(limit=25) if e["asset"] in selected][:1]
  t=time.monotonic();before=spool.counters();worker.flush()
  print(json.dumps(dict(elapsed=time.monotonic()-begin,flush_seconds=time.monotonic()-t,counters=spool.counters(),usage=spool.usage(),phase='all_assets_one_head' if os.environ.get('H07_RECOVERY_ALL') else 'fixed_three_assets_one_head',publish=stages,receipts=checks)),flush=True)
  stages.clear();checks.clear();time.sleep(.2)
finally:
 print(json.dumps(dict(final=True,counters=spool.counters(),usage=spool.usage(),elapsed=time.monotonic()-begin)),flush=True)
 publisher.disconnect();receipts.close();spool.close()
