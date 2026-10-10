import json,math,sys
from pathlib import Path
from datetime import datetime
import psycopg
p=Path('docs/hackathon_readiness/execution/evidence/h07/recovery');phase=sys.argv[1] if len(sys.argv)>1 else 'before';s=json.loads((p/f'spool-identities-{phase}.json').read_text(encoding='utf-8-sig'));m=json.load(open(p.parent/'soak-dfb1b1/manifest.json'));start=datetime.fromisoformat(m['source']['start_utc']);begin=datetime.fromisoformat(m['measurement_start_utc'] if 'measurement_start_utc' in m else '2026-10-09T19:36:35.718308+00:00');end=datetime.fromisoformat(m['end_utc']);first=math.ceil((begin-start).total_seconds()/5);last=math.floor((end-start).total_seconds()/5)
with psycopg.connect('host=127.0.0.1 port=55433 user=transformer password=transformer dbname=transformer') as d:
 rows=d.execute("SELECT t.transformer_id,t.payload_hash,t.timestamp,t.acquisition->>'sequence',r.committed_at,(SELECT count(*) FROM analytics a WHERE a.telemetry_id=t.id) FROM telemetry t JOIN ingestion_receipts r ON r.snapshot_id=t.payload_hash WHERE t.transformer_id=ANY(%s)",(m['assets'],)).fetchall()
 groups=[];identities=[]
 for asset in m['assets']:
  byseq={int(r[3]):r for r in rows if r[0]==asset};pending={int(round((datetime.fromisoformat(r['event_time'].replace('Z','+00:00'))-start).total_seconds()/5)):r for r in s['entries'] if r['asset']==asset};counts={}
  for seq in range(first,last+1):
   row=byseq.get(seq);entry=pending.get(seq)
   if row:status='COMMITTED_IN_WINDOW' if row[4]<=end else 'COMMITTED_AFTER_WINDOW'
   elif entry:status='DURABLE_PENDING_'+entry['state']
   else:status='UNACQUIRED_EXPECTED_SEQUENCE'
   counts[status]=counts.get(status,0)+1;identities.append(dict(asset=asset,sequence=seq,event_time=(start+__import__('datetime').timedelta(seconds=seq*5)).isoformat(),status=status,snapshot=row[1] if row else entry['snapshot'] if entry else None,in_spool=entry is not None))
  groups.append(dict(asset=asset,counts=counts,sql_total=len(byseq),spool_total=len(pending),sql_spool_overlap=len(set(byseq)&set(pending)),maximum_observed_sequence=max(set(byseq)|set(pending))))
 result=dict(observed_at=datetime.now().astimezone().isoformat(),expected_interval=dict(first_sequence=first,last_sequence=last,count=len(identities)),spool_counters=s['counters'],assets=groups,identities=identities,notes=['UNACQUIRED_EXPECTED_SEQUENCE is a scheduled sequence not represented in SQL or the durable spool. Snapshot hash unavailable: generator has no per-emission audit log. Poller missed-sequence counts and highest observed sequence corroborate overwriting between polls. Exact emission wall times remain unknown.','PUBACK is an attempt counter; retries mean it is not a unique observation count. SQL and spool overlap until receipts are checked.'])
(p/f'reconciliation-{phase}.json').write_text(json.dumps(result,indent=2,default=str))
print(json.dumps(dict(expected=len(identities),statuses={k:sum(a['counts'].get(k,0) for a in groups) for k in {k for a in groups for k in a['counts']}},sql=sum(a['sql_total'] for a in groups),overlap=sum(a['sql_spool_overlap'] for a in groups),spool=len(s['entries']))))
