"""H00 semantic-sha256-v1; Decimal JSON parsing preserves source precision."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal

PROTECTION = ('oil_temp_alarm', 'oil_temp_trip', 'magnetic_oil_gauge_alarm')
FIELDS = ('phase_voltage_l1', 'phase_voltage_l2', 'phase_voltage_l3',
          'current_l1', 'current_l2', 'current_l3', 'neutral_current',
          'oil_temperature', 'winding_temperature', 'ambient_temperature',
          'oil_level', *PROTECTION, 'active_power_total', 'apparent_power_total',
          'reactive_power_total', 'energy_kwh', 'power_factor_l1',
          'power_factor_l2', 'power_factor_l3')


def parse_record_json(value):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError(f'duplicate JSON key: {k}')
            result[k] = v
        return result
    def reject(value):
        raise ValueError(f'nonfinite JSON constant: {value}')
    return json.loads(value, parse_float=Decimal, object_pairs_hook=pairs,
                      parse_constant=reject)


def utc(value):
    import pandas as pd
    if isinstance(value, str) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', value):
        raise ValueError('aware ISO timestamp at microsecond precision required')
    t = pd.Timestamp(value)
    if t.tzinfo is None or t.nanosecond:
        raise ValueError('aware timestamp at microsecond precision required')
    return t.tz_convert(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def serialize(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        value.encode('utf-8')
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, (int, Decimal, float)):
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError('nonfinite number')
        if not number:
            return '0'
        result = format(number, 'f')
        return result.rstrip('0').rstrip('.') if '.' in result else result
    if isinstance(value, (list, tuple)):
        return '[' + ','.join(serialize(item) for item in value) + ']'
    if isinstance(value, dict):
        return '{' + ','.join(serialize(k) + ':' + serialize(value[k])
                              for k in sorted(value)) + '}'
    raise ValueError(f'unsupported JSON value: {type(value)}')


def normalized_payload(record):
    result = {'transformer_id': record['transformer_id'],
              'timestamp': utc(record['timestamp'])}
    for key in FIELDS:
        value = record.get(key)
        if key in PROTECTION and value is not None:
            if type(value) not in (bool, int) or value not in (0, 1):
                raise ValueError(f'invalid protection {key}')
            value = int(value)
        elif value is not None and (isinstance(value, bool) or
                                   not isinstance(value, (int, float, Decimal))):
            raise ValueError(f'invalid numeric measurement {key}')
        result[key] = value
    result['source_name'] = record.get('source_name')
    result['scenario_id'] = record.get('scenario_id')
    result['acquisition'] = copy.deepcopy(record.get('acquisition'))
    if result['acquisition'] is not None:
        result['acquisition'].pop('snapshot_id', None)
    return result


def canonical_bytes(record):
    return serialize(normalized_payload(record)).encode('utf-8')


def payload_hash(record):
    return hashlib.sha256(canonical_bytes(record)).hexdigest()
