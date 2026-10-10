import copy
import json
import unittest
from dataclasses import replace
from ml.pipeline import AssetConfig,PipelineBundle,UnifiedMLPipeline,PipelineSession,CheckpointCompatibilityError,CandidateStateError
from ml.pipeline.orchestrator import PipelineValidationError
from ml.rul.model import update_degradation
from ml.tests.test_rul_h05 import config
from ml.tests._h05_fixtures import START,row,example,schema_validate

class TestH05Session(unittest.TestCase):
    def setUp(self):
        self.bundle=PipelineBundle.load_from_processed_dir()
        self.session=PipelineSession(UnifiedMLPipeline(self.bundle))
        self.asset=self.make_asset('HX-A')
    def make_asset(self,id,**scenario):
        asset=AssetConfig.from_dict(dict(example('asset-valid'),id=id))
        return replace(asset,additional_configuration={**asset.additional_configuration,'synthetic_rul':config(**scenario).to_dict()})
    def accept(self,seconds=0,asset=None,**record):
        asset=asset or self.asset
        candidate=self.session.prepare(asset,row(seconds,asset=asset.transformer_id,**record))
        result=self.session.install(candidate,database_committed=True)
        return candidate,result
    def test_candidate_discard_and_install_once(self):
        self.accept()
        before=json.dumps(self.session.export_checkpoint('HX-A'),sort_keys=True)
        pending=self.session.prepare(self.asset,row(5))
        self.assertGreater(pending.result['rul']['degradation_state'],.2)
        self.session.discard(pending)
        self.assertEqual(before,json.dumps(self.session.export_checkpoint('HX-A'),sort_keys=True))
        pending=self.session.prepare(self.asset,row(5))
        with self.assertRaises(CandidateStateError):self.session.install(pending)
        self.session.install(pending,database_committed=True)
        self.assertEqual(self.session.export_checkpoint('HX-A')['observation_count'],2)
        with self.assertRaises(CandidateStateError):self.session.install(pending,database_committed=True)
    def test_restart_json_equivalence(self):
        self.accept();self.accept(5)
        checkpoint=json.loads(json.dumps(self.session.export_checkpoint('HX-A')))
        restored=PipelineSession(UnifiedMLPipeline(self.bundle));restored.import_checkpoint(checkpoint,self.asset)
        self.assertEqual(checkpoint,restored.export_checkpoint('HX-A'))
        a=self.session.prepare(self.asset,row(10));b=restored.prepare(self.asset,row(10))
        self.assertEqual(a.result,b.result);self.assertEqual(a.checkpoint,b.checkpoint)
        schema_validate('checkpoint.schema.json',a.checkpoint)
        schema_validate('analytics.schema.json',a.result)
        self.assertEqual(a.checkpoint['state']['synthetic_degradation']['state_version'],'1.0.0')
    def test_exact_retry_changed_trip_and_late_never_advance(self):
        self.accept();self.accept(5)
        before=json.dumps(self.session.export_checkpoint('HX-A'),sort_keys=True)
        retry=self.session.prepare(self.asset,row(5));self.assertEqual(retry.outcome,'EXACT_RETRY')
        self.session.install(retry,database_committed=True)
        conflict=self.session.prepare(self.asset,dict(row(5),oil_temp_trip=1))
        self.assertEqual(conflict.outcome,'CONFLICT');self.assertIsNone(conflict.result)
        late=self.session.prepare(self.asset,row(2));self.assertEqual(late.outcome,'REJECTED_LATE_OBSERVATION')
        self.assertEqual(before,json.dumps(self.session.export_checkpoint('HX-A'),sort_keys=True))
    def test_two_assets_and_trip_latches(self):
        other=self.make_asset('HX-B',rate_per_hour=.02)
        self.accept();self.accept(asset=other)
        record=row(5);record['oil_temp_trip']=1
        a=self.session.prepare(self.asset,record);self.session.install(a,database_committed=True)
        _,b=self.accept(5,asset=other)
        self.assertAlmostEqual(a.result['rul']['degradation_state'],.2+.01*5/3600)
        self.assertAlmostEqual(b['rul']['degradation_state'],.2+.02*5/3600)
        self.assertTrue(a.result['metadata']['maintenance_trip_latched'])
        self.assertFalse(b['metadata']['maintenance_trip_latched'])
    def test_extension_corruption_or_scenario_change_rejects_and_preserves_trip(self):
        record=row();record['oil_temp_trip']=1
        candidate=self.session.prepare(self.asset,record);self.session.install(candidate,database_committed=True)
        checkpoint=self.session.export_checkpoint('HX-A')
        for mutation in ('extension_version','degradation','scenario_fingerprint','last_event_time'):
            session=PipelineSession(UnifiedMLPipeline(self.bundle));session.import_checkpoint(checkpoint,self.asset)
            bad=copy.deepcopy(checkpoint);payload=bad['state']['synthetic_degradation']['payload']
            payload[mutation]={'extension_version':'9','degradation':-1,'scenario_fingerprint':'changed','last_event_time':'2026-10-08T00:00:00Z'}[mutation]
            with self.assertRaises(CheckpointCompatibilityError):session.import_checkpoint(bad,self.asset)
            self.assertTrue(session.pipeline.get_state('HX-A').maintenance_state.trip_latched)
        with self.assertRaises(CheckpointCompatibilityError):
            self.session.import_checkpoint(checkpoint,self.make_asset('HX-A',rate_per_hour=.02))
    def test_gap_withholds_d_and_remains_unknown(self):
        self.accept();_,r=self.accept(30)
        self.assertIsNone(r['rul']['rul_value']);self.assertIsNone(r['rul']['degradation_state'])
        self.assertIn('DEGRADATION_GAP_UNSUPPORTED',r['rul']['limitation_codes'])
        _,next_result=self.accept(35);self.assertIsNone(next_result['rul']['degradation_state'])
    def test_explicit_gap_assumption_and_timestep_subdivision(self):
        scenario=config(assume_constant_rate_across_gaps=True).to_dict()
        large,projection=update_degradation(None,row(3600),scenario)
        state=None
        for second in range(0,3601,60):state,_=update_degradation(state,row(second),scenario)
        self.assertAlmostEqual(large['degradation'],.21,places=10)
        self.assertAlmostEqual(state['degradation'],large['degradation'],places=10)
        self.assertTrue(any('not sensor coverage' in a for a in projection.rul['assumptions']))
    def test_negative_elapsed_rejects(self):
        state,_=update_degradation(None,row(5),config().to_dict())
        with self.assertRaises(ValueError):update_degradation(state,row(2),config().to_dict())
    def test_curve_corruption_and_missing_extension_reject(self):
        self.accept();checkpoint=self.session.export_checkpoint('HX-A')
        for missing in (False,True):
            bad=copy.deepcopy(checkpoint)
            if missing:bad['state']['synthetic_degradation']['payload']=None
            else:bad['state']['synthetic_degradation']['payload']['projected_curve'][0]['degradation']=99
            with self.assertRaises(CheckpointCompatibilityError):PipelineSession(UnifiedMLPipeline(self.bundle)).import_checkpoint(bad,self.asset)
    def test_changed_scenario_prepare_does_not_reset_accepted_state(self):
        self.accept();before=self.session.export_checkpoint('HX-A')
        with self.assertRaises(PipelineValidationError):self.session.prepare(self.make_asset('HX-A',rate_per_hour=.02),row(5))
        self.assertEqual(before,self.session.export_checkpoint('HX-A'))
    def test_public_analyze_hydrates_history_once(self):
        from ml.pipeline import analyze
        pipe=UnifiedMLPipeline(self.bundle)
        transformer=dict(example('asset-valid'),synthetic_rul=config().to_dict())
        result=analyze(transformer,row(10),[row(0),row(5)],pipeline=pipe)
        self.assertAlmostEqual(result['rul']['degradation_state'],.2+.01*10/3600)
        self.assertEqual(result,analyze(transformer,row(10),[row(0),row(5)],pipeline=pipe))
        self.assertEqual(pipe.get_state('HX-A').observation_count,3)
    def test_replay_run_isolation_and_wall_clock_speed_independence(self):
        asset=self.make_asset('REPLAY-ASSET')
        slow=PipelineSession(UnifiedMLPipeline(self.bundle));fast=PipelineSession(UnifiedMLPipeline(self.bundle))
        for seconds in (0,5,10):
            record=row(seconds,asset='REPLAY-ASSET',source='REPLAYED')
            a=slow.prepare(asset,record);b=fast.prepare(asset,copy.deepcopy(record))
            self.assertEqual(a.result,b.result);self.assertEqual(a.checkpoint,b.checkpoint)
            schema_validate('analytics.schema.json',a.result)
            slow.install(a,database_committed=True);fast.install(b,database_committed=True)
        self.assertEqual(a.result['rul']['source_kind'],'REPLAYED')
        before=slow.export_checkpoint('REPLAY-ASSET')
        with self.assertRaises(PipelineValidationError):slow.prepare(asset,row(15,asset='REPLAY-ASSET',source='REPLAYED',run='different-run'))
        self.assertEqual(before,slow.export_checkpoint('REPLAY-ASSET'))
        self.assertIsNone(self.session.export_checkpoint('HX-A'))
    def test_real_source_operational_null_preserves_existing_analytics(self):
        asset=AssetConfig.from_dict(example('asset-valid'))
        pending=self.session.prepare(asset,row(source='LIVE'))
        self.assertIsNone(pending.result['rul']['rul_value'])
        self.assertFalse(pending.result['rul']['simulated']);self.assertIsNone(pending.result['fault_risk'])
        self.assertIsNone(pending.result['prediction_confidence'])
        schema_validate('analytics.schema.json',pending.result)
    def test_prior_algorithm_outputs_unchanged_with_explicit_scenario(self):
        baseline=PipelineSession(UnifiedMLPipeline(self.bundle))
        asset=replace(self.asset,additional_configuration={k:v for k,v in self.asset.additional_configuration.items() if k!='synthetic_rul'})
        for seconds in (0,5,10):
            a=self.session.prepare(self.asset,row(seconds));b=baseline.prepare(asset,row(seconds))
            for key in ('thermal_model_temperature','thermal_residual','anomaly_score','health_index','health_components','maintenance_priority','maintenance_recommendation','fault_risk','prediction_confidence','reason_codes'):
                self.assertEqual(a.result[key],b.result[key],key)
            self.session.install(a,database_committed=True);baseline.install(b,database_committed=True)

if __name__=='__main__':unittest.main()
