"""Fixed UTC synthetic inputs only, reading the authoritative H00 examples."""
import copy
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
ROOT=Path(__file__).resolve().parents[2]
EXAMPLES=json.loads((ROOT/'tests/fixtures/hackathon/examples.json').read_text())
START='2026-10-09T00:00:00Z'
def example(name):
    return copy.deepcopy(next(e['payload'] for e in EXAMPLES if e['name']==name))
def row(seconds=0, power=10, counter=None, asset='HX-A', source='SIMULATED',run='run-1'):
    value=example('telemetry-valid')
    value.update(transformer_id=asset,timestamp=(datetime(2026,10,9,tzinfo=timezone.utc)+timedelta(seconds=seconds)).isoformat(),
                 active_power_total=power,energy_kwh=counter,schema_version='1.1.0')
    a=value['acquisition'];a.update(source_kind=source,snapshot_id=None,sequence=int(seconds),expected_interval_seconds=5)
    a['field_units'].update(active_power_total='kW',energy_kwh='kWh',current_l1='A',current_l2='A',current_l3='A')
    for key in ('active_power_total','energy_kwh','current_l1','current_l2','current_l3'):
        a['field_verification'][key]='VERIFIED' if source=='LIVE' else 'SYNTHETIC'
    if source=='LIVE':
        a.update(origin_kind='LIVE',timezone_status='VERIFIED')
        a['field_verification']={k:'VERIFIED' if v=='SYNTHETIC' else v for k,v in a['field_verification'].items()}
    elif source=='REPLAYED':
        a.update(origin_kind='SIMULATED',origin_transformer_id='SOURCE-ORIGINAL',replay_run_id=run,timestamp_origin='SOURCE_EVENT')
    return value
def schema_validate(name, value):
    from jsonschema import Draft202012Validator, FormatChecker
    schema=json.loads((ROOT/'tests/fixtures/hackathon'/name).read_text())
    Draft202012Validator(schema,format_checker=FormatChecker()).validate(value)
def loss_model(version='fictional-loss-v1', no_load=.8, rated_load=.2):
    from ml.energy import LossModel
    fields={key:{'unit':unit,'verification':'SYNTHETIC_CONFIG','provenance':'Fictional H05 arithmetic configuration','evidence_reference':None}
            for key,unit in [('loss_parameters.no_load_kw','kW'),('loss_parameters.rated_load_kw','kW'),('rated_current_a','A')]}
    return LossModel(version,no_load,rated_load,10,'LV',True,'Fictional LV delivered-output boundary',fields)
