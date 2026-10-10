"""Run by absolute path from a neutral cwd using the clean venv interpreter."""
import json
from pathlib import Path
import sys

import ml
from ml.pipeline import analyze, AssetConfig, PipelineBundle, PipelineSession, UnifiedMLPipeline
from ml.pipeline.bundle import BundleNotReadyError

assert 'site-packages' in str(Path(ml.__file__).resolve()), ml.__file__
bundle = PipelineBundle.load_from_processed_dir(sys.argv[1], mode='STRICT_FITTED')
row = {'transformer_id': 'INSTALL-CHECK', 'timestamp': '2026-10-09T00:00:00Z',
       'oil_temp_trip': 1, 'schema_version': '1.1.0'}
session = PipelineSession(UnifiedMLPipeline(bundle))
candidate = session.prepare(AssetConfig('INSTALL-CHECK'), row)
assert candidate.result['health_index'] == 0
assert candidate.result['maintenance_priority'] == 'URGENT'
assert candidate.result['fault_risk'] is None
assert candidate.result['prediction_confidence'] is None
session.install(candidate, database_committed=True)
checkpoint = json.loads(json.dumps(session.export_checkpoint('INSTALL-CHECK')))
restored = PipelineSession(UnifiedMLPipeline(bundle))
restored.import_checkpoint(checkpoint, AssetConfig('INSTALL-CHECK'))
assert restored.export_checkpoint('INSTALL-CHECK') == checkpoint
assert restored.prepare(AssetConfig('INSTALL-CHECK'), row).outcome == 'EXACT_RETRY'
demo = PipelineBundle.load_from_processed_dir(mode='DEMO_UNVERIFIED_CONFIG')
assert demo.bundle_id != bundle.bundle_id
assert demo.configuration_readiness == 'UNVERIFIED'
result = analyze({'id': 'INSTALL-CHECK'}, row, [], pipeline=UnifiedMLPipeline(demo))
assert result['fault_risk'] is None
try:
    PipelineBundle.load_from_processed_dir(Path(sys.argv[1]) / 'absent', mode='STRICT_FITTED')
except BundleNotReadyError:
    pass
else:
    raise AssertionError('strict mode silently fell back')
print(json.dumps({'import_path': ml.__file__, 'strict_mode': bundle.runtime_mode,
                  'demo_mode': demo.runtime_mode, 'health_index': candidate.result['health_index'],
                  'maintenance_priority': candidate.result['maintenance_priority'],
                  'fault_risk': candidate.result['fault_risk'], 'checkpoint_roundtrip': True}))
