import json,statistics,urllib.request
from pathlib import Path
from datetime import datetime,timezone
import psycopg
p=Path('docs/hackathon_readiness/execution/evidence/h07/recovery');before=json.loads((p/'spool-identities-before.json').read_text(encoding='utf-8-sig'));after=json.loads((p/'spool-identities-after.json').read_text(encoding='utf-8-sig'));primary=json.loads((p/'primary-spool-after.json').read_text(encoding='utf-8-sig'));attempts=json.loads((p/'primary-trace/trace-attempts.json').read_text());hashes=[r['snapshot'] for r in before['entries']]+[r['snapshot'] for r in attempts];pending={r['snapshot']:r for r in after['entries']};pri={r['snapshot']:r for r in primary['entries']}
with psycopg.connect('host=127.0.0.1 port=55433 user=transformer password=transformer dbname=transformer') as db:
 rows=db.execute("SELECT r.snapshot_id,r.payload_hash,r.accepted_payload_hash,r.status,r.ingestion_outcome,r.transformer_id,r.event_time,(SELECT count(*) FROM telemetry t WHERE t.payload_hash=r.snapshot_id),(SELECT count(*) FROM analytics a JOIN telemetry t ON t.id=a.telemetry_id WHERE t.payload_hash=r.snapshot_id) FROM ingestion_receipts r WHERE r.snapshot_id=ANY(%s)",(hashes,)).fetchall();sql={r[0]:r for r in rows};dispositions=[]
 for entry in before['entries']:
  h=entry['snapshot'];row=sql.get(h)
  if row:
   assert row[1]==row[2]==h and row[3]=='COMMITTED' and row[7]==row[8]==1,(h,row)
  assert row or h in pending,h
  dispositions.append(dict(snapshot=h,asset=entry['asset'],status='COMMITTED_STILL_AWAITING_SPOOL_CHECK' if row and h in pending else 'COMMITTED_REMOVED_AFTER_RECEIPT' if row else 'PENDING',telemetry_count=row[7] if row else 0,analytics_count=row[8] if row else 0,spool=pending.get(h)))
 checkpoints=db.execute("SELECT c.transformer_id,(c.checkpoint->>'observation_count')::int,(SELECT count(*) FROM analytics a WHERE a.transformer_id=c.transformer_id),c.checkpoint->'state'->'maintenance_persistence'->'payload'->>'trip_latched' FROM ml_checkpoints c WHERE c.transformer_id LIKE 'H07-dfb1b1-%'").fetchall()
 assert all(r[1]==r[2] for r in checkpoints),checkpoints
 traced=[]
 for a in attempts:
  h=a['snapshot'];row=sql.get(h);entry=pri.get(h)
  try:
   resp=json.load(urllib.request.urlopen('http://127.0.0.1:8001/api/v1/ingestion/receipts/'+h,timeout=2));status=200
  except urllib.error.HTTPError as e:status=e.code;resp=None
  traced.append(dict(**a,current_http_status=status,current_receipt=resp,sql=row,spool=entry,status='COMMITTED' if row else 'PENDING_IN_SPOOL' if entry else 'NOT_IN_SQL_OR_SPOOL'))
 def pct(vals):
  vals=sorted(vals);return dict(n=len(vals),p50=vals[int((len(vals)-1)*.5)],p95=vals[int((len(vals)-1)*.95)],maximum=max(vals)) if vals else None
 log=[json.loads(x) for x in (p/'recovery-measurements-attempt2.jsonl').read_text(encoding='utf-8-sig').splitlines() if x.startswith('{')];small=[json.loads(x) for x in (p/'three-asset-measurements.jsonl').read_text(encoding='utf-8-sig').splitlines() if x.startswith('{')]
 pub=[e for x in log for e in x.get('publish',[])];checks=[e for x in log for e in x.get('receipts',[])];first_ack={};first_receipt={}
 for x in pub:first_ack.setdefault(x['snapshot'],x['wall'])
 for x in checks:
  if x['outcome']=='COMMITTED':first_receipt.setdefault(x['snapshot'],x['wall'])
 latency=[first_receipt[h]-t for h,t in first_ack.items() if h in first_receipt]
 result=dict(at=datetime.now(timezone.utc).isoformat(),before_counters=before['counters'],after_counters=after['counters'],before_pending=len(before['entries']),after_pending=len(after['entries']),initial_identity_dispositions=dispositions,primary_trace=traced,checkpoints=checkpoints,recovery_duration_seconds=log[-1]['elapsed'],recovery_confirmed_delta=log[-1]['counters']['committed']-before['counters']['committed'],publish_latency_seconds=pct([x['seconds'] for x in pub]),receipt_lookup_seconds=pct([x['seconds'] for x in checks]),observed_puback_to_receipt_confirmation_seconds=pct(latency),small_test_final=small[-1],api_unit_tests='6 passed; real SQL evidence is this recovery, not the mocked unit harness',remaining_scope='No new soak or generated replay; original failed primary hashes were not captured and cannot be retroactively identified.')
 (p/'recovery-summary.json').write_text(json.dumps(result,indent=2,default=str));print(json.dumps({k:v for k,v in result.items() if k not in ('initial_identity_dispositions','primary_trace','checkpoints','small_test_final')}));print('primary status',[(r['snapshot'][:12],r['status']) for r in traced]);print('small final',small[-1]);print('retained pending SQL overlap',sum(x['status']=='COMMITTED_STILL_AWAITING_SPOOL_CHECK' for x in dispositions))
