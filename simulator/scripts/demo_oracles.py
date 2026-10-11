"""Real API arithmetic trace using explicit fictional canonical measurements."""
import json,math
from datetime import datetime,timezone,timedelta
from pathlib import Path
from simulator.generator import SyntheticGenerator
from simulator.schema import TransformerConfig
from ml.pipeline.identity import payload_hash
from demo_runtime import request,register,ROOT
START=datetime(2026,10,9,tzinfo=timezone.utc)
def rows(asset,points):
    generator=SyntheticGenerator(TransformerConfig(transformer_id=asset,rated_power_kva=30,rated_voltage_lv=400,rated_current_a=43.30127018922193,configuration_status='SYNTHETIC_CONFIG',configuration_version='fictional-demo-v1',measurement_side='LV'),seed=42,interval_s=3600)
    result=[]
    for seconds,power,counter in points:
        record=generator.next_record(START+timedelta(seconds=seconds)).model_dump(mode='json')
        record.update(active_power_total=power,apparent_power_total=power,reactive_power_total=0,energy_kwh=counter,oil_temp_alarm=0,oil_temp_trip=0,magnetic_oil_gauge_alarm=0)
        for phase in (1,2,3):record.update({f'phase_voltage_l{phase}':400/math.sqrt(3),f'current_l{phase}':power*1000/(400*math.sqrt(3)),f'power_factor_l{phase}':1})
        record['acquisition']['snapshot_id']=None;record['acquisition']['snapshot_id']=payload_hash(record);result.append(record)
    return result
if __name__=='__main__':
    import argparse,demo_runtime
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url',default='http://127.0.0.1:8001')
    parser.add_argument('--evidence-directory',type=Path,default=ROOT/'docs/hackathon_readiness/execution/evidence/h06')
    args=parser.parse_args();demo_runtime.BASE=args.api_url.rstrip('/')
    cases={'H06-RUL-ORACLE':[(0,10,0)],'H06-ENERGY-CONSTANT':[(0,10,0),(7200,10,20)],'H06-ENERGY-RAMP':[(0,0,0),(3600,10,5)],'H06-ENERGY-RESET':[(0,10,100),(3600,10,110),(7200,10,2),(10800,10,5)]}
    evidence={}
    for asset,points in cases.items():
        register(asset);records=rows(asset,points)
        for record in records:request('/api/v1/telemetry',record)
        end=(START+timedelta(seconds=points[-1][0])).isoformat()
        from urllib.parse import urlencode
        resource=request('/api/v1/transformers/'+asset+'/rul') if asset=='H06-RUL-ORACLE' else request('/api/v1/transformers/'+asset+'/energy?'+urlencode({'from':START.isoformat(),'to':end,'anchor':'latest'}))
        evidence[asset]=resource
    assert evidence['H06-RUL-ORACLE']['rul']['rul_value']==80
    assert evidence['H06-ENERGY-CONSTANT']['consumed_kwh']==20
    assert evidence['H06-ENERGY-RAMP']['consumed_kwh']==5
    assert evidence['H06-ENERGY-RESET']['consumed_kwh'] is None and evidence['H06-ENERGY-RESET']['covered_consumed_kwh']==13
    # A deliberately unverified LIVE-labelled validation input is not a device
    # authorization or physical measurement claim. It must never gain ratings,
    # lifetime, risk, loss or efficiency from the fictional scenario policies.
    asset='H06-UNVERIFIED-INPUT'
    try: request('/api/v1/transformers',dict(id=asset,name='Unverified integration validation input'))
    except Exception as exc:
        import urllib.error
        if not isinstance(exc,urllib.error.HTTPError) or exc.code!=409: raise
    for record in rows(asset,[(0,10,0),(5,10,0)]):
        record['source_name']='integration-unverified-input';record['scenario_id']=None
        a=record['acquisition'];a.update(source_kind='LIVE',origin_kind='LIVE',source_name=record['source_name'],timezone_status='VERIFIED',snapshot_id=None)
        a['field_units']={field:'UNKNOWN' for field in a['field_units']}
        a['field_verification']={field:'UNVERIFIED' for field in a['field_verification']}
        a['measurement_side']='UNKNOWN';a['snapshot_id']=payload_hash(record)
        request('/api/v1/telemetry',record)
    actual=request('/api/v1/transformers/'+asset+'/latest')
    unavailable=request('/api/v1/transformers/'+asset+'/energy?window=1h&anchor=latest')
    assert actual['analytics']['rul']['rul_value'] is None and actual['analytics']['fault_risk'] is None
    assert unavailable['consumed_kwh'] is None and unavailable['loss_kw'] is None and unavailable['efficiency_percent'] is None
    evidence[asset]=dict(latest=actual,energy=unavailable,input_kind='Unverified LIVE-labelled integration validation input; not a real device')
    directory=args.evidence_directory;directory.mkdir(parents=True,exist_ok=True)
    (directory/'api-oracles.json').write_text(json.dumps(evidence,indent=2))
    replay=rows('H06-RUL-ORACLE',[(0,10,0),(5,10,0)])
    (ROOT/'simulator/config/replay-canonical.jsonl').write_text(''.join(json.dumps(record)+'\n' for record in replay))
    print(json.dumps(evidence,indent=2))
