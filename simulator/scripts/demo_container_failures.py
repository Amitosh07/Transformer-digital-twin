"""Real disposable H06 Compose failure gates; never operator infrastructure."""
import argparse,atexit,copy,json,os,subprocess,time,urllib.error
from uuid import uuid4
from pathlib import Path
import psycopg
from ml.pipeline.identity import payload_hash
from demo_runtime import request,register,ROOT
from demo_oracles import rows

PROJECT='transformer-h06-20261009'
DSN='host=127.0.0.1 port=55433 user=transformer password=transformer dbname=transformer'
OUT=ROOT/'docs/hackathon_readiness/execution/evidence/h06/container/failures.json'

def compose(*args):
    return subprocess.check_output(['docker','compose',*args],cwd=ROOT,text=True,timeout=120)

def spool():
    code="import sqlite3,json;d=sqlite3.connect('/spool/delivery.sqlite3');print(json.dumps(dict(counters=dict(d.execute('select * from counters')),entries=d.execute('select snapshot,hash,pubacks,reason from entries order by event_time').fetchall())))"
    return json.loads(compose('exec','-T','modbus-bridge','python','-c',code).splitlines()[-1])

def ready():
    for _ in range(60):
        try:request('/health/ready');return
        except OSError:time.sleep(1)
    raise RuntimeError('Backend readiness timeout')

def asset_state(asset):
    with psycopg.connect(DSN) as db:
        tables={table:db.execute(f'SELECT to_jsonb(t) FROM {table} t WHERE transformer_id=%s ORDER BY id',(asset,)).fetchall() for table in ('telemetry','analytics','alerts','maintenance_records')}
        checkpoint=db.execute('SELECT checkpoint FROM ml_checkpoints WHERE transformer_id=%s',(asset,)).fetchone()
    return dict(tables=tables,checkpoint=checkpoint)

def expect_http(code,body):
    try:request('/api/v1/telemetry',body)
    except urllib.error.HTTPError as exc:
        assert exc.code==code,(exc.code,exc.read());return
    raise AssertionError(f'Expected HTTP {code}')



def strict_recovery(config):
    """Identity-scoped real broker gate; keep the ongoing source/spool untouched."""
    from datetime import datetime, timezone
    from ml.pipeline.identity import parse_record_json
    run=uuid4().hex[:8]
    asset='H06-STRICT-'+run
    helper=PROJECT+'-strict-'+run
    directory='/spool/strict-'+run
    output=OUT.with_name('strict-recovery-'+run+'.json')
    evidence={'run':run,'asset':asset,'completed':False,'configuration':config,
              'historical_diagnostic_limit':'The prior failed counter assertion did not save identities or counter snapshots; its exact increment cannot be retrospectively attributed.'}
    wait_seconds=config['max_backoff_seconds']+2*config['timeout_seconds']+2*config['poll_interval_seconds']+10
    def stamp():return datetime.now(timezone.utc).isoformat()
    def persist():output.write_text(json.dumps(evidence,indent=2,default=str),encoding='utf-8')
    def sql_rows(digest):
        with psycopg.connect(DSN) as db:
            return db.execute('SELECT t.id,count(a.id) FROM telemetry t LEFT JOIN analytics a ON a.telemetry_id=t.id WHERE t.payload_hash=%s GROUP BY t.id',(digest,)).fetchall()
    def receipt(snapshot):
        import urllib.request
        try:
            with urllib.request.urlopen('http://127.0.0.1:8001/api/v1/ingestion/receipts/'+snapshot,timeout=3) as response:
                return dict(status=response.status,body=json.load(response))
        except urllib.error.HTTPError as exc:return dict(status=exc.code)
    code=r"""
import json,sys,socket,time
from simulator.spool import DurableSpool
from simulator.modbus_bridge import DeliveryWorker,ReceiptClient
from simulator.streaming import MqttPublisher
from ml.pipeline.identity import parse_record_json
v=json.load(sys.stdin);c=v['config']
s=DurableSpool(v['directory'],max_records=20,max_bytes=131072)
p=MqttPublisher(host='mqtt',port=1883,timeout=c['timeout_seconds'])
r=ReceiptClient('http://backend:8000',timeout=c['timeout_seconds'])
w=DeliveryWorker(s,p,r,c['backoff_seconds'],c['max_backoff_seconds'])
try:
 if v['op']=='enqueue':s.enqueue(v['record'])
 elif v['op']=='flush':w.flush()
 elif v['op']=='republish':p.publish_payload(v['record'])
 elif v['op']!='status':raise ValueError(v['op'])
 try:
  with socket.create_connection(('mqtt',1883),timeout=c['timeout_seconds']):reachable=True
 except OSError:reachable=False
 entries=[dict(row) for row in s.db.execute('SELECT snapshot,hash,asset,event_time,state,attempts,pubacks,reason,next_attempt FROM entries ORDER BY event_time')]
 print(json.dumps(dict(counters=s.counters(),entries=entries,broker_reachable=reachable,publisher_connected=p._connected,observed_at=time.time())),flush=True)
finally:p.disconnect();r.close();s.close()
"""
    def worker(op,record=None):
        result=subprocess.run(['docker','exec','-i',helper,'python','-c',code],
            input=json.dumps(dict(op=op,record=record,config=config,directory=directory)),
            cwd=ROOT,text=True,capture_output=True,timeout=20,check=True)
        return json.loads(result.stdout.splitlines()[-1])
    def broker_running():
        container=compose('ps','-a','-q','mqtt').strip()
        return json.loads(subprocess.check_output(['docker','inspect','--format','{{.State.Running}}',container],text=True,timeout=10))
    try:
        ready();register(asset)
        # Reuse an actual already-committed semantic identity solely for diagnosis.
        with psycopg.connect(DSN) as db:
            old=db.execute("SELECT t.semantic_payload,t.payload_hash,r.committed_at FROM telemetry t JOIN ingestion_receipts r ON r.telemetry_id=t.id WHERE t.transformer_id='H06-SIM-05' AND r.status='COMMITTED' ORDER BY t.timestamp DESC LIMIT 1").fetchone()
        old_record=json.loads(old[0]);old_record['schema_version']='1.1.0'
        old_record['acquisition']['snapshot_id']=old[1]
        main_id=compose('ps','-q','modbus-bridge').strip()
        info=json.loads(subprocess.check_output(['docker','inspect',main_id],text=True,timeout=10))[0]
        network=next(iter(info['NetworkSettings']['Networks']))
        subprocess.check_output(['docker','run','-d','--name',helper,'--network',network,'--volumes-from',main_id,'--entrypoint','python',info['Image'],'-c','import time;time.sleep(600)'],text=True,timeout=30)
        evidence['preoutage']=dict(wall_time=stamp(),queued=worker('enqueue',old_record),receipt=receipt(old[1]),sql_committed_at=old[2])
        compose('stop','mqtt')
        assert not broker_running()
        offline=worker('status');assert not offline['broker_reachable']
        evidence['outage_established']=dict(wall_time=stamp(),broker_running=False,status=offline)
        diagnostic=worker('flush')
        assert not diagnostic['broker_reachable'] and diagnostic['counters'].get('committed',0)==1
        assert diagnostic['counters'].get('broker_pubacks',0)==0 and not diagnostic['entries']
        assert receipt(old[1])['body']['receipt_status']=='COMMITTED'
        evidence['diagnosis']=dict(before=offline,after=diagnostic,snapshot_id=old[1],matching_receipt=receipt(old[1]),
            conclusion='Receipt-first confirmation legitimately increments delivery committed count while MQTT is offline; this identity committed in SQL before the outage, with no new publication or new SQL row.')
        # Creation wall time is after the observable outage; event time stays explicit UTC.
        record=rows(asset,[(0,10,0)])[0];snapshot=record['acquisition']['snapshot_id']
        assert receipt(snapshot)['status']==404 and not sql_rows(snapshot)
        pending=worker('enqueue',record);failed=worker('flush')
        baseline=diagnostic['counters'].get('committed',0)
        assert not failed['broker_reachable'] and not failed['publisher_connected']
        assert failed['entries'][0]['reason']=='BROKER_FAILURE' and failed['counters'].get('committed',0)==baseline
        evidence['postoutage_identity']=dict(created_wall_time=stamp(),record=record,expected_hash=payload_hash(record),pending=pending,disconnected=failed,receipt=receipt(snapshot))
        assert snapshot==payload_hash(record)
        observe_seconds=max(10,3*config['poll_interval_seconds']+2*config['timeout_seconds'])
        deadline=time.monotonic()+observe_seconds;observations=[]
        while True:
            observed=worker('flush')
            assert not broker_running() and not observed['broker_reachable']
            assert observed['counters'].get('committed',0)==baseline
            assert observed['counters'].get('broker_pubacks',0)==0
            assert observed['entries'][0]['snapshot']==snapshot and observed['entries'][0]['hash']==snapshot
            assert receipt(snapshot)['status']==404 and not sql_rows(snapshot)
            observations.append(observed)
            if time.monotonic()>=deadline:break
            time.sleep(config['poll_interval_seconds'])
        evidence['offline_observation']=dict(seconds=observe_seconds,observations=observations,no_committed_receipt=True,no_sql_rows=True,committed_counter_unchanged=True)
        subprocess.run(['docker','restart',helper],check=True,timeout=30,capture_output=True)
        restored=worker('status')
        assert restored['entries']==observations[-1]['entries'] and restored['counters']==observations[-1]['counters']
        evidence['durable_restart']=restored
        compose('start','mqtt');deadline=time.monotonic()+wait_seconds
        while True:
            observed=worker('flush');committed=receipt(snapshot)
            if committed['status']==200 and not observed['entries']:break
            if time.monotonic()>=deadline:raise AssertionError('Strict recovery deadline exceeded')
            time.sleep(config['poll_interval_seconds'])
        r=committed['body']
        assert r['receipt_status']=='COMMITTED' and r['payload_hash']==snapshot and r['accepted_payload_hash']==snapshot
        assert observed['counters']['committed']==baseline+1
        matches=sql_rows(snapshot);assert len(matches)==1 and matches[0][1]==1
        state=asset_state(asset)
        assert state['checkpoint'][0]['observation_count']==1
        assert request('/api/v1/telemetry',record)['duplicate'] and asset_state(asset)==state
        # A real new MQTT connection republishes the exact accepted identity.
        compose('pause','modbus-bridge')
        try:
            # No other owned producer can inflate this diagnostics counter.
            deadline=time.monotonic()+wait_seconds;stable_since=None;previous=None
            while True:
                status=request('/api/v1/ingest/mqtt/status')
                marker=(status['received_count'],status['duplicate_count'],status['committed_count'])
                if status['queue_depth']==0 and marker==previous:
                    if stable_since is None:stable_since=time.monotonic()
                    if time.monotonic()-stable_since>=2*config['poll_interval_seconds']:break
                else:stable_since=None
                previous=marker
                if time.monotonic()>=deadline:raise AssertionError('MQTT pre-retry queue did not settle')
                time.sleep(1)
            mqtt_before=status['duplicate_count']
            republished=worker('republish',record)
            deadline=time.monotonic()+wait_seconds
            while request('/api/v1/ingest/mqtt/status')['duplicate_count']<=mqtt_before:
                if time.monotonic()>=deadline:raise AssertionError('MQTT exact retry not observed')
                time.sleep(1)
        finally:
            compose('unpause','modbus-bridge')
        assert asset_state(asset)==state and sql_rows(snapshot)==matches
        assert worker('status')['counters']['committed']==baseline+1
        evidence['recovery']=dict(deadline_seconds=wait_seconds,status=observed,receipt=r,sql_rows=matches,checkpoint_observations=1,
            http_exact_retry=True,mqtt_reconnect_exact_retry=True,telemetry_analytics_alerts_maintenance_checkpoint_unchanged=True,republish=republished)
        evidence['completed']=True
        print('PASS strict real broker outage/recovery, receipt-first diagnosis, durable restart and exact HTTP/MQTT retry:',snapshot,flush=True)
    except BaseException as exc:
        evidence['failure']=dict(type=type(exc).__name__,detail=str(exc));raise
    finally:
        persist()
        compose('start','mqtt')
        if helper:
            subprocess.run(['docker','stop',helper],capture_output=True,timeout=30)
        # Retain the stopped helper and its bounded spool for diagnostics; do not delete anything.
        print('Evidence:',output,flush=True)

if __name__=='__main__':
    if os.environ.get('COMPOSE_PROJECT_NAME')!=PROJECT:
        raise SystemExit('Requires explicitly selected disposable transformer-h06-20261009 project')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recovery-only',action='store_true',help='Resume only broker/database/spool recovery gates')
    args=parser.parse_args()
    if args.recovery_only:
        OUT=OUT.with_name('recovery-continuation.json')
    config=json.loads((ROOT/'simulator/config/hackathon-bridge.yaml').read_text(encoding='utf-8'))
    if args.recovery_only:
        strict_recovery(config)
        raise SystemExit(0)
    ack_wait=config['max_backoff_seconds']+2*config['timeout_seconds']+2*config['poll_interval_seconds']+10
    evidence={'recovery_wait_seconds':ack_wait};completed=False
    def cleanup():
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(dict(evidence,completed=completed),indent=2,default=str),encoding='utf-8')
        if not completed:
            compose('start','db','mqtt');time.sleep(5)
            compose('restart','backend');compose('start','modbus-bridge')
    atexit.register(cleanup);ready()
    if not args.recovery_only:
        asset='H06-RUL-ORACLE';record=rows(asset,[(0,10,0)])[0]
        before=asset_state(asset);retry=request('/api/v1/telemetry',record)
        assert retry['duplicate'] and asset_state(asset)==before
        changed=copy.deepcopy(record);changed['oil_temp_trip']=1;changed['acquisition']['snapshot_id']=None
        changed['acquisition']['snapshot_id']=payload_hash(changed)
        expect_http(409,changed);assert asset_state(asset)==before
        receipt=request('/api/v1/ingestion/receipts/'+changed['acquisition']['snapshot_id'])
        assert receipt['receipt_status']=='CONFLICT'
        from simulator.streaming import MqttPublisher
        publisher=MqttPublisher(host='127.0.0.1',port=51885,timeout=5)
        mqtt_before=request('/api/v1/ingest/mqtt/status')['conflicted_count']
        try: assert publisher.publish_payload(changed)['broker_acknowledged']
        finally:publisher.disconnect()
        for _ in range(30):
            if request('/api/v1/ingest/mqtt/status')['conflicted_count']>mqtt_before:break
            time.sleep(1)
        else:raise AssertionError('MQTT conflict was not recorded')
        assert asset_state(asset)==before
        evidence['retry_conflict']=dict(exact_retry=retry['duplicate'],accepted_state_unchanged=True,conflict_receipt=receipt,mqtt_conflict_count_increased=True)

        asset='H06-ROLLBACK-'+uuid4().hex[:8];register(asset);record=rows(asset,[(0,10,0)])[0]
        with psycopg.connect(DSN,autocommit=True) as db:
            db.execute(f"CREATE OR REPLACE FUNCTION h06_test_fail_analytics() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.transformer_id='{asset}' THEN RAISE EXCEPTION 'H06 disposable injected analytics failure'; END IF; RETURN NEW; END $$")
            db.execute('CREATE TRIGGER h06_test_fail BEFORE INSERT ON analytics FOR EACH ROW EXECUTE FUNCTION h06_test_fail_analytics()')
        try:
            expect_http(500,record);state=asset_state(asset)
            assert all(not values for values in state['tables'].values()) and state['checkpoint'] is None
            try:request('/api/v1/ingestion/receipts/'+record['acquisition']['snapshot_id'])
            except urllib.error.HTTPError as exc:assert exc.code==404
            else:raise AssertionError('Failed transaction exposed a committed receipt')
        finally:
            with psycopg.connect(DSN,autocommit=True) as db:
                db.execute('DROP TRIGGER h06_test_fail ON analytics');db.execute('DROP FUNCTION h06_test_fail_analytics()')
        accepted=request('/api/v1/telemetry',record);state=asset_state(asset)
        assert len(state['tables']['telemetry'])==len(state['tables']['analytics'])==1
        assert state['checkpoint'][0]['observation_count']==1
        evidence['sql_failure']=dict(http_status=500,no_committed_receipt_before_retry=True,accepted_rows_after_retry=1,checkpoint_observations=1)
        print('PASS real container exact retry, HTTP/MQTT conflict and injected SQL rollback',flush=True)

    strict_recovery(config)
    completed=True
