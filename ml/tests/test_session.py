"""H01 transaction, restart, identity and time-coverage evidence."""
import copy
import json
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pandas as pd

from ml.pipeline import (AssetConfig, PipelineBundle, UnifiedMLPipeline, PipelineSession,
                         CandidateStateError, CheckpointCompatibilityError, analyze)
from ml.pipeline.identity import canonical_bytes, payload_hash, parse_record_json
from ml.tests.test_pipeline import make_sample_record, fictional_asset, fictional_acquisition

ROOT = Path(__file__).resolve().parents[2]


class TestSession(unittest.TestCase):
    def setUp(self):
        self.config = AssetConfig('TX-001')
        self.bundle = PipelineBundle.load_from_processed_dir()
        self.session = PipelineSession(UnifiedMLPipeline(self.bundle))

    def row(self, seconds=0, asset='TX-001', trip=0):
        return make_sample_record(transformer_id=asset,
            timestamp=pd.Timestamp('2026-10-09T00:00:00Z') + pd.Timedelta(seconds=seconds), trip=trip)

    def accept(self, seconds=0, trip=0):
        c = self.session.prepare(self.config, self.row(seconds, trip=trip))
        self.session.install(c, database_committed=True)
        return c

    def test_prepare_discard_bytes_and_result_unchanged(self):
        self.accept()
        before = json.dumps(self.session.export_checkpoint('TX-001'), sort_keys=True)
        c = self.session.prepare(self.config, self.row(5, trip=1))
        self.assertTrue(c.result['metadata']['maintenance_trip_latched'])
        self.session.discard(c)
        self.assertEqual(before, json.dumps(self.session.export_checkpoint('TX-001'), sort_keys=True))
        with self.assertRaises(CandidateStateError):
            self.session.install(c, database_committed=True)

    def test_install_once_and_backend_commit_required(self):
        c = self.session.prepare(self.config, self.row())
        self.assertIsNone(self.session.export_checkpoint('TX-001'))
        with self.assertRaises(CandidateStateError):
            self.session.install(c)
        # Mutating review copies cannot mutate the internal staged state.
        c.checkpoint['observation_count'] = 999
        c.result['health_index'] = -1
        result = self.session.install(c, database_committed=True)
        self.assertGreaterEqual(result['health_index'], 0)
        self.assertEqual(self.session.export_checkpoint('TX-001')['observation_count'], 1)
        with self.assertRaises(CandidateStateError):
            self.session.install(c, database_committed=True)

    def test_stale_candidate_rejected(self):
        a = self.session.prepare(self.config, self.row())
        b = self.session.prepare(self.config, self.row(5))
        self.session.install(a, database_committed=True)
        with self.assertRaises(CandidateStateError):
            self.session.install(b, database_committed=True)

    def test_json_restart_equivalence_and_trip(self):
        self.accept(trip=1)
        self.accept(5)
        checkpoint = json.loads(json.dumps(self.session.export_checkpoint('TX-001')))
        restored = PipelineSession(UnifiedMLPipeline(self.bundle))
        restored.import_checkpoint(checkpoint, self.config)
        self.assertEqual(checkpoint, restored.export_checkpoint('TX-001'))
        a = self.session.prepare(self.config, self.row(10))
        b = restored.prepare(self.config, self.row(10))
        self.assertEqual(a.result, b.result)
        self.assertEqual(a.checkpoint, b.checkpoint)
        self.assertTrue(b.result['metadata']['maintenance_trip_latched'])
        self.assertEqual(b.result['health_index'], 0)

    def test_incompatible_checkpoints_preserve_protection(self):
        self.accept(trip=1)
        checkpoint = self.session.export_checkpoint('TX-001')
        bads = []
        for field in ('checkpoint_version',):
            bad = copy.deepcopy(checkpoint); bad[field] = '9'; bads.append(bad)
        for field in checkpoint['versions']:
            bad = copy.deepcopy(checkpoint); bad['versions'][field] = '9'; bads.append(bad)
        bad = copy.deepcopy(checkpoint); bad['state']['synthetic_degradation']['state_version'] = '9'; bads.append(bad)
        bad = copy.deepcopy(checkpoint); bad['state']['coverage']['payload']['artifact_digest'] = 'corrupt'; bads.append(bad)
        for bad in bads:
            with self.assertRaises(CheckpointCompatibilityError):
                self.session.import_checkpoint(bad, self.config)
            self.assertEqual(checkpoint, self.session.export_checkpoint('TX-001'))
        with self.assertRaises(CheckpointCompatibilityError):
            self.session.prepare(self.config, self.row(5))
        self.session.import_checkpoint(checkpoint, self.config)
        self.assertTrue(self.session.prepare(self.config, self.row(5)).result['metadata']['maintenance_trip_latched'])

    def test_changed_ml_configuration_rejects_same_named_versions(self):
        self.accept(trip=1)
        checkpoint = self.session.export_checkpoint('TX-001')
        altered = replace(self.bundle, thermal_config=replace(self.bundle.thermal_config,
                                                              b0=self.bundle.thermal_config.b0 + 1))
        session = PipelineSession(UnifiedMLPipeline(altered))
        with self.assertRaises(CheckpointCompatibilityError):
            session.import_checkpoint(checkpoint, self.config)
        with self.assertRaises(CheckpointCompatibilityError):
            session.prepare(self.config, self.row(5))

    def test_old_retry_after_new_record_and_reset(self):
        first = self.accept()
        self.accept(5)
        retry = self.session.prepare(self.config, self.row())
        self.assertEqual(retry.result, first.result)
        self.assertEqual(self.session.install(retry, database_committed=True), first.result)
        self.session.pipeline.reset_state('TX-001')
        conflict = self.session.prepare(self.config, self.row(trip=1))
        self.assertEqual(conflict.outcome, 'CONFLICT')

    def test_duplicate_conflict_trip_and_late_are_isolated(self):
        first = self.accept()
        before = self.session.export_checkpoint('TX-001')
        retry = self.session.prepare(self.config, self.row())
        self.assertEqual(retry.outcome, 'EXACT_RETRY')
        self.assertEqual(retry.result, first.result)
        self.session.install(retry, database_committed=True)
        self.assertEqual(before, self.session.export_checkpoint('TX-001'))
        conflict = self.session.prepare(self.config, self.row(trip=1))
        self.assertEqual(conflict.outcome, 'CONFLICT')
        self.assertIsNone(conflict.result)
        self.assertIsNone(conflict.checkpoint)
        late = self.session.prepare(self.config, self.row(-5, trip=1))
        self.assertEqual(late.outcome, 'REJECTED_LATE_OBSERVATION')
        self.assertEqual(before, self.session.export_checkpoint('TX-001'))

    def test_two_assets_and_gap_trip_latches(self):
        self.accept(trip=1)
        b = self.session.prepare(AssetConfig('TX-002'), self.row(asset='TX-002'))
        self.session.install(b, database_committed=True)
        self.accept(7200)
        self.assertTrue(self.session.pipeline.get_state('TX-001').maintenance_state.trip_latched)
        self.assertFalse(self.session.pipeline.get_state('TX-002').maintenance_state.trip_latched)
        self.assertEqual(self.session.pipeline.get_state('TX-002').observation_count, 1)
        self.session.pipeline.reset_state()
        self.assertTrue(self.session.pipeline.get_state('TX-001').maintenance_state.trip_latched)

    def test_hour_retention_coverage_and_cap(self):
        # State retention itself is exercised at the required cadence; inference is
        # covered separately, avoiding 721 repeated whole-window feature builds.
        state = self.session.pipeline.get_state('TX-001')
        for i in range(800):
            row = self.row(i * 5)
            row['acquisition'] = fictional_acquisition()
            row['acquisition']['expected_interval_seconds'] = 5
            state.commit_observation(row, row['timestamp'], {})
        self.assertEqual(len(state.history_records), 721)
        self.assertEqual(state.coverage(state.last_processed_timestamp)['fraction'], 1)
        self.assertEqual((state.last_processed_timestamp - state.history_records[0]['timestamp']).total_seconds(), 3600)
        state.max_history_rows = 100
        row = self.row(4000); row['acquisition'] = fictional_acquisition(); row['acquisition']['expected_interval_seconds'] = 5
        state.commit_observation(row, row['timestamp'], {})
        self.assertTrue(state.history_capped)
        self.assertLess(state.coverage(state.last_processed_timestamp)['fraction'], 1)

    def test_sparse_coverage_and_missing_are_visible(self):
        a = self.accept()
        self.assertEqual(a.result['metadata']['coverage']['fraction'], 0)
        self.assertIn('UNKNOWN_PROVENANCE_AND_UNITS', a.result['metadata']['extended_reason_codes'])
        row = self.row(5); row['current_l1'] = None; row['current_l2'] = None
        b = self.session.prepare(self.config, row)
        self.assertEqual(b.result['inference_status'], 'INSUFFICIENT_DATA')
        self.assertIsNone(b.result['fault_risk'])

    def test_actual_five_second_inference_hour(self):
        pipe = UnifiedMLPipeline(self.bundle)
        config = fictional_asset('TX-001')
        pipe.register_asset(config)
        for i in range(722):
            row = self.row(i * 5)
            row['acquisition'] = fictional_acquisition()
            row['acquisition']['expected_interval_seconds'] = 5
            result = pipe.process_record(row)
        state = pipe.get_state('TX-001')
        self.assertEqual(len(state.history_records), 721)
        self.assertEqual(result['metadata']['coverage']['fraction'], 1)
        self.assertEqual(result['loading_percent'], 50)
        self.assertIsNone(result['fault_risk'])

    def test_public_history_hydrates_once_and_checks_consistency(self):
        pipe = UnifiedMLPipeline(self.bundle)
        history = [self.row(), self.row(5)]
        analyze({'id': 'TX-001'}, self.row(10), history, pipeline=pipe)
        analyze({'id': 'TX-001'}, self.row(15), history, pipeline=pipe)
        self.assertEqual(pipe.get_state('TX-001').observation_count, 4)
        history[0]['oil_temp_trip'] = 1
        with self.assertRaises(ValueError):
            analyze({'id': 'TX-001'}, self.row(20), history, pipeline=pipe)

    def test_replay_requires_registered_separate_asset(self):
        self.accept(trip=1)
        config = AssetConfig('REPLAY-A')
        row = self.row(asset='REPLAY-A')
        row['acquisition'] = fictional_acquisition()
        row['acquisition'].update(source_kind='REPLAYED', origin_transformer_id='TX-001', replay_run_id='run-1')
        candidate = self.session.prepare(config, row)
        self.session.install(candidate, database_committed=True)
        self.assertFalse(candidate.result['metadata']['maintenance_trip_latched'])
        self.assertTrue(self.session.pipeline.get_state('TX-001').maintenance_state.trip_latched)
        row['acquisition']['origin_transformer_id'] = 'REPLAY-A'
        with self.assertRaises(ValueError):
            self.session.prepare(config, row)

    def test_h00_hash_vectors_including_decimal_precision(self):
        vectors = parse_record_json((ROOT / 'tests/fixtures/hackathon/hash-vectors.json').read_text(encoding='utf-8'))
        for vector in vectors:
            for row in vector['equivalent_inputs']:
                self.assertEqual(canonical_bytes(row).decode(), vector['canonical_utf8'])
                self.assertEqual(payload_hash(row), vector['sha256'])
            for row in vector['different_inputs']:
                self.assertNotEqual(payload_hash(row), vector['sha256'])
        for stamp in ('2026-10-09T00:00:00', '2026-10-09T00:00:00.0000000Z'):
            with self.assertRaises(ValueError):
                payload_hash({'transformer_id': 'X', 'timestamp': stamp})
        with self.assertRaises(ValueError):
            parse_record_json('{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            payload_hash(dict(self.row(), oil_temp_trip=1.0))

    def test_rating_and_voltage_require_actual_evidence(self):
        a = fictional_acquisition()
        self.assertEqual(AssetConfig('X', rated_power_kva=100).calculate_loading(80, a), (None, None))
        self.assertEqual(fictional_asset('X').calculate_loading(80, a), (80, .8))
        a['source_kind'] = 'LIVE'
        self.assertEqual(fictional_asset('X').calculate_loading(80, a), (None, None))
        self.assertEqual(AssetConfig.from_dict({'id': 'X', 'voltageHvKv': 11}).rated_voltage_hv, 11)
        config = AssetConfig.from_dict({'id': 'X', 'voltageHvKv': 11,
            'configuration_metadata': {'field_metadata': {'voltageHvKv': {
                'unit': 'kV', 'verification': 'VERIFIED', 'evidence_reference': 'test-nameplate'}}}})
        self.assertEqual(config.rated_voltage_hv, 11000)


if __name__ == '__main__':
    unittest.main()
