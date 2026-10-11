"""Strict release, explicit demo, serialization and runtime export evidence."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ml.pipeline.bundle import PipelineBundle, BundleNotReadyError, RUNTIME_ARTIFACTS, load_forecast_artifact
from ml.pipeline.runtime import export_runtime
from ml.prediction.model import write_prediction_artifact
from ml.tests.test_pipeline import make_sample_record
from ml.pipeline import UnifiedMLPipeline

PROCESSED = Path(__file__).resolve().parents[2] / 'data/processed'


class TestBundleRuntime(unittest.TestCase):
    def test_original_runtime_hashes_and_parameters(self):
        bundle = PipelineBundle.load_from_processed_dir(PROCESSED, mode='STRICT_FITTED')
        thermal = json.loads((PROCESSED / RUNTIME_ARTIFACTS[0]).read_text())
        anomaly = json.loads((PROCESSED / RUNTIME_ARTIFACTS[1]).read_text())
        self.assertEqual(bundle.thermal_config.b0, thermal['parameters']['b0'])
        self.assertEqual(bundle.anomaly_config.thresholds['oil_level_deviation'].critical_threshold,
                         anomaly['thresholds']['oil_level_deviation']['critical_threshold'])
        self.assertEqual(bundle.runtime_mode, 'STRICT_FITTED')

    def test_strict_missing_corrupt_and_incompatible_block_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(BundleNotReadyError):
                PipelineBundle.load_from_processed_dir(root, mode='STRICT_FITTED')
            dest = export_runtime(PROCESSED, root / 'artifacts')
            (dest / RUNTIME_ARTIFACTS[0]).write_text('{}')
            with self.assertRaises(BundleNotReadyError):
                PipelineBundle.load_from_processed_dir(dest, mode='STRICT_FITTED')
            dest2 = export_runtime(PROCESSED, root / 'artifacts2')
            manifest = json.loads((dest2 / 'release_manifest.json').read_text())
            manifest['versions']['feature_version'] = '9'
            (dest2 / 'release_manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(BundleNotReadyError):
                PipelineBundle.load_from_processed_dir(dest2, mode='STRICT_FITTED')

    def test_demo_explicit_distinct_and_unreleased(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BundleNotReadyError):
                PipelineBundle.load_from_processed_dir(d)
            demo = PipelineBundle.load_from_processed_dir(d, mode='DEMO_UNVERIFIED_CONFIG')
            self.assertEqual(demo.configuration_readiness, 'UNVERIFIED')
            self.assertEqual(demo.model_version, 'DEMO_UNVERIFIED_CONFIG')
            self.assertNotEqual(demo.bundle_id, 'processed_bundle_v1')
            result = UnifiedMLPipeline(demo).process_record(make_sample_record())
            self.assertIsNone(result['fault_risk'])
            self.assertIsNone(result['prediction_confidence'])
            self.assertIn('DEMO_UNVERIFIED_CONFIG', result['metadata']['extended_reason_codes'])

    def test_real_writer_roundtrip_and_release_gate(self):
        artifact = json.loads((PROCESSED / RUNTIME_ARTIFACTS[2]).read_text())
        predictor = load_forecast_artifact(artifact)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prediction.json'
            write_prediction_artifact(artifact, path)
            output = json.loads(path.read_text())
            self.assertEqual(artifact, output)
            loaded = load_forecast_artifact(output)
            row = artifact['preprocessing']['medians']
            self.assertEqual(predictor.predict_record(row), loaded.predict_record(row))
            result = loaded.predict_record(row)
            self.assertIsNotNone(result['experimental_risk'])
            self.assertIsNone(result['fault_risk'])
            self.assertIsNone(result['prediction_confidence'])
        bad = copy.deepcopy(artifact); bad['preprocessing']['feature_names'].reverse()
        with self.assertRaises(BundleNotReadyError):
            load_forecast_artifact(bad)
        bad = copy.deepcopy(artifact); bad['operational_release_status']['is_operationally_released'] = True
        with self.assertRaises(BundleNotReadyError):
            load_forecast_artifact(bad)

    def test_legacy_preprocessor_compatibility(self):
        artifact = json.loads((PROCESSED / RUNTIME_ARTIFACTS[2]).read_text())
        artifact['primary_experiment']['preprocessor'] = artifact.pop('preprocessing')
        self.assertIsNotNone(load_forecast_artifact(artifact))

    def test_export_only_permitted_artifacts_and_original_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = export_runtime(PROCESSED, Path(directory) / 'export')
            self.assertEqual({p.name for p in dest.iterdir()}, {'release_manifest.json', *RUNTIME_ARTIFACTS})
            self.assertEqual((dest / 'release_manifest.json').read_bytes(), (PROCESSED / 'release_manifest.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
