"""Bounded native/WSL H06 commands. Run from any directory; no resets."""
import argparse,copy,json,subprocess,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE='http://127.0.0.1:8001'
def command(*args):
    return subprocess.check_output(args,cwd=ROOT,text=True,timeout=600).strip()
def request(path,body=None):
    data=None if body is None else json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json'}),timeout=120) as response:return json.load(response)
def ready():
    for _ in range(60):
        try:request('/health/ready');return
        except (OSError,ValueError):time.sleep(2)
    raise RuntimeError('Backend health did not become available within 120 seconds')
def register(asset):
    values={'rated_power_kva':30,'rated_voltage_lv':400,'rated_current_a':43.30127018922193,'measurement_side':'LV'}
    units={'rated_power_kva':'kVA','rated_voltage_lv':'V','rated_current_a':'A','measurement_side':None}
    payload=dict(id=asset,name=asset+' fictional demo',schema_version='1.1.0',**values,configuration_metadata=dict(version='fictional-demo-v1',status='SYNTHETIC_CONFIG',field_metadata={k:dict(unit=units[k],verification='SYNTHETIC_CONFIG',provenance='Declared H06 fictional configuration',evidence_reference=None,effective_at=None) for k in values}))
    try:request('/api/v1/transformers',payload)
    except urllib.error.HTTPError as e:
        if e.code!=409:raise
        existing=request('/api/v1/transformers/'+asset)
        if any(existing.get(k)!=v for k,v in payload.items()):raise RuntimeError('Existing asset configuration conflicts; select a deliberate separate run/asset')
def setup():
    ready()
    for asset in json.loads((ROOT/'simulator/config/analytics-policy.json').read_text())['assets']:register(asset)
    code="import json;from simulator.scheduler import Scheduler;c=json.load(open('/config/hackathon-single.yaml'));c['interval_seconds']=c['pre_roll_interval_seconds'];s=Scheduler(c);from simulator.register_map import encode,decode;print(json.dumps([decode(encode(s.tick()['H06-SIM-05'],1),transformer_id='H06-SIM-05',unit_id=1,gateway_id='H06-DEMO-GW',expected_interval_seconds=60).model_dump(mode='json') for _ in range(c['pre_roll_steps'])]))"
    if NATIVE:
        from simulator.scheduler import Scheduler
        c=json.loads((ROOT/'simulator/config/hackathon-native-server.json').read_text());c['interval_seconds']=c['pre_roll_interval_seconds'];scheduler=Scheduler(c)
        rows=[scheduler.tick()['H06-SIM-05'].model_dump(mode='json') for _ in range(c['pre_roll_steps'])]
    else:
        output=command('docker','compose','run','--rm','--no-deps','-T','--entrypoint','python','modbus-simulator','-c',code)
        # Compose's service build context can emit build progress to stdout;
        # the actual generator writes one final JSON line. Validate that line.
        rows=json.loads(output.splitlines()[-1])
        if not isinstance(rows,list) or len(rows)!=60:
            raise RuntimeError('Unexpected deterministic pre-roll output')
    # Hydrate history using the SAME map resolution/source/gateway lineage
    # as forward FC04 polling; do not mix raw generator and Modbus provenance.
    if NATIVE:
        from simulator.register_map import encode,decode
        from simulator.schema import TransformerRecord
        rows=[decode(encode(TransformerRecord.model_validate(record),1),transformer_id='H06-SIM-05',unit_id=1,gateway_id='H06-DEMO-GW',expected_interval_seconds=60).model_dump(mode='json') for record in rows]
    for start in range(0,len(rows),25):
        response=request('/api/v1/telemetry/batch',{'records':rows[start:start+25]})
        if response['parse_error_count'] or response['out_of_range_count']: raise RuntimeError(str(response))
        print('Pre-roll accepted/retried',min(start+25,len(rows)),flush=True)
    print('Registered fictional assets; accepted deterministic event-time pre-roll',len(rows))
def primary():
    ready()
    if NATIVE:
        import sys
        subprocess.run([sys.executable,'-m','simulator.cli','modbus-bridge','--config',str(ROOT/'simulator/config/hackathon-native-bridge.json')],check=True,cwd=ROOT);return
    command('docker','compose','--profile','primary','up','--no-build','--no-recreate','-d','modbus-bridge');print('Primary read-only Modbus bridge started; PUBACK alone does not prove commit')
def check():
    ready();latest=request('/api/v1/transformers/H06-SIM-05/latest');assert latest['telemetry'] and latest['analytics'],'Missing persisted observations/analytics'
    record=latest['telemetry'];snapshot=record['acquisition']['snapshot_id'];receipt=request('/api/v1/ingestion/receipts/'+snapshot)
    assert receipt['receipt_status']=='COMMITTED' and receipt['payload_hash']==snapshot
    assert latest['analytics']['timestamp']==record['timestamp'],'Stale analytics'
    rul=request('/api/v1/transformers/H06-SIM-05/rul');energy=request('/api/v1/transformers/H06-SIM-05/energy?window=1h&anchor=latest')
    assert rul['rul'] is not None and rul['rul']['simulated'];assert energy['energy_method']=='SIMULATED'
    evidence={'latest':latest,'receipt':receipt,'rul':rul,'energy':energy}
    directory=args.evidence_directory or ROOT/'docs/hackathon_readiness/execution/evidence/h06';directory.mkdir(parents=True,exist_ok=True)
    (directory/'primary-api.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2))
def replay():
    ready();register('H06-REPLAY-R1')
    if NATIVE:
        import sys
        command(sys.executable,'-m','simulator.cli','replay-canonical','--input',str(ROOT/'simulator/config/replay-canonical.jsonl'),'--transformer-id','H06-REPLAY-R1','--run-id','H06-R1','--http-url',BASE,'--speed','20')
    else:
        command('docker','compose','run','--rm','--no-deps','modbus-simulator','replay-canonical','--input','/config/replay-canonical.jsonl','--transformer-id','H06-REPLAY-R1','--run-id','H06-R1','--http-url','http://backend:8000','--speed','20')
    print('REPLAYED HTTP fallback; original event times preserved; does not prove Modbus path')
def future25():
    from demo_portfolio import run
    run(args.duration_seconds,args.evidence_directory)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['setup','primary','check','replay','25']);parser.add_argument('--api-url',default=BASE);parser.add_argument('--native',action='store_true');parser.add_argument('--evidence-directory',type=Path);parser.add_argument('--duration-seconds',type=int,default=1800)
    args=parser.parse_args();NATIVE=args.native;BASE=args.api_url.rstrip('/');{'setup':setup,'primary':primary,'check':check,'replay':replay,'25':future25}[args.action]()
