"""H00 contract checks only; no application or service implementation.

Requires jsonschema 4.x. Exit 1 on any failure, 2 for missing dependency.
Uses decimal JSON parsing to avoid platform-dependent semantic hashing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTECTION = ('oil_temp_alarm', 'oil_temp_trip', 'magnetic_oil_gauge_alarm')
FIELDS = (
    'phase_voltage_l1', 'phase_voltage_l2', 'phase_voltage_l3', 'current_l1',
    'current_l2', 'current_l3', 'neutral_current', 'oil_temperature',
    'winding_temperature', 'ambient_temperature', 'oil_level', *PROTECTION,
    'active_power_total', 'apparent_power_total', 'reactive_power_total',
    'energy_kwh', 'power_factor_l1', 'power_factor_l2', 'power_factor_l3',
)
TIME_PATTERN = re.compile(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$'
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f'duplicate JSON key: {key}')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f'nonfinite JSON constant: {value}')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'), parse_float=Decimal,
                      object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def timestamp(value):
    require(isinstance(value, str) and TIME_PATTERN.fullmatch(value),
            f'aware timestamp at microsecond precision required: {value}')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.utcoffset() is not None, 'naive timestamp')
    return result.astimezone(timezone.utc)


def utc(value):
    return timestamp(value).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def serialize(value):
    """semantic-sha256-v1 canonical JSON bytes, without terminal newline."""
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        value.encode('utf-8')  # Reject unpaired surrogates.
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, (int, Decimal, float)):
        number = Decimal(str(value))
        require(number.is_finite(), 'nonfinite number')
        if not number:
            return '0'
        result = format(number, 'f')
        return result.rstrip('0').rstrip('.') if '.' in result else result
    if isinstance(value, list):
        return '[' + ','.join(serialize(item) for item in value) + ']'
    if isinstance(value, dict):
        return '{' + ','.join(serialize(k) + ':' + serialize(value[k])
                              for k in sorted(value)) + '}'
    raise ValueError(f'unsupported JSON value: {type(value)}')


def normalized_payload(record):
    """Projection includes all semantic fields; output/transport keys excluded.

    This is a hash oracle, not input validation. Source-body validation separately
    rejects received_at and transport keys before using this projection.
    """
    result = {'transformer_id': record['transformer_id'],
              'timestamp': utc(record['timestamp'])}
    for key in FIELDS:
        value = record.get(key)
        if key in PROTECTION and value is not None:
            require(type(value) in (bool, int) and value in (0, 1),
                    f'invalid protection {key}')
            value = int(value)
        elif value is not None:
            require(not isinstance(value, bool), f'boolean measurement {key}')
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


def semantic_telemetry(v, is_output=False):
    timestamp(v['timestamp'])
    for key in FIELDS:
        value = v.get(key)
        if key in PROTECTION:
            require(value is None or (type(value) in (bool, int) and value in (0, 1)),
                    f'{key}: strict protection type')
        else:
            require(value is None or (not isinstance(value, bool) and
                    isinstance(value, (int, float, Decimal))), f'{key}: numeric type')
    a = v.get('acquisition')
    if a:
        if v.get('source_name') is not None:
            require(v['source_name'] == a['source_name'], 'source name mismatch')
        simulated_origin = a['source_kind'] == 'SIMULATED' or (
            a['source_kind'] == 'REPLAYED' and a['origin_kind'] == 'SIMULATED')
        require(a['timezone_status'] != 'UNKNOWN', 'unknown timezone must be staged')
        if a['timezone_status'] == 'DECLARED_UTC':
            require(simulated_origin, 'declared UTC requires synthetic source')
        if a['timezone_status'] == 'ASSUMED':
            require(a['source_kind'] == 'REPLAYED' and
                    a['timestamp_origin'] == 'REPLAY_ASSUMPTION', 'undeclared assumption')
        if a['source_kind'] == 'REPLAYED':
            require(a['origin_transformer_id'] != v['transformer_id'],
                    'replay destination equals origin')
        for key in FIELDS:
            unit = a['field_units'][key]
            verification = a['field_verification'][key]
            require(verification != 'SYNTHETIC' or simulated_origin,
                    f'synthetic verification on real source: {key}')
            require(unit != 'UNKNOWN' or verification == 'UNVERIFIED',
                    f'unknown verified unit: {key}')
        if a['snapshot_id'] is not None:
            require(a['snapshot_id'] == payload_hash(v), 'forged snapshot hash')
    if is_output:
        for key in PROTECTION:
            require(v.get(key) is None or type(v[key]) is int,
                    'stored/read protection must be integer')


def populated_leaves(value, prefix=''):
    for key, item in value.items():
        if key in ('id', 'name', 'schema_version', 'created_at', 'updated_at',
                   'configuration_metadata'):
            continue
        path = prefix + key
        if isinstance(item, dict):
            yield from populated_leaves(item, path + '.')
        elif item is not None:
            yield path


def semantic_asset(v):
    meta = v.get('configuration_metadata')
    if not meta:
        return  # Legacy evidence is unknown, not silently verified.
    entries = meta['field_metadata']
    for path in populated_leaves(v):
        require(path in entries, f'configuration provenance missing: {path}')
        f = entries[path]
        if f['verification'] == 'VERIFIED':
            require(bool(f['evidence_reference']), f'verification evidence missing: {path}')
        if meta['status'] in ('VERIFIED', 'SYNTHETIC_CONFIG'):
            require(f['verification'] == meta['status'], 'mixed aggregate verification')
        units = {'rated_voltage_hv':'V','rated_voltage_lv':'V','rated_power_kva':'kVA',
                 'rated_current_a':'A','rated_frequency_hz':'Hz','impedance_percent':'percent'}
        if path in units and f['verification'] != 'UNVERIFIED':
            require(f['unit'] == units[path], f'configuration unit mismatch: {path}')


def semantic_analytics(v):
    require(v.get('anomaly_flag') is None or type(v['anomaly_flag']) is bool,
            'anomaly flag requires boolean')
    meta = v.get('metadata') or {}
    f = meta.get('forecast')
    if f and (f['release_status'] != 'RELEASED' or not f['operational_eligible']):
        require(all(v.get(k) is None for k in
                    ('fault_risk', 'predicted_fault', 'prediction_confidence')),
                'unreleased operational forecast must be null')
    if v.get('schema_version') == '1.1.0' and not f:
        require(v.get('fault_risk') is None, 'no release evidence')
    if v.get('rul'):
        semantic_rul(v['rul'])
    c = meta.get('coverage')
    if c and c['expected_seconds']:
        close(c['fraction'], c['covered_seconds']/c['expected_seconds'])


def semantic_rul(v):
    require(v['simulated'] or v['rul_status'] != 'SIMULATED_ESTIMATE',
            'unlabelled synthetic RUL')
    if v['simulated']:
        require(v['source_kind'] in ('SIMULATED', 'REPLAYED'), 'synthetic real RUL')
    if v['rul_status'] in ('INSUFFICIENT_DATA', 'NO_CROSSING_WITHIN_HORIZON'):
        require(all(v[k] is None for k in ('rul_value','rul_lower','rul_upper')),
                'unsupported finite RUL')
    if v['required_inputs']:
        require(v['rul_value'] is None, 'missing RUL prerequisites')
    if v['rul_value'] is not None:
        if v['forecast_horizon_hours'] is not None:
            require(v['rul_value'] <= v['forecast_horizon_hours'], 'crossing beyond horizon')
        if v['rul_lower'] is not None:
            require(v['rul_lower'] <= v['rul_value'] <= v['rul_upper'], 'unordered RUL range')
            require(v['uncertainty_kind'] is not None, 'unlabelled uncertainty')


def semantic_energy(v):
    duration = (timestamp(v['window_end'])-timestamp(v['window_start'])).total_seconds()
    require(duration > 0, 'unbounded energy window')
    require(v['coverage_seconds'] <= duration, 'excess coverage')
    close(v['coverage_fraction'], float(v['coverage_seconds'])/duration)
    if v['coverage_fraction'] < v['provenance']['minimum_coverage_fraction']:
        require(v['consumed_kwh'] is None, 'unsupported total at deficient coverage')
    if v['energy_method'] == 'SIMULATED':
        require(v['source_kind'] in ('SIMULATED','REPLAYED'), 'unlabelled simulated energy')
    if v['energy_method'] == 'MEASURED_COUNTER':
        require(v['calculation_method'] == 'COUNTER_DIFFERENCE', 'counter method mismatch')
    if v['energy_method'] == 'CALCULATED_POWER':
        require(v['calculation_method'] == 'TRAPEZOID', 'power method mismatch')
    if v['energy_status'] == 'AVAILABLE':
        require(v['consumed_kwh'] is not None, 'available energy lacks supported value')
    if v['calculation_method'] == 'TRAPEZOID':
        known = v['provenance']['power_unit'] == 'kW' and v['active_power_unit_status'] in ('SYNTHETIC','VERIFIED')
    elif v['calculation_method'] == 'COUNTER_DIFFERENCE':
        known = v['provenance']['counter_unit'] == 'kWh' and v['provenance']['counter_semantics'] is not None
    else:
        known = False
    require(known or (v['consumed_kwh'] is None and v['covered_consumed_kwh'] is None),
            'unknown units/semantics yielded energy')
    for interval in v['missing_intervals']:
        require(timestamp(v['window_start']) <= timestamp(interval['start']) <
                timestamp(interval['end']) <= timestamp(v['window_end']), 'invalid missing interval')
    if v['timestamp'] is not None:
        require(timestamp(v['window_start']) <= timestamp(v['timestamp']) <=
                timestamp(v['window_end']), 'energy result time outside bounds')


def semantic_receipt(v):
    if 'error' in v:
        return
    require(v['snapshot_id'] == v['payload_hash'], 'receipt hash/ID mismatch')
    require(v['accepted_snapshot_id'] == v['accepted_payload_hash'], 'accepted ID/hash mismatch')
    if v['receipt_status'] == 'COMMITTED':
        require(v['accepted_snapshot_id'] == v['snapshot_id'], 'committed reference mismatch')
        require(timestamp(v['committed_at']) >= timestamp(v['received_at']), 'commit before receipt')
    else:
        require(v['accepted_snapshot_id'] != v['snapshot_id'], 'conflict points to same hash')
    require(v['analytics_status'] != 'UNAVAILABLE' or v['state_coverage_loss'],
            'unavailable ML requires coverage-loss disclosure')


def semantic_map(v):
    mappings = [(a['endpoint'], a['unit_id']) for a in v['assets']]
    require(len(mappings) == len(set(mappings)), 'duplicate endpoint/unit mapping')
    require(len({a['transformer_id'] for a in v['assets']}) == len(v['assets']),
            'asset mapped twice')
    require(set(e['field'] for e in v['entries']) == set(FIELDS) | {'timestamp','sequence','map_version'},
            'incomplete register requirements')
    if v['status'] == 'READY':
        require(not v['blocked_details'], 'ready map has blockers')
        for e in v['entries']:
            require(all(e[k] is not None for k in ('address_zero_based','register_count',
                    'data_type','byte_order','word_order','multiplier','quality_bit')), 'unfinished ready map')


def semantics(name, v):
    if name == 'telemetry': semantic_telemetry(v)
    elif name == 'asset': semantic_asset(v)
    elif name == 'analytics': semantic_analytics(v)
    elif name == 'rul':
        require((v['rul'] is None) == (v['timestamp'] is None), 'RUL timestamp/null mismatch')
        if v['rul']:
            require(timestamp(v['timestamp']) == timestamp(v['rul']['timestamp']), 'RUL identity time')
            semantic_rul(v['rul'])
    elif name == 'energy': semantic_energy(v)
    elif name == 'receipt': semantic_receipt(v)
    elif name == 'ingestion-outcome':
        if v['ingestion_outcome'] != 'ACCEPTED':
            require(not v['forward_state_advanced'], 'retry/conflict/late advanced state')
        if v['ingestion_outcome'] in ('CONFLICT','REJECTED_LATE_OBSERVATION'):
            require(v['http_status'] == 409 and v['analytics'] is None, 'rejected record inferred')
    elif name == 'checkpoint':
        require(v['last_snapshot_id'] == v['last_payload_hash'], 'checkpoint last identity')
        if v['lifecycle_status'] == 'READY':
            require(all(v['state'][k]['payload'] is not None for k in
                        ('thermal','history','anomaly_persistence','health_persistence','maintenance_persistence')),
                    'ready checkpoint lacks recoverable state')
    elif name == 'register-map': semantic_map(v)
    elif name == 'latest':
        semantic_asset(v['transformer'])
        if v['telemetry']: semantic_telemetry(v['telemetry'], is_output=True)
        if v['analytics']: semantic_analytics(v['analytics'])
        availability = v.get('analytics_availability')
        if availability and availability['status'] == 'UNAVAILABLE':
            require(v['analytics'] is None and availability['state_coverage_loss'],
                    'unavailable latest hides coverage loss')


def close(actual, expected):
    if actual is None or expected is None:
        require(actual is expected, f'null mismatch {actual} vs {expected}')
    else:
        require(math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9),
                f'arithmetic mismatch {actual} vs {expected}')


def energy_oracle(case):
    v = case['expected']
    if v['calculation_method'] == 'NONE':
        close(v['consumed_kwh'], None)
        close(v['covered_consumed_kwh'], None)
        return
    total, seconds, gaps, resets = Decimal(0), 0, 0, 0
    accepted = {}
    for t, power in case['samples']:
        t = timestamp(t)
        if t in accepted:
            require(accepted[t] == power, 'conflicting arithmetic sample')
        accepted[t] = power
    samples = sorted(accepted.items())
    for (t0,p0),(t1,p1) in zip(samples,samples[1:]):
        dt = (t1-t0).total_seconds()
        require(timestamp(v['window_start']) <= t0 < t1 <= timestamp(v['window_end']),
                'oracle outside window')
        if dt > v['provenance']['maximum_gap_seconds'] and not (
                v['calculation_method'] == 'COUNTER_DIFFERENCE' and v['provenance']['continuity_evidence']):
            gaps += 1
            continue
        if p0 is None or p1 is None:
            gaps += 1
            continue
        if v['calculation_method'] == 'COUNTER_DIFFERENCE':
            delta = p1-p0
            if delta < 0:
                resets += 1
                continue
        else:
            delta = (Decimal(str(p0))+Decimal(str(p1)))/2 * Decimal(str(dt))/3600
        total += delta
        seconds += dt
    close(v['coverage_seconds'], seconds)
    close(v['gap_count'], gaps)
    close(v['reset_count'], resets)
    close(v['covered_consumed_kwh'], total if seconds else None)
    if v['coverage_fraction'] >= v['provenance']['minimum_coverage_fraction'] and seconds:
        close(v['consumed_kwh'], total)
    else:
        close(v['consumed_kwh'], None)


def resolved_window(query, now, latest, maximum_days):
    durations = {'1h':1,'6h':6,'24h':24,'7d':168}
    window = query.get('window','1h')
    require(window in durations, 'invalid window')
    anchor = query.get('anchor','now')
    require(anchor in ('latest','now'), 'invalid anchor')
    end = timestamp(query['to']) if 'to' in query else (
        timestamp(latest) if anchor == 'latest' and 'from' not in query and latest else timestamp(now))
    start = timestamp(query['from']) if 'from' in query else end-timedelta(hours=durations[window])
    require(start < end and end-start <= timedelta(days=maximum_days), 'invalid bounds')
    return start,end


def main():
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError:
        print('BLOCKED: jsonschema is required (install 4.x or set PYTHONPATH).', file=sys.stderr)
        return 2
    files = sorted(HERE.glob('*.json'))
    for path in files:
        completed = subprocess.run([sys.executable,'-m','json.tool',str(path)],
                                   stdout=subprocess.DEVNULL, capture_output=False)
        require(completed.returncode == 0, f'json.tool failed: {path.name}')
        load(path)  # json.tool alone accepts NaN and duplicate keys.
    print(f'PASS json.tool and strict JSON parsing: {len(files)} files')
    validators = {}
    for path in HERE.glob('*.schema.json'):
        schema = load(path)
        Draft202012Validator.check_schema(schema)
        validators[path.name] = Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(name, payload):
        validators[name+'.schema.json'].validate(payload)
        semantics(name,payload)

    coverage = {name: set() for name in validators}
    examples = load(HERE/'examples.json')
    for example in examples:
        name = example['schema'].removesuffix('.schema.json')
        if example['valid']:
            validate(name,example['payload'])
        else:
            try:
                validate(name,example['payload'])
            except Exception as exc:
                # Restrict expected rejection to validator/semantic errors.
                from jsonschema.exceptions import ValidationError
                require(isinstance(exc,(ValueError,ValidationError)),
                        f'unexpected negative-case failure: {exc}')
            else:
                raise ValueError('invalid example accepted: '+example['name'])
        coverage[example['schema']].add(example['valid'])
    require(all(v == {True,False} for v in coverage.values()), 'schema lacks valid/invalid pair')
    print(f'PASS {len(validators)} Draft 2020-12 schemas; {len(examples)} positive/negative examples')

    oracles = load(HERE/'oracles.json')
    for case in oracles['rul']:
        validate('rul',case['expected'])
        v = case['expected']['rul']
        if case['oracle_kind'] == 'ARITHMETIC':
            d,end,g,h = (v[k] for k in ('degradation_state','end_threshold',
                                       'degradation_rate_per_hour','forecast_horizon_hours'))
            time = Decimal(0) if d >= end else (end-d)/g if g else None
            if time is not None and time > h:
                time = None
            close(v['rul_value'],time)
            if 'rate_bounds_per_hour' in case:
                low_rate, high_rate = case['rate_bounds_per_hour']
                close(v['rul_lower'], (end-d)/high_rate)
                close(v['rul_upper'], (end-d)/low_rate)
        else:
            close(v['rul_value'],None)
            require(v['required_inputs'], 'real insufficiency must identify prerequisites')
    for case in oracles['energy']:
        validate('energy',case['expected'])
        energy_oracle(case)
    print(f"PASS RUL/energy arithmetic and eligibility: {len(oracles['rul'])+len(oracles['energy'])} cases")

    traces = load(HERE/'traces.json')
    registered = {e['payload']['id'] for e in examples if e['valid'] and e['schema']=='asset.schema.json'}
    for trace in traces:
        identities, latest, outcomes, advances = {}, {}, [], 0
        for record in trace['records']:
            validate('telemetry',record)
            require(record['transformer_id'] in registered, 'unregistered fixture asset')
            identity = record['transformer_id'],utc(record['timestamp'])
            h = payload_hash(record)
            if identity in identities:
                outcome = 'EXACT_RETRY' if identities[identity] == h else 'CONFLICT'
            elif identity[0] in latest and timestamp(record['timestamp']) < latest[identity[0]]:
                outcome = 'REJECTED_LATE_OBSERVATION'
            else:
                outcome = 'ACCEPTED'
                identities[identity] = h
                latest[identity[0]] = timestamp(record['timestamp'])
                advances += 1
            outcomes.append(outcome)
        require(outcomes == trace['expected_outcomes'], 'trace ingestion outcome mismatch')
        if 'state_advances' in trace['oracle']:
            require(advances == trace['oracle']['state_advances'], 'duplicate state advancement')
        if 'loading_percent' in trace['oracle']:
            for record in trace['records']:
                close(100*record['apparent_power_total']/100, trace['oracle']['loading_percent'])
                require(math.isclose(math.sqrt(3)*400*float(record['current_l1'])/1000,
                        float(record['apparent_power_total']), rel_tol=1e-6),
                        'fictional balanced power/current mismatch')
    print(f'PASS ingestion traces and isolated asset identities: {len(traces)} traces')

    vectors = load(HERE/'hash-vectors.json')
    for vector in vectors:
        for record in vector['equivalent_inputs']:
            require(canonical_bytes(record).decode('utf-8') == vector['canonical_utf8'],
                    'canonical byte vector mismatch: '+vector['name'])
            require(payload_hash(record) == vector['sha256'], 'hash vector mismatch')
        for record in vector['different_inputs']:
            require(payload_hash(record) != vector['sha256'], 'semantic conflict hashed equally')
    require(payload_hash({**examples[0]['payload'],'oil_temp_trip':None}) !=
            payload_hash({**examples[0]['payload'],'oil_temp_trip':0}), 'null collapsed to zero')
    require(serialize(Decimal('-0.00')) == '0' and serialize(Decimal('1e1')) == '10',
            'numeric normalization')
    for bad in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}'):
        try:
            json.loads(bad,object_pairs_hook=unique_pairs,parse_constant=reject_constant)
        except ValueError:
            pass
        else:
            raise ValueError('invalid strict JSON accepted')
    print(f'PASS deterministic semantic hashes: {len(vectors)} vectors, exclusions/null/normalization')

    queries = load(HERE/'query-cases.json')
    for case in queries['cases']:
        start,end = resolved_window(case['query'],queries['clock_now'],
                                   case.get('latest_event',queries['latest_event']),
                                   queries['maximum_window_days'])
        require(start == timestamp(case['start']) and end == timestamp(case['end']),
                'window resolution mismatch')
    for query in queries['invalid']:
        try:
            resolved_window(query,queries['clock_now'],queries['latest_event'],
                            queries['maximum_window_days'])
        except ValueError:
            pass
        else:
            raise ValueError('invalid query accepted')
    print('PASS bounded event-time query cases')
    count = 0
    for path in [ROOT/'docs/contracts/hackathon-v1.1.md',HERE/'README.md',HERE/'VALIDATION.md']:
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                require((path.parent/target.split('#')[0]).resolve().exists(),
                        f'broken local documentation link: {path.name}: {target}')
                count += 1
    print(f'PASS local documentation links: {count}')
    print('PASS H00 focused checks. Owner review and future integration remain pending.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'FAIL: {type(error).__name__}: {error}', file=sys.stderr)
        sys.exit(1)
