"""H07 serialization optimization preserves checkpoint and transaction semantics."""
import copy
import json
import unittest
from decimal import Decimal
import numpy as np
import pandas as pd
from ml.pipeline.session import encode
from ml.tests import test_session as baseline

class TestH07Session(unittest.TestCase):
    setUp = baseline.TestSession.setUp
    row = baseline.TestSession.row
    accept = baseline.TestSession.accept
    def test_native_encoder_tags_and_nonfinite_rejection(self):
        value = {'n': None, 'zero': 0, 'flag': False, 'float': 1.5,
                 'utc': pd.Timestamp('2026-10-10T00:00:00Z'),
                 'decimal': Decimal('1.50'), 'array': (np.int64(2),)}
        self.assertEqual(encode(value), {'n': None, 'zero': 0, 'flag': False,
            'float': 1.5, 'utc': {'$utc': '2026-10-10T00:00:00.000000Z'},
            'decimal': {'$decimal': '1.50'}, 'array': [2]})
        with self.assertRaises(ValueError): encode(float('nan'))

    def test_cached_past_results_remain_private_and_rollback_safe(self):
        self.accept()
        committed = self.session.pipeline._asset_states['TX-001']
        before = json.dumps(self.session.export_checkpoint('TX-001'), sort_keys=True)
        candidate = self.session.prepare(self.config, self.row(5, trip=1))
        candidate.checkpoint['state']['history']['payload']['identity_cache'].clear()
        candidate.result['metadata'].clear()
        self.session.discard(candidate)
        self.assertEqual(before, json.dumps(self.session.export_checkpoint('TX-001'), sort_keys=True))
        review = self.session.export_checkpoint('TX-001')
        for entry in review['state']['history']['payload']['identity_cache'].values():
            entry['result']['metadata'].clear()
        self.assertEqual(before, json.dumps(self.session.export_checkpoint('TX-001'), sort_keys=True))
        retry = self.session.prepare(self.config, self.row())
        retry.result['metadata'].clear()
        self.session.discard(retry)
        self.assertEqual(before, json.dumps(self.session.export_checkpoint('TX-001'), sort_keys=True))
        next_candidate = self.session.prepare(self.config, self.row(5))
        self.session.install(next_candidate, database_committed=True)
        restarted = type(self.session)(type(self.session.pipeline)(self.bundle))
        checkpoint = self.session.export_checkpoint('TX-001')
        restarted.import_checkpoint(copy.deepcopy(checkpoint), self.config)
        self.assertEqual(checkpoint, restarted.export_checkpoint('TX-001'))
