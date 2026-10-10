"""Read-only receipt reconciliation plus consistent SQLite preservation snapshots."""
import argparse,json,sqlite3,subprocess,hashlib,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
import psycopg

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--backup-dir',required=True,type=Path)
args=parser.parse_args();args.backup_dir.mkdir(parents=True,exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
paths={'portfolio':'/spool/h07-dfb1b1/delivery.sqlite3','primary':'/spool/delivery.sqlite3',
       'bounded':'/spool/h07-b41b39/delivery.sqlite3',
       'bounded180':'/spool/h07-1ea791/delivery.sqlite3'}
result={'observed_at':datetime.now(timezone.utc).isoformat(),'spools':{}}
for label,path in paths.items():
    output=args.backup_dir/(stamp+'-'+label+'.sqlite3')
    assert not output.exists(),output
    remote='/tmp/'+output.name
    code='import sqlite3; s=sqlite3.connect('+repr(path)+'); d=sqlite3.connect('+repr(remote)+'); s.backup(d); assert d.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; d.close(); s.close()'
    subprocess.run(['docker','exec','-i','transformer-h06-20261009-modbus-bridge-1','python','-'],input=code,text=True,check=True)
    subprocess.run(['docker','cp','transformer-h06-20261009-modbus-bridge-1:'+remote,str(output)],check=True)
    with sqlite3.connect('file:'+output.as_posix()+'?mode=ro',uri=True) as d:
        d.row_factory=sqlite3.Row
        assert d.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        entries=[dict(r) for r in d.execute('SELECT * FROM entries')]
        result['spools'][label]={'backup':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'entries':entries,'counters':dict(d.execute('SELECT name,value FROM counters').fetchall())}
with psycopg.connect('host=127.0.0.1 port=55433 user=transformer password=transformer dbname=transformer') as db:
    for label,spool in result['spools'].items():
        hashes=[r['snapshot'] for r in spool['entries']]
        rows=db.execute("SELECT r.snapshot_id,r.payload_hash,r.accepted_payload_hash,r.status,r.committed_at,(SELECT count(*) FROM telemetry t WHERE t.payload_hash=r.snapshot_id),(SELECT count(*) FROM analytics a JOIN telemetry t ON t.id=a.telemetry_id WHERE t.payload_hash=r.snapshot_id) FROM ingestion_receipts r WHERE r.snapshot_id=ANY(%s)",(hashes,)).fetchall()
        receipts={r[0]:r for r in rows}
        for entry in spool['entries']:
            row=receipts.get(entry['snapshot'])
            if row:
                assert row[1]==row[2]==entry['hash'] and row[3]=='COMMITTED' and row[5]==row[6]==1,row
            entry['disposition']='COMMITTED_AWAITING_RECEIPT_CHECK' if row else 'DURABLE_PENDING'
        spool['pending_count']=len(hashes)
        spool['sql_committed_overlap']=len(receipts)
    attempts=json.loads(Path('docs/hackathon_readiness/execution/evidence/h07/recovery/primary-trace/trace-attempts.json').read_text())
    result['primary_trace']=[]
    for attempt in attempts:
        h=attempt['snapshot'];row=db.execute('SELECT r.status,r.payload_hash,r.accepted_payload_hash,(SELECT count(*) FROM telemetry t WHERE t.payload_hash=r.snapshot_id),(SELECT count(*) FROM analytics a JOIN telemetry t ON t.id=a.telemetry_id WHERE t.payload_hash=r.snapshot_id) FROM ingestion_receipts r WHERE r.snapshot_id=%s',(h,)).fetchone()
        result['primary_trace'].append(dict(attempt,receipt=row,still_pending=any(e['snapshot']==h for e in result['spools']['primary']['entries'])))
        if row:assert row[0]=='COMMITTED' and row[1]==row[2]==h and row[3]==row[4]==1
    result['database_bytes']=db.execute("SELECT pg_database_size('transformer')").fetchone()[0]
output=Path('docs/hackathon_readiness/execution/evidence/h07/20261010-diagnosis')/(stamp+'-reconciliation.json')
output.write_text(json.dumps(result,indent=2,default=str))
print(json.dumps({'evidence':str(output),'spools':{k:{x:v[x] for x in ['pending_count','sql_committed_overlap','counters']} for k,v in result['spools'].items()},'primary_trace':[(r['snapshot'],bool(r['receipt']),r['still_pending']) for r in result['primary_trace']]}))
