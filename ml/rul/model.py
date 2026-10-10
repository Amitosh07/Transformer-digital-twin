"""Synthetic first passage and operational evidence assessment, never HI conversion."""
from __future__ import annotations
import copy
from dataclasses import dataclass
from .common import event_time, iso, finite, lineage, synthetic, validate_source
from .config import Duty, SyntheticConfig
from .types import RULResult, ProjectedPoint

METHOD = 'SYNTHETIC_FIRST_PASSAGE_V1'
EXTENSION_VERSION = '1.0.0'
@dataclass(frozen=True)
class RULProjection:
    rul: RULResult
    projected_curve: list[ProjectedPoint]

def base_result(timestamp, source_kind=None, config=None) -> RULResult:
    return dict(rul_status='INSUFFICIENT_DATA',rul_method=METHOD,
        rul_target_definition='Declared fictional degradation reaches scenario endpoint; not physical end-of-life',
        rul_value=None,rul_unit='h',rul_lower=None,rul_upper=None,uncertainty_kind=None,
        forecast_horizon_hours=config.horizon_hours if config else None,
        future_duty_scenario=config.scenario_id if config else None,
        degradation_state=None,end_threshold=config.endpoint if config else None,
        degradation_unit='1' if config else None,degradation_rate_per_hour=config.rate_per_hour if config else None,
        equivalent_ageing_hours=None,source_kind=source_kind,simulated=False,
        model_version='synthetic-first-passage-v1',config_version=config.version if config else None,
        required_inputs=[],assumptions=[],limitation_codes=[],
        coverage_start=None,coverage_end=None,coverage_fraction=None,timestamp=iso(timestamp))

def first_passage(current, endpoint, horizon, duty):
    """Exact integration of a bounded piecewise-constant declared future rate."""
    current=finite(current,minimum=0);endpoint=finite(endpoint,positive=True);horizon=finite(horizon,positive=True)
    curve=[{'elapsed_hours':0.0,'degradation':float(current)}]
    if current >= endpoint:
        return 0.0,curve,True
    elapsed=0.0
    for piece in duty:
        duration=min(float(piece.hours),horizon-elapsed)
        if duration <= 0:
            break
        rate=float(piece.rate_per_hour)
        if rate > 0 and current+rate*duration >= endpoint-1e-12:
            crossing=(endpoint-current)/rate
            elapsed+=crossing
            curve.append({'elapsed_hours':elapsed,'degradation':float(endpoint)})
            return elapsed,curve,True
        current+=rate*duration;elapsed+=duration
        curve.append({'elapsed_hours':elapsed,'degradation':current})
    return None,curve,elapsed >= horizon-1e-10

def predict_synthetic(current, config, timestamp, acquisition, *, coverage_start=None,
                      coverage_fraction=None, limitations=()):
    result=base_result(timestamp,(acquisition or {}).get('source_kind'),config)
    result['simulated']=synthetic(acquisition)
    result['coverage_start']=iso(coverage_start) if coverage_start is not None else None
    result['coverage_end']=iso(timestamp)
    result['coverage_fraction']=coverage_fraction
    result['limitation_codes']=list(limitations)
    if not synthetic(acquisition):
        result['required_inputs']=['explicit synthetic source/origin']
        result['limitation_codes'].append('SYNTHETIC_CONFIG_INELIGIBLE_FOR_SOURCE')
        return RULProjection(result,[])
    # A declared endpoint already reached does not require extrapolation or a
    # future rate; zero hours is distinct from unavailable forward prognosis.
    if config is not None and config.endpoint is not None and current is not None and finite(current,minimum=0)>=config.endpoint:
        result.update(rul_status='END_THRESHOLD_REACHED',rul_value=0.0,degradation_state=float(current))
        result['assumptions']=['Fictional latent D and endpoint; no physical transformer end-of-life claim']
        return RULProjection(result,[{'elapsed_hours':0.0,'degradation':float(current)}])
    required=[]
    if config is None:
        required.append('versioned synthetic scenario configuration')
    if current is None:
        required.append('current synthetic degradation state')
    if config:
        for key in ('endpoint','rate_per_hour','horizon_hours'):
            if getattr(config,key) is None:
                required.append(key)
    if required:
        result['required_inputs']=required
        result['limitation_codes']+=['SYNTHETIC_INPUTS_MISSING']
        return RULProjection(result,[])
    finite(current,minimum=0)
    result['degradation_state']=float(current)
    result['assumptions']=['Fictional latent D is independent of health index and anomaly score',
        'Endpoint is a scenario definition, not transformer end-of-life',
        'Future duty begins at this event time; rates have units 1/hour']
    duty=config.future_duty or (Duty(config.horizon_hours,config.rate_per_hour),)
    value,curve,complete=first_passage(current,config.endpoint,config.horizon_hours,duty)
    if not complete:
        result['required_inputs']=['future duty covering the forecast horizon']
        result['limitation_codes'].append('INCOMPLETE_FUTURE_DUTY')
    elif value == 0:
        result.update(rul_status='END_THRESHOLD_REACHED',rul_value=0.0)
    elif value is None:
        result['rul_status']='NO_CROSSING_WITHIN_HORIZON'
        result['limitation_codes'].append('NO_FINITE_SCENARIO_CROSSING')
    else:
        result.update(rul_status='SIMULATED_ESTIMATE',rul_value=value)
        if config.rate_bounds_per_hour:
            low,high=config.rate_bounds_per_hour
            lower=(config.endpoint-current)/high if high else None
            upper=(config.endpoint-current)/low if low else None
            if upper is not None and upper <= config.horizon_hours+1e-10:
                result.update(rul_lower=lower,rul_upper=upper,uncertainty_kind='SCENARIO_RANGE')
            else:
                result['limitation_codes'].append('SCENARIO_BOUND_NO_CROSSING_WITHIN_HORIZON')
            result['assumptions'].append(f'Declared rate range {low}–{high}/hour; not calibrated confidence')
    result['assumptions'].append('Declared future duty: '+str([{'hours':d.hours,'rate_per_hour':d.rate_per_hour} for d in duty]))
    return RULProjection(result,curve)

REQUIREMENTS={
    'hotspot':('DEG_C','verified hotspot measurement or validated hotspot model; WTI status/oil surrogate is insufficient'),
    'liquid':(None,'verified liquid and applicability'),
    'insulation':(None,'verified insulation and applicability'),
    'ageing_parameters':(None,'justified thermal-ageing parameter set and reference'),
    'life_budget':('h','defensible equivalent-life budget'),
    'service_age':('h','prior service-age history'),
    'prior_exposure':('h','service age and consumed exposure history'),
    'future_duty':(None,'declared future load/ambient duty'),
    'time_coverage':('fraction','adequate verified temporal coverage'),
}
def assess_operational_eligibility(evidence=None):
    """Reports prerequisites; even all supplied evidence does not implement a life estimator."""
    evidence=evidence or {}
    missing=[]
    for key,(unit,description) in REQUIREMENTS.items():
        item=evidence.get(key) or {}
        valid=item.get('verification') == 'VERIFIED' and bool(item.get('evidence_reference')) and item.get('value') is not None and (unit is None or item.get('unit') == unit)
        if key == 'hotspot':
            valid=valid and item.get('semantics') in ('MEASURED_HOTSPOT','VALIDATED_HOTSPOT_MODEL')
            if valid:
                try: finite(item['value'])
                except ValueError: valid=False
        if key in ('liquid','insulation'):
            valid=valid and isinstance(item.get('value'),str) and bool(item['value'].strip())
        if key in ('ageing_parameters','future_duty'):
            valid=valid and isinstance(item.get('value'),(dict,list)) and bool(item['value'])
        if key in ('life_budget','service_age','prior_exposure','time_coverage') and valid:
            try:
                v=finite(item['value'],minimum=0,positive=key=='life_budget')
                if key=='time_coverage':
                    minimum=finite(item.get('minimum_fraction'),positive=True)
                    valid=minimum<=1 and minimum<=v<=1
            except ValueError:
                valid=False
        if not valid:
            missing.append((key,description))
    return {'eligible':not missing,'required_inputs':[d for _,d in missing],
            'limitation_codes':['MISSING_VERIFIED_'+k.upper() for k,_ in missing]}

def operational_result(timestamp, acquisition, evidence=None):
    assessment=assess_operational_eligibility(evidence)
    hotspot=(evidence or {}).get('hotspot') or {}
    if hotspot.get('semantics')=='MEASURED_HOTSPOT':
        a=acquisition or {}
        from .common import field_eligible
        if not field_eligible(a,'winding_temperature','DEG_C') or a.get('field_verification',{}).get('winding_temperature')!='VERIFIED':
            assessment['required_inputs'].append('source-verified winding hotspot in DEG_C; WTI contact/status is ineligible')
            assessment['limitation_codes'].append('SOURCE_HOTSPOT_UNITS_OR_SEMANTICS_INELIGIBLE')
    result=base_result(timestamp,(acquisition or {}).get('source_kind'))
    result.update(rul_method='THERMAL_AGEING_ELIGIBILITY_V1',model_version='thermal-ageing-eligibility-v1',
        rul_target_definition='Conditional insulation-life prerequisites; whole-transformer remaining life unavailable',
        required_inputs=assessment['required_inputs'],
        limitation_codes=assessment['limitation_codes']+['OPERATIONAL_RUL_ESTIMATOR_NOT_IMPLEMENTED'],
        assumptions=['Oil surrogate and binary WTI contacts are not verified winding hotspot',
                     'No life budget, physical ageing constants or empirical accuracy is invented'])
    return result

def update_degradation(previous, record, scenario):
    """Called only after H01 identity checks, on its staged per-asset state."""
    from ml.pipeline.identity import payload_hash
    validate_source(record)
    config=SyntheticConfig.from_dict(scenario)
    a=record.get('acquisition') or {}
    if not synthetic(a):
        if previous is not None:
            raise ValueError('source lineage changed under an active synthetic scenario')
        return None,RULProjection(operational_result(record['timestamp'],a),[])
    ts=event_time(record['timestamp']);start=event_time(config.start_time)
    if ts < start:
        raise ValueError('event precedes declared scenario start')
    if previous is not None:
        validate_extension(previous,scenario)
        if previous['lineage'] != lineage(a):
            raise ValueError('scenario lineage/run changed; use a separate asset/session')
        last=event_time(previous['last_event_time'])
        if ts <= last:
            raise ValueError('duplicate/late event must be handled by H01 before degradation')
        current=previous['degradation']
        covered=previous['covered_seconds'];gaps=previous['gap_count']
    else:
        last=start;current=config.initial_degradation;covered=0.0;gaps=0
    seconds=(ts-last).total_seconds()
    limitations=['DEGRADATION_GAP_UNSUPPORTED'] if gaps else []
    if seconds == 0:
        pass
    elif seconds > config.maximum_gap_seconds and not config.assume_constant_rate_across_gaps:
        current=None;gaps+=1
        if 'DEGRADATION_GAP_UNSUPPORTED' not in limitations:
            limitations.append('DEGRADATION_GAP_UNSUPPORTED')
    elif current is not None and config.rate_per_hour is not None:
        current+=config.rate_per_hour*seconds/3600
        covered+=seconds
    else:
        current=None
    expected=(ts-start).total_seconds()
    fraction=covered/expected if expected else 1.0
    projection=predict_synthetic(current,config,ts,a,coverage_start=start,coverage_fraction=fraction,limitations=limitations)
    if config.assume_constant_rate_across_gaps:
        projection.rul['assumptions'].append('Declared constant synthetic historical rate across missing observations; scenario support is not sensor coverage')
    extension=dict(extension_version=EXTENSION_VERSION,scenario=config.to_dict(),
        scenario_fingerprint=config.fingerprint,transformer_id=record['transformer_id'],
        lineage=lineage(a),degradation=current,start_event_time=iso(start),
        last_event_time=iso(ts),last_payload_hash=payload_hash(record),
        covered_seconds=covered,gap_count=gaps,projected_curve=projection.projected_curve)
    return extension,projection

def validate_extension(value, scenario, record=None):
    config=SyntheticConfig.from_dict(scenario)
    keys={'extension_version','scenario','scenario_fingerprint','transformer_id','lineage','degradation',
          'start_event_time','last_event_time','last_payload_hash','covered_seconds','gap_count','projected_curve'}
    if not isinstance(value,dict) or set(value)!=keys or value['extension_version']!=EXTENSION_VERSION:
        raise ValueError('incompatible synthetic degradation extension')
    if value['scenario_fingerprint']!=config.fingerprint or value['scenario']!=config.to_dict():
        raise ValueError('synthetic scenario version/parameters changed')
    start=event_time(value['start_event_time']);last=event_time(value['last_event_time'])
    if start!=event_time(config.start_time) or last<start:
        raise ValueError('invalid degradation event times')
    if value['degradation'] is not None:
        finite(value['degradation'],minimum=0)
    covered=finite(value['covered_seconds'],minimum=0)
    if covered>(last-start).total_seconds()+1e-8 or type(value['gap_count']) is not int or value['gap_count']<0:
        raise ValueError('invalid degradation coverage')
    if not isinstance(value['projected_curve'],list) or len(value['projected_curve'])>1026:
        raise ValueError('invalid projected curve')
    for point in value['projected_curve']:
        finite(point['elapsed_hours'],minimum=0);finite(point['degradation'],minimum=0)
    expected=predict_synthetic(value['degradation'],config,last,value['lineage']).projected_curve
    if value['projected_curve']!=expected:
        raise ValueError('projected curve differs from declared scenario/state')
    if record is not None:
        from ml.pipeline.identity import payload_hash
        if value['transformer_id']!=record['transformer_id'] or last!=event_time(record['timestamp']) or value['last_payload_hash']!=payload_hash(record) or value['lineage']!=lineage(record.get('acquisition')):
            raise ValueError('degradation checkpoint observation/lineage mismatch')
