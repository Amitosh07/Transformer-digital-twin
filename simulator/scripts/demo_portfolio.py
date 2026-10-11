"""H07 integrated 25-asset measurement runner; reuses installed H03 code."""
import copy,json,os,platform,shutil,subprocess,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import psycopg
from demo_runtime import ROOT,register,request
from simulator.modbus_bridge import SnapshotPoller
PROJECT='transformer-h06-20261009'
DSN='host=127.0.0.1 port=55433 user=transformer password=transformer dbname=transformer'
def docker(*args):return subprocess.check_output(['docker',*args],cwd=ROOT,text=True,timeout=40).strip()
def utc():return datetime.now(timezone.utc).isoformat()
def get(path):
    begin=time.perf_counter()
    with urllib.request.urlopen('http://127.0.0.1:8001'+path,timeout=5) as response:return json.load(response),(time.perf_counter()-begin)*1000

def run(duration=1800,evidence_directory=None):
    if os.environ.get('COMPOSE_PROJECT_NAME')!=PROJECT:raise RuntimeError('Select the established disposable H06 project explicitly')
    if not 30<=duration<=1800:raise ValueError('diagnostic duration 30..1800; acceptance requires full 1800')
    if shutil.disk_usage('C:/').free < 5*1024**3: raise RuntimeError('At least 5 GiB C: free required before starting')
    run_id=uuid4().hex[:6];out=(evidence_directory or ROOT/'docs/hackathon_readiness/execution/evidence/h07')/('soak-'+run_id);out.mkdir(parents=True)
    cfgdir=ROOT/'simulator/config'/('h07-'+run_id);cfgdir.mkdir()
    source=copy.deepcopy(json.loads((ROOT/'simulator/config/hackathon-25.yaml').read_text()))
    source['timeline']=[];assets=[]
    for i,a in enumerate(source['assets']):
        asset=f'H07-{run_id}-{i+1:02d}';assets.append(asset);a['transformer_id']=asset;a['configuration']['transformer_id']=asset
        a['timeline']=([{'from_seconds':120,'to_seconds':150,'scenario':'OVERLOAD'},{'from_seconds':150,'to_seconds':180,'scenario':'ALARM_TRIP'}] if i==0 else [])
    sim=PROJECT+'-h07-source-'+run_id;bridge=PROJECT+'-h07-bridge-'+run_id
    existing=json.loads(docker('inspect',docker('compose','ps','-q','modbus-bridge')))[0]
    network=next(iter(existing['NetworkSettings']['Networks']));image=docker('image','inspect','transformer-h07-runtime','--format','{{.Id}}')
    policy_path=ROOT/'simulator/config/analytics-policy.json';policy=json.loads(policy_path.read_text());original=copy.deepcopy(policy['assets'])
    bridge_cfg=copy.deepcopy(json.loads((ROOT/'simulator/config/hackathon-bridge.yaml').read_text()))
    bridge_cfg['audit_delivery']=True
    bridge_cfg['gateway_id']='H07-'+run_id;bridge_cfg['spool']['directory']='/spool/h07-'+run_id
    bridge_cfg['assets']=[dict(transformer_id=a,unit_id=i+1,host=sim,port=1502,expected_interval_seconds=5) for i,a in enumerate(assets)]
    source['audit_gateway_id']=bridge_cfg['gateway_id']
    for asset in assets:register(asset)
    source['start_utc']=utc();started=source['start_utc']
    for i,asset in enumerate(assets):
        policy['assets'][asset]=dict(synthetic_rul=dict(scenario_id='H07_FICTIONAL_CONSTANT_'+str(i),version='h07-fictional-rul-v1',start_time=started,initial_degradation=.2+i*.001,endpoint=1.,rate_per_hour=.01+i*.0001,horizon_hours=100.,maximum_gap_seconds=10.,assume_constant_rate_across_gaps=False,rate_bounds_per_hour=[.008+i*.0001,.012+i*.0001],future_duty=[]),energy=dict(version='h07-fictional-power-v1',method='POWER',maximum_gap_seconds=10,power_sign='IMPORT_ONLY_NONNEGATIVE'))
    assert all(policy['assets'][k]==v for k,v in original.items())
    policy_path.write_text(json.dumps(policy,indent=2),encoding='utf-8')
    (cfgdir/'server.json').write_text(json.dumps(source,indent=2),encoding='utf-8');(cfgdir/'bridge.json').write_text(json.dumps(bridge_cfg,indent=2),encoding='utf-8')
    manifest=dict(run_id=run_id,assets=assets,source=source,bridge=bridge_cfg,source_container=sim,bridge_container=bridge,start_utc=started,requested_duration_seconds=duration,target_duration_seconds=1800,software=dict(python=platform.python_version(),host=platform.platform(),docker=docker('version','--format','{{.Server.Version}}'),image=image),evidence_directory=str(out),status='starting')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('H07 manifest:',out/'manifest.json',flush=True)
    browser=None;completed=False;t0=None
    try:
        docker('run','-d','--name',sim,'--network',network,'--mount',f'type=bind,source={cfgdir},target=/h07,readonly','-p','127.0.0.1:1503:1502',image,'modbus-server','--config','/h07/server.json')
        deadline=time.monotonic()+30
        poller=SnapshotPoller(dict(transformer_id=assets[0],unit_id=1,host='127.0.0.1',port=1503,expected_interval_seconds=5),bridge_cfg['gateway_id'])
        while True:
            try:initial=poller.poll().model_dump(mode='json');break
            except Exception:
                if time.monotonic()>deadline:raise
                time.sleep(1)
        poller.close();(out/'initial-fc04.json').write_text(json.dumps(initial,indent=2),encoding='utf-8')
        docker('run','-d','--name',bridge,'--network',network,'--mount',f'type=bind,source={cfgdir},target=/h07,readonly','--volumes-from',docker('compose','ps','-q','modbus-bridge'),image,'modbus-bridge','--config','/h07/bridge.json')
        t0=time.monotonic();manifest.update(status='running',measurement_start_utc=utc());(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        browser_log=(out/'browser.log').open('w',encoding='utf-8')
        browser=subprocess.Popen(['node',str(ROOT/'simulator/scripts/demo_portfolio_browser.mjs'),str(out/'manifest.json')],cwd=ROOT,stdout=browser_log,stderr=subprocess.STDOUT)
        rows_log=(out/'measurements.jsonl').open('a',encoding='utf-8');samples=0;failure_events=[]
        while time.monotonic()-t0<duration:
            elapsed=time.monotonic()-t0
            data={'wall_time':utc(),'elapsed_seconds':elapsed,'disk_free_c_bytes':shutil.disk_usage('C:/').free,'disk_free_d_bytes':shutil.disk_usage('D:/').free}
            try:
                status,ms=get('/api/v1/ingest/mqtt/status');data['mqtt']=status;data['mqtt_api_ms']=ms
                with psycopg.connect(DSN,connect_timeout=3) as db:
                    data['database_bytes']=db.execute("SELECT pg_database_size('transformer')").fetchone()[0]
                    stats=db.execute("SELECT transformer_id,count(*),min(timestamp),max(timestamp),count(DISTINCT acquisition->>'sequence'),count(*) FILTER(WHERE oil_temp_trip=1),count(*) FILTER(WHERE ingestion_outcome='REJECTED_LATE') FROM telemetry WHERE transformer_id=ANY(%s) GROUP BY transformer_id",(assets,)).fetchall()
                    data['per_asset_sql']=[dict(asset=a,committed=n,first=str(f),last=str(l),unique_sequences=q,trip_rows=tr,late_rows=late) for a,n,f,l,q,tr,late in stats]
                    if samples in (0,12,18) or elapsed>duration-15:
                        selected={}
                        for asset in assets[:3]:
                            latest,api_ms=get('/api/v1/transformers/'+asset+'/latest');energy,_=get('/api/v1/transformers/'+asset+'/energy?window=1h&anchor=latest')
                            checkpoint=db.execute('SELECT checkpoint FROM ml_checkpoints WHERE transformer_id=%s',(asset,)).fetchone()
                            alerts=db.execute('SELECT to_jsonb(t) FROM alerts t WHERE transformer_id=%s',(asset,)).fetchall()
                            maintenance=db.execute('SELECT to_jsonb(t) FROM maintenance_records t WHERE transformer_id=%s',(asset,)).fetchall()
                            selected[asset]=dict(latest=latest,energy=energy,checkpoint=checkpoint[0] if checkpoint else None,alerts=alerts,maintenance=maintenance,api_ms=api_ms)
                        (out/f'isolation-{int(elapsed):04d}.json').write_text(json.dumps(selected,indent=2,default=str),encoding='utf-8')
                logs=docker('logs','--tail','100',bridge)
                statuses=[json.loads(line) for line in logs.splitlines() if line.startswith('{') and 'spool_usage' in line]
                data['bridge']=statuses[-1] if statuses else {'raw':logs[-500:]}
                data['containers']=docker('stats','--no-stream','--format','{{json .}}',sim,bridge,docker('compose','ps','-q','backend'),docker('compose','ps','-q','db'))
            except Exception as exc:data['measurement_error']=repr(exc)
            rows_log.write(json.dumps(data,default=str)+'\n');rows_log.flush();samples+=1
            if data['disk_free_c_bytes']<4*1024**3:raise RuntimeError('Host C: free space fell below 4 GiB emergency boundary; target unmet')
            print(json.dumps(dict(elapsed_seconds=round(elapsed),active_sql_assets=len(data.get('per_asset_sql',[])),committed=sum(a['committed'] for a in data.get('per_asset_sql',[])),queue=data.get('mqtt',{}).get('queue_depth'),spool=data.get('bridge',{}).get('spool_usage'),measurement_error=data.get('measurement_error'))),flush=True)
            time.sleep(min(10,max(0,duration-(time.monotonic()-t0))))
        completed=True
    except BaseException as exc:manifest['failure']=repr(exc);raise
    finally:
        manifest.update(status='completed' if completed else 'failed',actual_duration_seconds=time.monotonic()-t0 if t0 else 0,end_utc=utc())
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        try:docker('stop',sim)
        except Exception:pass
        if browser:
            try:browser.wait(timeout=25)
            except subprocess.TimeoutExpired:browser.terminate();browser.wait(timeout=10)
            manifest['browser_exit_code']=browser.returncode
        for container in (sim,bridge):
            try:docker('stop',container)
            except Exception:pass
        for container in (sim,bridge):
            try:(out/(container+'-logs.txt')).write_text(docker('logs',container),encoding='utf-8')
            except Exception:pass
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        print('H07 retained containers/spool/config/evidence:',out,flush=True)
