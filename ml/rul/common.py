"""H05 evidence helpers; H01 remains the sole semantic identity implementation."""
from __future__ import annotations
import math
from datetime import datetime, timezone
from decimal import Decimal

def finite(value, *, minimum=None, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError('finite numeric value required')
    value = float(value)
    if not math.isfinite(value) or (minimum is not None and value < minimum) or (positive and value <= 0):
        raise ValueError('invalid numeric range')
    return value

def event_time(value):
    from ml.pipeline.identity import utc
    return datetime.fromisoformat(utc(value).replace('Z', '+00:00'))

def iso(value):
    return event_time(value).isoformat(timespec='microseconds').replace('+00:00','Z')

def synthetic(acquisition):
    a = acquisition or {}
    return a.get('source_kind') == 'SIMULATED' or (a.get('source_kind') == 'REPLAYED' and a.get('origin_kind') == 'SIMULATED')

def lineage(acquisition):
    a = acquisition or {}
    return {key: a.get(key) for key in ('source_kind','source_name','origin_kind','origin_transformer_id','replay_run_id','measurement_side','map_version')}

def field_eligible(acquisition, field, unit):
    a = acquisition or {}
    verification = a.get('field_verification',{}).get(field)
    return a.get('timezone_status') in ('VERIFIED','DECLARED_UTC','ASSUMED') and a.get('field_units',{}).get(field) == unit and (
        verification == 'VERIFIED' or (verification == 'SYNTHETIC' and synthetic(a)))

def validate_source(record):
    a = record.get('acquisition') or {}
    if not a:
        return
    if a.get('source_kind') not in ('SIMULATED','REPLAYED','LIVE'):
        raise ValueError('unsupported source kind')
    if a.get('source_kind') == 'REPLAYED' and (not a.get('replay_run_id') or not a.get('origin_transformer_id') or a['origin_transformer_id'] == record['transformer_id']):
        raise ValueError('separate replay identity and lineage required')
    if any(v == 'SYNTHETIC' for v in a.get('field_verification',{}).values()) and not synthetic(a):
        raise ValueError('synthetic verification cannot authorize live inputs')
    if a.get('timezone_status') == 'DECLARED_UTC' and not synthetic(a):
        raise ValueError('declared UTC requires synthetic origin')
    if a.get('timezone_status') == 'ASSUMED' and (a.get('source_kind') != 'REPLAYED' or a.get('timestamp_origin') != 'REPLAY_ASSUMPTION'):
        raise ValueError('undeclared replay timezone assumption')
    if record.get('source_name') and record['source_name'] != a.get('source_name'):
        raise ValueError('source names disagree')
