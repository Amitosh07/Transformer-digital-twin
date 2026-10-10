"""Pure event-time analytics; no SQL, transport or client-side fallback."""
from __future__ import annotations
import copy
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from ml.rul.common import event_time, iso, finite, field_eligible, lineage, synthetic, validate_source
from .config import EnergyConfig
from .loss import LossModel, loss_eligible, interval_loss, efficiency_percent, synthetic_parameters
from .types import EnergyResult

CALCULATION_VERSION='energy-event-time-v1'
class EnergyConflictError(ValueError):
    """Changed observation under an accepted asset/time or snapshot identity."""

@dataclass(frozen=True)
class EnergyAnalysis:
    result: EnergyResult
    mean_power_kw: float | None

def normalize_records(records,asset):
    from ml.pipeline.identity import FIELDS, payload_hash
    allowed=set(FIELDS)|{'transformer_id','timestamp','schema_version','source_name','scenario_id',
        'acquisition','received_at','id','is_missing_critical','data_quality_score'}
    accepted={};snapshots={}
    for raw in records:
        row=copy.deepcopy(dict(raw))
        if row.get('transformer_id')!=asset:
            raise ValueError('mixed or mismatched transformer identity')
        if set(row)-allowed:
            raise ValueError('noncanonical measurement fields')
        timestamp=event_time(row['timestamp'])
        for field in FIELDS:
            value=row.get(field)
            if value is not None and field not in ('oil_temp_alarm','oil_temp_trip','magnetic_oil_gauge_alarm'):
                finite(value)
                if field.startswith('power_factor_') and not -1 <= value <= 1:
                    raise ValueError('power factor must be in [-1,1]')
        validate_source(row)
        digest=payload_hash(row)
        snapshot=(row.get('acquisition') or {}).get('snapshot_id')
        if snapshot is not None and snapshot!=digest:
            raise EnergyConflictError('snapshot ID differs from semantic payload')
        if timestamp in accepted and payload_hash(accepted[timestamp])!=digest:
            raise EnergyConflictError('changed duplicate asset/event identity')
        if snapshot is not None and snapshot in snapshots and snapshots[snapshot]!=digest:
            raise EnergyConflictError('changed duplicate snapshot')
        accepted[timestamp]=row
        if snapshot is not None:
            snapshots[snapshot]=digest
    return sorted(accepted.items())

def positive_parts(p0,p1,hours):
    """Separate import/export; split a linear segment at its actual zero crossing."""
    if p0>=0 and p1>=0:
        return (p0+p1)/2*hours,0.0
    if p0<=0 and p1<=0:
        return 0.0,-(p0+p1)/2*hours
    left=hours*abs(p0)/(abs(p0)+abs(p1))
    if p0>0:
        return p0*left/2,-p1*(hours-left)/2
    return p1*(hours-left)/2,-p0*left/2

def _missing_intervals(start,end,segments,excluded):
    missing=[];cursor=start
    for left,right in segments+[(end,end)]:
        if cursor<left:
            reasons=[reason for a,b,reason in excluded if a<left and b>cursor]
            missing.append({'start':iso(cursor),'end':iso(left),'reason':','.join(dict.fromkeys(reasons)) or 'UNSUPPORTED_WINDOW_BOUNDARY'})
        cursor=max(cursor,right)
    return missing

def analyze_energy(records, transformer_id, window_start, window_end, config:EnergyConfig,
                   *, asset_config=None, loss_model:LossModel|None=None,
                   alternative_loss_model:LossModel|None=None):
    start=event_time(window_start);end=event_time(window_end)
    if not isinstance(transformer_id,str) or not transformer_id.strip() or transformer_id!=transformer_id.strip() or len(transformer_id)>128 or start>=end or (end-start).total_seconds()>config.maximum_window_seconds:
        raise ValueError('nonempty asset and configured bounded positive window required')
    bounded_records=[]
    for record in records:
        if len(bounded_records) >= config.maximum_records:
            raise ValueError('record count exceeds configured safe bound; no silent truncation')
        bounded_records.append(record)
    records=tuple(bounded_records)
    rows=normalize_records(records,transformer_id)
    # Context endpoints are permitted only around this bounded interval.
    inside=[(t,r) for t,r in rows if start<=t<=end]
    before=[(t,r) for t,r in rows if t<start];after=[(t,r) for t,r in rows if t>end]
    rows=before[-1:]+inside+after[:1]
    contexts={str(lineage(r.get('acquisition'))) for _,r in rows}
    if len(contexts)>1:
        raise ValueError('mixed source/run/map/side lineage requires separate calculation windows')
    acquisition=(rows[0][1].get('acquisition') or {}) if rows else {}
    is_synthetic=synthetic(acquisition)
    source_kind=acquisition.get('source_kind')
    unit_checks=[field_eligible(r.get('acquisition'),'active_power_total','kW') for _,r in rows]
    power_unit_status=('SYNTHETIC' if is_synthetic and acquisition.get('field_verification',{}).get('active_power_total')=='SYNTHETIC' else 'VERIFIED') if any(unit_checks) else ('UNVERIFIED' if acquisition.get('field_units',{}).get('active_power_total') not in (None,'UNKNOWN') else 'UNKNOWN')
    result=dict(transformer_id=transformer_id,timestamp=None,schema_version='1.1.0',
        energy_status='UNAVAILABLE',energy_method='UNAVAILABLE',calculation_method='NONE',
        source_kind=source_kind,active_power_unit_status=power_unit_status,energy_unit='kWh',
        window_start=iso(start),window_end=iso(end),consumed_kwh=None,covered_consumed_kwh=None,
        import_kwh=None,export_kwh=None,peak_kw=None,loss_kw=None,loss_kwh=None,
        estimated_savings_kwh=None,efficiency_percent=None,loss_method=None,coverage_seconds=0.0,
        coverage_fraction=0.0,gap_count=0,reset_count=0,missing_intervals=[],peak_time=None,
        load_profile=[],conservation_recommendation=None,conservation_evidence=[],
        assumptions=[],limitation_codes=[],config_version=config.version,
        map_version=acquisition.get('map_version'),calculation_version=CALCULATION_VERSION,
        provenance=dict(power_unit=acquisition.get('field_units',{}).get('active_power_total'),
            counter_unit=acquisition.get('field_units',{}).get('energy_kwh'),
            counter_semantics=config.counter_semantics,continuity_evidence=config.continuity_reference,
            measurement_side=acquisition.get('measurement_side') or 'UNKNOWN',
            maximum_gap_seconds=config.maximum_gap_seconds,
            minimum_coverage_fraction=config.minimum_coverage_fraction))
    result['assumptions']+=['Source lineage: '+str(lineage(acquisition)),
        'Counter and power are alternative authoritative methods; never summed',
        'No extrapolation beyond supported event-time endpoints',
        'Power sign convention: '+config.power_sign]
    if is_synthetic:
        result['assumptions'].append('Fictional simulated measurements/configuration; not measured real energy')
    counter_supported=config.counter_semantics in ('CUMULATIVE_IMPORT','CUMULATIVE_EXPORT')
    units_supported=any(field_eligible(r.get('acquisition'),'energy_kwh','kWh') for _,r in rows) if config.method=='COUNTER' else any(unit_checks)
    eligible=units_supported and (counter_supported if config.method=='COUNTER' else config.power_sign!='UNKNOWN')
    if not eligible:
        result['limitation_codes'].append('COUNTER_UNITS_OR_SEMANTICS_UNVERIFIED' if config.method=='COUNTER' else 'POWER_UNITS_OR_SIGN_UNVERIFIED')
    else:
        result['energy_method']='SIMULATED' if is_synthetic else ('MEASURED_COUNTER' if config.method=='COUNTER' else 'CALCULATED_POWER')
        result['calculation_method']='COUNTER_DIFFERENCE' if config.method=='COUNTER' else 'TRAPEZOID'
        result['energy_status']='INSUFFICIENT_DATA'
    if config.power_semantics!='INSTANTANEOUS':
        result['assumptions'].append(config.power_semantics+': declared interval-average is a constant supported interval (equal-endpoint trapezoid), not instantaneous interpolation')
    if config.allow_boundary_interpolation:
        result['assumptions'].append('Explicit linear power/current interpolation at bounded window boundaries')
    segments=[];excluded=[];imports=exports=signed_power_integral=loss_energy=0.0
    loss_supported=loss_eligible(loss_model,acquisition) and config.method=='POWER' and config.power_semantics=='INSTANTANEOUS'
    overload_segments=[]
    resets={event_time(t) for t in config.reset_event_times}
    for (ta,ra),(tb,rb) in zip(rows,rows[1:]):
        left=max(ta,start);right=min(tb,end)
        if left>=right:
            continue
        original_seconds=(tb-ta).total_seconds();seconds=(right-left).total_seconds()
        reason=None;part_import=part_export=0.0
        aa=ra.get('acquisition');ab=rb.get('acquisition')
        counter_reset=False
        if config.method=='COUNTER' and eligible and start<=tb<=end:
            va=ra.get('energy_kwh');vb=rb.get('energy_kwh')
            if va is not None and vb is not None and min(va,vb)>=0 and all(field_eligible(a,'energy_kwh','kWh') for a in (aa,ab)):
                counter_reset=tb in resets or (vb<va and config.counter_modulus is None)
                if counter_reset:
                    result['reset_count']+=1
        if not eligible:
            reason='UNVERIFIED_UNITS_OR_SOURCE_SEMANTICS'
        elif counter_reset:
            reason='COUNTER_RESET'
            if original_seconds>config.maximum_gap_seconds and not config.continuity_reference:
                reason+=',LONG_GAP';result['gap_count']+=1
        elif original_seconds>config.maximum_gap_seconds and not (config.method=='COUNTER' and config.continuity_reference):
            reason='LONG_GAP';result['gap_count']+=1
        elif (ta<start or tb>end) and (config.method=='COUNTER' or not config.allow_boundary_interpolation):
            reason='UNSUPPORTED_WINDOW_BOUNDARY'
        elif config.method=='COUNTER':
            va=ra.get('energy_kwh');vb=rb.get('energy_kwh')
            if va is None or vb is None or not all(field_eligible(a,'energy_kwh','kWh') for a in (aa,ab)):
                reason='COUNTER_ENDPOINT_UNAVAILABLE'
            elif va<0 or vb<0:
                reason='INVALID_CUMULATIVE_COUNTER'
            elif config.counter_modulus is not None and max(va,vb)>=config.counter_modulus:
                reason='COUNTER_OUTSIDE_MODULUS'
            elif tb in resets or (vb<va and config.counter_modulus is None):
                reason='COUNTER_RESET'
            else:
                delta=Decimal(str(vb))-Decimal(str(va))
                if delta<0:
                    delta+=Decimal(str(config.counter_modulus))
                    result['assumptions'].append('Counter rollover: '+config.rollover_reference)
                delta=float(delta)
                if config.counter_semantics=='CUMULATIVE_IMPORT':
                    part_import=delta
                else:
                    part_export=delta
                if original_seconds>config.maximum_gap_seconds:
                    result['assumptions'].append('Independent counter continuity evidence: '+config.continuity_reference)
        else:
            va=ra.get('active_power_total');vb=rb.get('active_power_total')
            if not all(field_eligible(a,'active_power_total','kW') for a in (aa,ab)) or va is None or vb is None:
                reason='POWER_ENDPOINT_UNAVAILABLE'
            else:
                va=float(va);vb=float(vb)
                if config.power_semantics=='INTERVAL_AVERAGE_START':
                    vb=va
                elif config.power_semantics=='INTERVAL_AVERAGE_END':
                    va=vb
                p0=va+(vb-va)*(left-ta).total_seconds()/original_seconds
                p1=va+(vb-va)*(right-ta).total_seconds()/original_seconds
                if config.power_sign=='IMPORT_ONLY_NONNEGATIVE' and min(p0,p1)<0:
                    reason='NEGATIVE_POWER_OUTSIDE_DECLARED_SIGN_CONVENTION'
                else:
                    part_import,part_export=positive_parts(p0,p1,seconds/3600)
                    signed_power_integral+=(p0+p1)/2*seconds
                    if min(p0,p1)<0:
                        loss_supported=False
                    if loss_supported:
                        try:
                            first=dict(ra);last=dict(rb)
                            for field in ('current_l1','current_l2','current_l3'):
                                ia=finite(ra.get(field),minimum=0);ib=finite(rb.get(field),minimum=0)
                                if not all(field_eligible(a,field,'A') for a in (aa,ab)):
                                    raise ValueError('unverified current')
                                first[field]=ia+(ib-ia)*(left-ta).total_seconds()/original_seconds
                                last[field]=ia+(ib-ia)*(right-ta).total_seconds()/original_seconds
                            loss_energy+=interval_loss(loss_model,first,last,seconds)
                        except ValueError:
                            loss_supported=False
                    if asset_config is not None:
                        loading_a=asset_config.calculate_loading(ra.get('apparent_power_total'),aa)[0]
                        loading_b=asset_config.calculate_loading(rb.get('apparent_power_total'),ab)[0]
                        if loading_a is not None and loading_b is not None and min(loading_a,loading_b)>100:
                            overload_segments.append((left,right))
        if reason:
            excluded.append((left,right,reason))
        else:
            segments.append((left,right));imports+=part_import;exports+=part_export
            result['timestamp']=iso(tb)
    covered=sum((b-a).total_seconds() for a,b in segments)
    fraction=covered/(end-start).total_seconds()
    result.update(coverage_seconds=covered,coverage_fraction=fraction,
                  missing_intervals=_missing_intervals(start,end,segments,excluded))
    result['limitation_codes']+=list(dict.fromkeys(reason for _,_,reason in excluded))
    if result['missing_intervals']:
        result['limitation_codes'].append('INCOMPLETE_WINDOW_COVERAGE')
    if fraction<config.minimum_coverage_fraction:
        result['limitation_codes'].append('BELOW_MINIMUM_COVERAGE')
    mean=None
    if covered>0:
        complete=abs(fraction-1)<1e-10
        result['energy_status']='AVAILABLE' if complete else 'PARTIAL'
        result['covered_consumed_kwh']=imports
        result['consumed_kwh']=imports if complete else None
        result['import_kwh']=imports if complete else None
        result['export_kwh']=exports if complete and (config.method=='POWER' and config.power_sign=='IMPORT_POSITIVE' or config.counter_semantics=='CUMULATIVE_EXPORT') else None
        if config.method=='COUNTER' and config.counter_semantics=='CUMULATIVE_EXPORT':
            result['covered_consumed_kwh']=None;result['consumed_kwh']=None;result['import_kwh']=None
        if config.method=='POWER':
            mean=signed_power_integral/covered
        if loss_supported and complete:
            result['loss_kwh']=loss_energy
            result['loss_kw']=loss_energy/(covered/3600)
            result['efficiency_percent']=efficiency_percent(mean,result['loss_kw']) if mean is not None and mean>=0 else None
            result['loss_method']='APPROXIMATE_PHASE_RMS_I_SQUARED_V1'
            result['assumptions']+=['Energized transformer; delivered-output boundary: '+loss_model.output_boundary_reference,
                'Approximate P0 + Pr*K_I²; linear phase current, constant loss parameters; not measured loss']
            if result['efficiency_percent'] is None:
                result['limitation_codes'].append('POSITIVE_DELIVERED_POWER_REQUIRED')
        else:
            result['limitation_codes'].append('LOSS_PARAMETERS_BOUNDARY_OR_COVERAGE_INELIGIBLE')
    else:
        result['limitation_codes'].append('NO_SUPPORTED_INTERVALS')
    if config.power_semantics=='INSTANTANEOUS':
        for t,row in inside:
            if row.get('active_power_total') is not None and field_eligible(row.get('acquisition'),'active_power_total','kW'):
                result['load_profile'].append({'timestamp':iso(t),'active_power_total':float(row['active_power_total'])})
        if result['load_profile']:
            peak=max(result['load_profile'],key=lambda point:point['active_power_total'])
            result.update(peak_kw=peak['active_power_total'],peak_time=peak['timestamp'])
    if not result['load_profile']:
        result['limitation_codes'].append('INSTANTANEOUS_LOAD_PROFILE_UNAVAILABLE')
    overload_seconds=run_seconds=0.0
    previous_end=None
    for left,right in overload_segments:
        duration=(right-left).total_seconds()
        run_seconds=run_seconds+duration if previous_end==left else duration
        overload_seconds=max(overload_seconds,run_seconds);previous_end=right
    if config.overload_duration_seconds is not None and overload_seconds>=config.overload_duration_seconds:
        result['conservation_recommendation']='Operator review: sustained observed loading above the eligible configured rating; review duty and losses without automatic control.'
        result['conservation_evidence'].append(f'Both interval endpoints exceed configured rated kVA over {overload_seconds} covered seconds')
    if alternative_loss_model is not None:
        if not (is_synthetic and synthetic_parameters(loss_model) and synthetic_parameters(alternative_loss_model) and result['loss_kwh'] is not None
                and loss_model.measurement_side==alternative_loss_model.measurement_side
                and loss_model.output_boundary_reference==alternative_loss_model.output_boundary_reference):
            result['limitation_codes'].append('SIMULATED_EQUAL_SERVICE_COMPARISON_INELIGIBLE')
        else:
            alternative=analyze_energy(records,transformer_id,start,end,config,loss_model=alternative_loss_model).result
            if alternative['loss_kwh'] is not None and alternative['consumed_kwh']==result['consumed_kwh'] and alternative['coverage_seconds']==covered:
                difference=result['loss_kwh']-alternative['loss_kwh']
                if difference>0:
                    result['estimated_savings_kwh']=difference
                    result['conservation_recommendation']='Simulated opportunity only: operator review of fictional equal-delivered-service loss alternatives.'
                    result['conservation_evidence']+=[f'Baseline loss {result["loss_kwh"]} kWh; alternative loss {alternative["loss_kwh"]} kWh',
                        f'Same delivered service {result["consumed_kwh"]} kWh, same event-time horizon; no useful-load reduction']
                    result['assumptions'].append('Fictional loss configurations '+loss_model.version+' versus '+alternative_loss_model.version+'; not measured savings')
                else:
                    result['limitation_codes'].append('NO_POSITIVE_MODELLED_CONSERVATION_OPPORTUNITY')
            else:
                result['limitation_codes'].append('EQUAL_SERVICE_LOSS_COMPARISON_UNAVAILABLE')
    result['assumptions']=list(dict.fromkeys(result['assumptions']))
    result['limitation_codes']=list(dict.fromkeys(result['limitation_codes']))
    return EnergyAnalysis(result,mean)

def calculate_energy(records, transformer_id, window_start, window_end, config, **kwargs) -> EnergyResult:
    """H00-shaped resource; richer covered-duration summary stays outside the wire shape."""
    return analyze_energy(records,transformer_id,window_start,window_end,config,**kwargs).result
