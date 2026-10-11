import unittest
from dataclasses import replace
from ml.rul import SyntheticConfig,Duty,predict_synthetic,first_passage,assess_operational_eligibility,operational_result
from ml.tests._h05_fixtures import START,row,schema_validate

def config(**kwargs):
    values=dict(scenario_id='FICTIONAL',version='fictional-rul-v1',start_time=START,initial_degradation=.2,
                endpoint=1.,rate_per_hour=.01,horizon_hours=100.,maximum_gap_seconds=10.)
    values.update(kwargs)
    return SyntheticConfig(**values)

class TestSyntheticRUL(unittest.TestCase):
    def predict(self,current=.2,cfg=None,source=None):
        p=predict_synthetic(current,cfg or config(),START,source or row()['acquisition'],coverage_start=START,coverage_fraction=1.)
        schema_validate('rul.schema.json',dict(transformer_id='HX-A',timestamp=p.rul['timestamp'],rul=p.rul,schema_version='1.1.0'))
        return p
    def test_constant_oracle_and_curve(self):
        p=self.predict()
        self.assertAlmostEqual(p.rul['rul_value'],80.,places=10)
        self.assertEqual(p.rul['rul_status'],'SIMULATED_ESTIMATE')
        self.assertEqual(p.projected_curve[-1],{'elapsed_hours':80.,'degradation':1.})
        self.assertNotIn('projected_curve',p.rul)
    def test_endpoint_is_zero(self):
        self.assertEqual(self.predict(1.).rul['rul_value'],0.)
        self.assertEqual(self.predict(1.2).rul['rul_status'],'END_THRESHOLD_REACHED')
        self.assertEqual(self.predict(1.,config(rate_per_hour=None,horizon_hours=None)).rul['rul_value'],0.)
    def test_zero_and_beyond_horizon(self):
        for cfg in (config(rate_per_hour=0),config(horizon_hours=20)):
            r=self.predict(cfg=cfg).rul
            self.assertEqual(r['rul_status'],'NO_CROSSING_WITHIN_HORIZON')
            self.assertIsNone(r['rul_value']);self.assertIsNone(r['rul_upper'])
    def test_double_rate_halves_time(self):
        self.assertAlmostEqual(self.predict(cfg=config(rate_per_hour=.02)).rul['rul_value'],40.)
    def test_piecewise_and_subdivision(self):
        duty=(Duty(10,.02),Duty(40,.03))
        value,curve,complete=first_passage(.2,1,50,duty)
        self.assertAlmostEqual(value,30.,places=10);self.assertTrue(complete)
        subdivided=tuple(Duty(1,.02) for _ in range(10))+tuple(Duty(1,.03) for _ in range(40))
        self.assertAlmostEqual(first_passage(.2,1,50,subdivided)[0],value,places=10)
        self.assertEqual(curve[-1]['degradation'],1.)
        self.assertAlmostEqual(self.predict(cfg=config(horizon_hours=50,future_duty=duty)).rul['rul_value'],30.)
    def test_declared_range_not_confidence(self):
        r=self.predict(cfg=config(rate_bounds_per_hour=(.008,.012))).rul
        self.assertAlmostEqual(r['rul_lower'],66.6666666667,places=8)
        self.assertEqual(r['rul_upper'],100);self.assertLessEqual(r['rul_lower'],r['rul_value'])
        self.assertEqual(r['uncertainty_kind'],'SCENARIO_RANGE')
    def test_range_without_finite_upper_is_unavailable(self):
        r=self.predict(cfg=config(rate_bounds_per_hour=(0,.012))).rul
        self.assertIsNone(r['rul_upper']);self.assertIsNone(r['uncertainty_kind'])
    def test_missing_inputs_and_incomplete_duty(self):
        for cfg in (config(endpoint=None),config(rate_per_hour=None),config(horizon_hours=None)):
            self.assertEqual(self.predict(cfg=cfg).rul['rul_status'],'INSUFFICIENT_DATA')
        self.assertEqual(self.predict(current=None).rul['rul_status'],'INSUFFICIENT_DATA')
        self.assertEqual(self.predict(cfg=config(future_duty=(Duty(1,0),))).rul['rul_status'],'INSUFFICIENT_DATA')
    def test_invalid_parameters_and_timestamps(self):
        for change in (dict(rate_per_hour=-1),dict(endpoint=0),dict(horizon_hours=-1),dict(maximum_gap_seconds=0),dict(rate_per_hour=float('nan')),dict(start_time='2026-10-09T00:00:00')):
            with self.assertRaises(ValueError):config(**change)
    def test_real_source_never_gets_synthetic_fallback(self):
        r=self.predict(source=row(source='LIVE')['acquisition']).rul
        self.assertIsNone(r['rul_value']);self.assertFalse(r['simulated'])
    def test_operational_prerequisites_and_wti(self):
        a=row(source='LIVE')['acquisition']
        r=operational_result(START,a)
        self.assertIsNone(r['rul_value']);self.assertIn('MISSING_VERIFIED_HOTSPOT',r['limitation_codes'])
        assessment=assess_operational_eligibility({'hotspot':{'verification':'VERIFIED','evidence_reference':'test','value':1,'unit':'DEG_C','semantics':'WTI_CONTACT'}})
        self.assertFalse(assessment['eligible'])
        schema_validate('rul.schema.json',dict(transformer_id='HX-A',timestamp=r['timestamp'],rul=r,schema_version='1.1.0'))
    def test_replayed_real_source_is_insufficient(self):
        a=row(source='REPLAYED')['acquisition'];a['origin_kind']='LIVE'
        r=operational_result(START,a);self.assertIsNone(r['rul_value']);self.assertEqual(r['source_kind'],'REPLAYED')
    def test_even_complete_eligibility_does_not_invent_an_estimator(self):
        from ml.rul.model import REQUIREMENTS
        evidence={k:dict(verification='VERIFIED',evidence_reference='controlled-test-evidence',value=1,unit=u,semantics='MEASURED_HOTSPOT') for k,(u,_) in REQUIREMENTS.items()}
        evidence['liquid']['value']='declared liquid';evidence['insulation']['value']='declared insulation'
        evidence['ageing_parameters']['value']={'declared_set':'owner reference'}
        evidence['future_duty']['value']={'declared_scenario':'owner reference'}
        evidence['time_coverage']['minimum_fraction']=1.
        self.assertTrue(assess_operational_eligibility(evidence)['eligible'])
        acquisition=row(source='LIVE')['acquisition']
        acquisition['field_units']['winding_temperature']='DEG_C'
        acquisition['field_verification']['winding_temperature']='VERIFIED'
        r=operational_result(START,acquisition,evidence)
        self.assertIsNone(r['rul_value']);self.assertEqual(r['required_inputs'],[])
        self.assertIn('OPERATIONAL_RUL_ESTIMATOR_NOT_IMPLEMENTED',r['limitation_codes'])
        evidence['time_coverage']['value']=.5
        self.assertFalse(assess_operational_eligibility(evidence)['eligible'])
        status_source=row(source='LIVE')['acquisition']
        self.assertIn('SOURCE_HOTSPOT_UNITS_OR_SEMANTICS_INELIGIBLE',operational_result(START,status_source,evidence)['limitation_codes'])

if __name__=='__main__':unittest.main()
