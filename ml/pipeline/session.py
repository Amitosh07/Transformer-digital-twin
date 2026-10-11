"""Backend-controlled candidate/checkpoint lifecycle; no database side effects.

Call prepare, persist its checkpoint with telemetry/analytics/receipt, then install
with database_committed=True. A rollback must discard. Each session belongs to a
single backend worker; H02 must serialize durable asset transactions across workers.
"""
from __future__ import annotations

import copy
import dataclasses
import math
import json
import re
import threading
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from ml.pipeline.asset_config import AssetConfig
from ml.pipeline.identity import utc, payload_hash
from ml.pipeline.orchestrator import UnifiedMLPipeline
from ml.pipeline.state import AssetPipelineState

CHECKPOINT_VERSION = '1.0.0'
STATE_VERSION = '1.0.0'
CONTRACT_VERSION = '1.1.0'
CATEGORIES = {'thermal': 'thermal_state', 'anomaly_persistence': 'anomaly_state',
              'health_persistence': 'health_state', 'maintenance_persistence': 'maintenance_state'}


class CheckpointCompatibilityError(ValueError):
    pass


class CandidateStateError(ValueError):
    pass


def encode(value):
    """JSON only: tagged timestamps/decimals, enum values, native scalar dtypes."""
    # Native JSON scalars dominate persisted history. Dispatch them before the
    # timestamp/dataclass checks without changing tagged dtype serialization.
    kind = type(value)
    if kind in (str, int, bool, type(None)):
        return value
    if kind is float:
        if not math.isfinite(value):
            raise ValueError('nonfinite checkpoint value')
        return value
    if kind is dict:
        return {k: encode(v) for k, v in value.items()}
    if kind in (list, tuple):
        return [encode(v) for v in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return {'$utc': utc(value)}
    if isinstance(value, Decimal):
        return {'$decimal': str(value)}
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value):
        return {f.name: encode(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite checkpoint value')
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError(f'unsupported checkpoint dtype: {type(value)}')


def decode(value):
    if isinstance(value, dict):
        if set(value) == {'$utc'}:
            return pd.Timestamp(utc(value['$utc']))
        if set(value) == {'$decimal'}:
            d = Decimal(value['$decimal'])
            if not d.is_finite():
                raise ValueError('nonfinite checkpoint decimal')
            return d
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def restore_dataclass(target, payload):
    if not isinstance(payload, dict) or set(payload) != {f.name for f in dataclasses.fields(target)}:
        raise CheckpointCompatibilityError('incompatible state fields')
    for name, value in payload.items():
        previous = getattr(target, name)
        if dataclasses.is_dataclass(previous):
            restore_dataclass(previous, value)
        else:
            if isinstance(previous, bool) and type(value) is not bool:
                raise CheckpointCompatibilityError(f'invalid boolean state: {name}')
            if isinstance(previous, list) and not isinstance(value, list):
                raise CheckpointCompatibilityError(f'invalid list state: {name}')
            setattr(target, name, value)


@dataclasses.dataclass(frozen=True)
class PreparedInference:
    candidate_id: str
    transformer_id: str
    outcome: str
    result: dict[str, Any] | None
    checkpoint: dict[str, Any] | None
    ingestion: dict[str, Any]


class PipelineSession:
    def __init__(self, pipeline=None):
        self.pipeline = pipeline or UnifiedMLPipeline()
        self._encoded_identity_cache = {}
        self._pending = {}
        self._revisions = {}
        self._restore_failures = set()
        self._lock = threading.RLock()

    def _versions(self, config):
        b = self.pipeline.bundle
        return {'bundle_id': b.bundle_id, 'contract_version': CONTRACT_VERSION,
                'feature_version': b.feature_version, 'model_version': b.model_version,
                'preprocessing_version': b.preprocessing_version,
                'configuration_version': config.configuration_version}

    def _checkpoint(self, state, config):
        if state.last_processed_timestamp is None:
            return None
        previous = self._encoded_identity_cache.get(state.transformer_id, {})
        cached = {}
        identity_payload = {}
        for key, entry in state.identity_cache.items():
            old = previous.get(key)
            encoded = old[1] if old is not None and old[0] is entry else json.dumps(encode(entry), allow_nan=False)
            cached[key] = (entry, encoded)
            # Cached bytes are immutable. Each envelope receives a fresh JSON tree,
            # so caller review edits cannot poison committed state or later exports.
            identity_payload[key] = json.loads(encoded)
        self._encoded_identity_cache[state.transformer_id] = cached
        categories = {name: {'state_version': STATE_VERSION, 'payload': encode(getattr(state, attr))}
                      for name, attr in CATEGORIES.items()}
        categories.update({
            'history': {'state_version': STATE_VERSION, 'payload': {
                'records': encode(state.history_records), 'identity_cache': identity_payload,
                'max_history_rows': state.max_history_rows}},
            'synthetic_degradation': {'state_version': STATE_VERSION,
                                      'payload': encode(state.synthetic_degradation)},
            'coverage': {'state_version': STATE_VERSION, 'payload': {
                'history_capped': state.history_capped,
                'protection_context_unknown': state.protection_context_unknown,
                'configuration_fingerprint': config.fingerprint,
                'artifact_digest': self.pipeline.bundle.artifact_digest,
                'bundle_configuration_fingerprint': self.pipeline.bundle.configuration_fingerprint,
                'artifact_schema_version': self.pipeline.bundle.schema_version,
                'coverage': state.coverage(state.last_processed_timestamp)}}})
        return {'checkpoint_version': CHECKPOINT_VERSION, 'transformer_id': state.transformer_id,
                'committed_event_time': utc(state.last_processed_timestamp),
                'last_snapshot_id': state.last_snapshot_id, 'last_payload_hash': state.last_payload_hash,
                'versions': self._versions(config), 'lifecycle_status': state.lifecycle_status,
                'state': categories, 'last_result': copy.deepcopy(state.last_result),
                'observation_count': state.observation_count}

    def prepare(self, transformer, record, history=()):
        config = transformer if isinstance(transformer, AssetConfig) else AssetConfig.from_dict(transformer)
        asset = config.transformer_id
        with self._lock:
            if asset in self._restore_failures:
                raise CheckpointCompatibilityError('asset quarantined after failed restore; compatible checkpoint required')
            # Owning runners receive explicit states; they never use internal asset caches.
            staging = UnifiedMLPipeline(self.pipeline.bundle, self.pipeline.asset_configs)
            staging.register_asset(config)
            if asset in self.pipeline._asset_states:
                committed = self.pipeline._asset_states[asset]
                # Past identity entries are append-only values: processing reads
                # them or replaces/removes dictionary keys, never edits entries.
                # Copy the dictionary and all mutable component/history state,
                # retaining these private immutable values. Review/checkpoint
                # results remain independently copied/encoded below.
                memo = {id(entry): entry for entry in committed.identity_cache.values()}
                # Accepted telemetry dictionaries are also append-only; rolling
                # retention replaces/slices the list, not the historical rows.
                memo.update({id(row): row for row in committed.history_records})
                staging._asset_states[asset] = copy.deepcopy(committed, memo)
            staging.hydrate_history(config, record, history)
            before = staging._asset_states.get(asset)
            prior = (before.identity_cache.get(pd.Timestamp(record['timestamp']).tz_convert('UTC').isoformat())
                     if before is not None else None)
            result = staging.process_record(record, config)
            if 'ingestion_outcome' in result:
                return PreparedInference('', asset, result['ingestion_outcome'], None, None, result)
            state = staging._asset_states[asset]
            outcome = 'EXACT_RETRY' if prior is not None else 'ACCEPTED'
            if outcome == 'EXACT_RETRY':
                config = self.pipeline.asset_configs.get(asset) or config
            checkpoint = self._checkpoint(state, config)
            token = uuid.uuid4().hex
            self._pending[token] = (asset, self._revisions.get(asset, 0), state, config, outcome, copy.deepcopy(result))
            ingestion = {'schema_version': CONTRACT_VERSION, 'transformer_id': asset,
                         'timestamp': utc(record['timestamp']), 'snapshot_id': state.last_snapshot_id
                         if outcome == 'ACCEPTED' else payload_hash(record),
                         'ingestion_outcome': outcome, 'http_status': 201 if outcome == 'ACCEPTED' else 200,
                         'forward_state_advanced': False, 'analytics': copy.deepcopy(result), 'reason': None}
            return PreparedInference(token, asset, outcome, copy.deepcopy(result), checkpoint, ingestion)

    def install(self, candidate, *, database_committed=False):
        """Caller attests successful commit; this method does not verify a database."""
        with self._lock:
            if database_committed is not True:
                raise CandidateStateError('backend must confirm successful database commit')
            pending = self._pending.get(candidate.candidate_id)
            if pending is None:
                raise CandidateStateError('unknown, discarded, rejected, or already installed candidate')
            asset, revision, state, config, outcome, result = pending
            if asset in self._restore_failures:
                raise CheckpointCompatibilityError('failed restore quarantines pending candidates')
            if revision != self._revisions.get(asset, 0):
                raise CandidateStateError('stale candidate; serialize/retry the asset transaction')
            if outcome == 'ACCEPTED':
                self.pipeline._asset_states[asset] = state
                self.pipeline.register_asset(config)
                self._revisions[asset] = revision + 1
            del self._pending[candidate.candidate_id]
            return copy.deepcopy(result)

    def discard(self, candidate):
        with self._lock:
            self._pending.pop(candidate.candidate_id, None)

    def export_checkpoint(self, transformer_id):
        with self._lock:
            state = self.pipeline._asset_states.get(transformer_id)
            if state is None:
                return None
            config = self.pipeline.asset_configs.get(transformer_id) or AssetConfig(transformer_id)
            return self._checkpoint(state, config)

    def import_checkpoint(self, checkpoint, transformer):
        """Validate completely before replacing state; failure preserves existing latches."""
        config = transformer if isinstance(transformer, AssetConfig) else AssetConfig.from_dict(transformer)
        with self._lock:
            try:
                c = copy.deepcopy(checkpoint)
                required = {'checkpoint_version', 'transformer_id', 'committed_event_time',
                    'last_snapshot_id', 'last_payload_hash', 'versions', 'lifecycle_status',
                    'state', 'last_result', 'observation_count'}
                if set(c) != required or c['checkpoint_version'] != CHECKPOINT_VERSION or c['versions'] != self._versions(config) or c['transformer_id'] != config.transformer_id:
                    raise CheckpointCompatibilityError('incompatible checkpoint/schema/model/configuration versions')
                expected = set(CATEGORIES) | {'history', 'coverage', 'synthetic_degradation'}
                if set(c['state']) != expected or any(set(v) != {'state_version', 'payload'} or v['state_version'] != STATE_VERSION for v in c['state'].values()):
                    raise CheckpointCompatibilityError('incompatible state categories/extension versions')
                coverage = c['state']['coverage']['payload']
                if type(coverage['history_capped']) is not bool or type(coverage['protection_context_unknown']) is not bool:
                    raise CheckpointCompatibilityError('invalid coverage/protection flags')
                if coverage['configuration_fingerprint'] != config.fingerprint or coverage['artifact_digest'] != self.pipeline.bundle.artifact_digest or coverage['artifact_schema_version'] != self.pipeline.bundle.schema_version:
                    raise CheckpointCompatibilityError('configuration/artifact content changed')
                if coverage['bundle_configuration_fingerprint'] != self.pipeline.bundle.configuration_fingerprint:
                    raise CheckpointCompatibilityError('ML runtime configuration changed')
                if c['lifecycle_status'] not in ('READY', 'WARMING_UP', 'REINITIALIZED', 'COVERAGE_LOSS') or type(c['observation_count']) is not int or c['observation_count'] < 0:
                    raise CheckpointCompatibilityError('invalid lifecycle/count')
                if any(not isinstance(c[k], str) or not re.fullmatch('[0-9a-f]{64}', c[k]) for k in ('last_snapshot_id', 'last_payload_hash')) or c['last_snapshot_id'] != c['last_payload_hash']:
                    raise CheckpointCompatibilityError('invalid semantic identity')
                state = AssetPipelineState(config.transformer_id, self.pipeline.bundle.bundle_id,
                    self.pipeline.bundle.schema_version, self.pipeline.bundle.feature_version,
                    self.pipeline.bundle.model_version)
                for name, attr in CATEGORIES.items():
                    restore_dataclass(getattr(state, attr), decode(c['state'][name]['payload']))
                    if getattr(state, attr).transformer_id != config.transformer_id:
                        raise CheckpointCompatibilityError('mixed asset checkpoint')
                h = decode(c['state']['history']['payload'])
                if type(h['max_history_rows']) is not int or not 721 <= h['max_history_rows'] <= 4096:
                    raise CheckpointCompatibilityError('unsafe history count cap')
                state.max_history_rows = h['max_history_rows']
                state.history_records = h['records']
                state.identity_cache = h['identity_cache']
                if len(state.history_records) > state.max_history_rows or len(state.identity_cache) > state.max_history_rows:
                    raise CheckpointCompatibilityError('history exceeds cap')
                state.last_processed_timestamp = pd.Timestamp(utc(c['committed_event_time']))
                for name, attr in CATEGORIES.items():
                    component = getattr(state, attr)
                    if component.last_timestamp is not None and (not isinstance(component.last_timestamp, pd.Timestamp) or component.last_timestamp > state.last_processed_timestamp):
                        raise CheckpointCompatibilityError('invalid component event time')
                if state.thermal_state.parameter_version != self.pipeline.bundle.thermal_config.parameter_version:
                    raise CheckpointCompatibilityError('thermal state parameter version mismatch')
                for name in ('last_model_temperature', 'last_forcing', 'warmup_elapsed_hours'):
                    value = getattr(state.thermal_state, name)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                        raise CheckpointCompatibilityError('invalid numeric thermal state')
                if state.maintenance_state.trip_latched and not isinstance(state.maintenance_state.latched_at, pd.Timestamp):
                    raise CheckpointCompatibilityError('latched protection requires event time')
                times = [pd.Timestamp(utc(r['timestamp'])) for r in state.history_records]
                if not times or times != sorted(set(times)) or times[-1] != state.last_processed_timestamp or any(r['transformer_id'] != config.transformer_id for r in state.history_records):
                    raise CheckpointCompatibilityError('invalid causal history')
                if payload_hash(state.history_records[-1]) != c['last_payload_hash']:
                    raise CheckpointCompatibilityError('checkpoint history/hash mismatch')
                state.last_payload_hash, state.last_snapshot_id = c['last_payload_hash'], c['last_snapshot_id']
                state.last_result, state.observation_count = c['last_result'], c['observation_count']
                state.lifecycle_status = c['lifecycle_status']
                state.configuration_fingerprint = config.fingerprint
                state.history_capped = coverage['history_capped']
                state.protection_context_unknown = coverage['protection_context_unknown']
                state.synthetic_degradation = decode(c['state']['synthetic_degradation']['payload'])
                if state.synthetic_degradation is not None:
                    from ml.rul.model import validate_extension
                    scenario = config.additional_configuration.get('synthetic_rul')
                    if scenario is None:
                        raise CheckpointCompatibilityError('synthetic checkpoint requires its explicit scenario')
                    validate_extension(state.synthetic_degradation, scenario, state.history_records[-1])
                    if (state.last_result.get('rul') or {}).get('degradation_state') != state.synthetic_degradation['degradation']:
                        raise CheckpointCompatibilityError('degradation/result mismatch')
                elif (state.last_result.get('rul') or {}).get('simulated') and config.additional_configuration.get('synthetic_rul'):
                    raise CheckpointCompatibilityError('synthetic result requires degradation extension')
                last = state.identity_cache[state.last_processed_timestamp.isoformat()]
                if last['hash'] != state.last_payload_hash or last['result'] != state.last_result:
                    raise CheckpointCompatibilityError('checkpoint result/identity mismatch')
                if not isinstance(state.last_result, dict) or state.last_result.get('transformer_id') != config.transformer_id or utc(state.last_result['timestamp']) != utc(state.last_processed_timestamp):
                    raise CheckpointCompatibilityError('invalid result asset/event identity')
                for row in state.history_records:
                    accepted = state.identity_cache.get(pd.Timestamp(row['timestamp']).isoformat())
                    if accepted is None or accepted['hash'] != payload_hash(row):
                        raise CheckpointCompatibilityError('history/identity cache mismatch')
                # Validate all state is safe JSON, then install only after complete validation.
                encode(state)
            except CheckpointCompatibilityError:
                self._restore_failures.add(config.transformer_id)
                raise
            except Exception as exc:
                self._restore_failures.add(config.transformer_id)
                raise CheckpointCompatibilityError(f'invalid checkpoint: {exc}') from exc
            self.pipeline._asset_states[config.transformer_id] = state
            self.pipeline.register_asset(config)
            self._revisions[config.transformer_id] = self._revisions.get(config.transformer_id, 0) + 1
            self._restore_failures.discard(config.transformer_id)
