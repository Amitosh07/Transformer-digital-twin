"""Validate actual H01 outputs against the unchanged H00 schemas (test-only jsonschema)."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from ml.pipeline import AssetConfig, PipelineBundle, PipelineSession, UnifiedMLPipeline

FIXTURES = Path(__file__).resolve().parents[2] / 'tests/fixtures/hackathon'


class TestContractCompatibility(unittest.TestCase):
    def validate(self, name, value):
        schema = json.loads((FIXTURES / (name + '.schema.json')).read_text(encoding='utf-8'))
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)

    def test_actual_checkpoint_analytics_and_outcomes(self):
        traces = json.loads((FIXTURES / 'traces.json').read_text(encoding='utf-8'))
        row = copy.deepcopy(traces[0]['records'][0])
        row['acquisition']['snapshot_id'] = None
        session = PipelineSession(UnifiedMLPipeline(PipelineBundle.load_from_processed_dir()))
        config = AssetConfig(row['transformer_id'])
        candidate = session.prepare(config, row)
        self.validate('analytics', candidate.result)
        self.validate('checkpoint', candidate.checkpoint)
        self.validate('ingestion-outcome', candidate.ingestion)
        session.install(candidate, database_committed=True)
        self.validate('ingestion-outcome', session.prepare(config, row).ingestion)
        row['oil_temp_trip'] = 1
        self.validate('ingestion-outcome', session.prepare(config, row).ingestion)
        row['timestamp'] = '2026-10-08T23:59:55Z'
        self.validate('ingestion-outcome', session.prepare(config, row).ingestion)

    def test_legacy_and_demo_analytics_remain_representable(self):
        row = {'schema_version': '1.0.0', 'transformer_id': 'LEGACY',
               'timestamp': '2026-10-09T00:00:00Z', 'oil_temp_trip': None}
        self.validate('telemetry', row)
        for mode in ('STRICT_FITTED', 'DEMO_UNVERIFIED_CONFIG'):
            result = UnifiedMLPipeline(PipelineBundle.load_from_processed_dir(mode=mode)).process_record(row)
            self.validate('analytics', result)
            self.assertIsNone(result['fault_risk'])
            self.assertEqual(result['metadata']['coverage']['fraction'], 0)


if __name__ == '__main__':
    unittest.main()
