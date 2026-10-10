import copy
import unittest
from dataclasses import replace
from ml.energy import EnergyConfig,EnergyConflictError,calculate_energy,analyze_energy,efficiency_percent
from ml.tests._h05_fixtures import START,row,loss_model,schema_validate
from datetime import timedelta
from ml.rul.common import event_time

def config(method='POWER',**changes):
    fields=dict(version='h05-source-v1',method=method,maximum_gap_seconds=7200,power_sign='IMPORT_ONLY_NONNEGATIVE')
    if method=='COUNTER':fields['counter_semantics']='CUMULATIVE_IMPORT'
    fields.update(changes)
    return EnergyConfig(**fields)

class TestEnergyH05(unittest.TestCase):
    def calculate(self,rows,cfg=None,seconds=None,**kwargs):
        end=seconds if seconds is not None else max((event_time(r['timestamp'])-event_time(START)).total_seconds() for r in rows)
        result=calculate_energy(rows,rows[0]['transformer_id'] if rows else 'HX-A',START,event_time(START)+timedelta(seconds=end),cfg or config(),**kwargs)
        schema_validate('energy.schema.json',result)
        return result
    def test_constant_and_linear_oracles(self):
        self.assertEqual(self.calculate([row(),row(7200)])['consumed_kwh'],20)
        self.assertEqual(self.calculate([row(power=0),row(3600,power=10)])['consumed_kwh'],5)
    def test_irregular_intervals_weighted_mean_and_observed_peak(self):
        rows=[row(0,power=0),row(600,power=10),row(3600,power=20)]
        analysis=analyze_energy(rows,'HX-A',START,rows[-1]['timestamp'],config())
        self.assertAlmostEqual(analysis.result['consumed_kwh'],5/6+12.5)
        self.assertAlmostEqual(analysis.mean_power_kw,13.333333333333334)
        self.assertEqual(analysis.result['peak_kw'],20)
        self.assertEqual(event_time(analysis.result['peak_time']),event_time(rows[-1]['timestamp']))
    def test_counter_difference_selects_one_method(self):
        r=self.calculate([row(counter=100,power=999),row(3600,counter=110,power=999)],config('COUNTER'))
        self.assertEqual(r['consumed_kwh'],10);self.assertEqual(r['calculation_method'],'COUNTER_DIFFERENCE')
        self.assertEqual(r['energy_method'],'SIMULATED')
    def test_counter_reset_excludes_jump_and_retains_partial(self):
        r=self.calculate([row(counter=100),row(3600,counter=110),row(7200,counter=2),row(10800,counter=5)],config('COUNTER',maximum_gap_seconds=3600))
        self.assertEqual(r['covered_consumed_kwh'],13);self.assertIsNone(r['consumed_kwh'])
        self.assertEqual(r['reset_count'],1);self.assertAlmostEqual(r['coverage_fraction'],2/3)
        self.assertIn('COUNTER_RESET',r['missing_intervals'][0]['reason'])
    def test_long_gaps_no_false_total(self):
        for method in ('POWER','COUNTER'):
            r=self.calculate([row(counter=100),row(3600,counter=110)],config(method,maximum_gap_seconds=10))
            self.assertIsNone(r['consumed_kwh']);self.assertIsNone(r['covered_consumed_kwh']);self.assertEqual(r['gap_count'],1)
    def test_long_counter_gap_needs_independent_evidence(self):
        r=self.calculate([row(counter=100),row(3600,counter=110)],config('COUNTER',maximum_gap_seconds=10,continuity_reference='controlled uninterrupted meter evidence'))
        self.assertEqual(r['consumed_kwh'],10);self.assertEqual(r['coverage_fraction'],1)
    def test_missing_power_endpoint_excludes_only_unsupported_intervals(self):
        r=self.calculate([row(),row(3600),row(7200,power=None)])
        self.assertEqual(r['covered_consumed_kwh'],10);self.assertIsNone(r['consumed_kwh']);self.assertEqual(r['energy_status'],'PARTIAL')
    def test_invalid_finite_numeric_values_reject(self):
        for value in (float('nan'),float('inf'),True,'10'):
            with self.assertRaises(ValueError):self.calculate([row(power=value),row(3600)])
    def test_exact_duplicate_and_input_order(self):
        records=[row(),row(3600)]
        self.assertEqual(self.calculate(records),self.calculate([records[1],records[0],copy.deepcopy(records[0])]))
    def test_changed_duplicate_and_changed_trip_are_conflicts(self):
        original=row()
        for field,value in [('active_power_total',11),('oil_temp_trip',1)]:
            altered=copy.deepcopy(original);altered[field]=value
            with self.assertRaises(EnergyConflictError):self.calculate([original,altered,row(3600)])
    def test_known_modulus_and_unknown_rollover(self):
        records=[row(counter=250),row(3600,counter=5)]
        self.assertEqual(self.calculate(records,config('COUNTER',counter_modulus=256,rollover_reference='explicit unsigned counter map'))['consumed_kwh'],11)
        unknown=self.calculate(records,config('COUNTER'))
        self.assertEqual(unknown['reset_count'],1);self.assertIsNone(unknown['consumed_kwh'])
        with self.assertRaises(ValueError):config('COUNTER',counter_modulus=256)
    def test_reset_evidence_overrides_wrap(self):
        records=[row(counter=250),row(3600,counter=5)]
        r=self.calculate(records,config('COUNTER',counter_modulus=256,rollover_reference='map',reset_event_times=(records[1]['timestamp'],)))
        self.assertEqual(r['reset_count'],1);self.assertIsNone(r['covered_consumed_kwh'])
    def test_modulus_out_of_range_excluded(self):
        r=self.calculate([row(counter=260),row(3600,counter=5)],config('COUNTER',counter_modulus=256,rollover_reference='map'))
        self.assertIsNone(r['consumed_kwh']);self.assertIn('COUNTER_OUTSIDE_MODULUS',r['limitation_codes'])
    def test_unknown_units_and_unverified_measurements(self):
        for method,field in [('POWER','active_power_total'),('COUNTER','energy_kwh')]:
            for key,value in [('field_units','UNKNOWN'),('field_verification','UNVERIFIED')]:
                rows=[row(counter=100),row(3600,counter=110)]
                for item in rows:item['acquisition'][key][field]=value
                r=self.calculate(rows,config(method));self.assertIsNone(r['consumed_kwh']);self.assertIsNone(r['covered_consumed_kwh'])
    def test_unknown_sign_or_counter_semantics_unavailable(self):
        self.assertIsNone(self.calculate([row(),row(3600)],config(power_sign='UNKNOWN'))['consumed_kwh'])
        self.assertIsNone(self.calculate([row(counter=100),row(3600,counter=110)],config('COUNTER',counter_semantics=None))['consumed_kwh'])
    def test_import_export_zero_crossing_and_unsigned_policy(self):
        records=[row(power=-10),row(3600,power=10)]
        r=self.calculate(records,config(power_sign='IMPORT_POSITIVE'))
        self.assertAlmostEqual(r['import_kwh'],2.5);self.assertAlmostEqual(r['export_kwh'],2.5)
        self.assertIsNone(self.calculate(records)['consumed_kwh'])
    def test_export_counter_is_not_import_consumption(self):
        r=self.calculate([row(counter=100),row(3600,counter=110)],config('COUNTER',counter_semantics='CUMULATIVE_EXPORT'))
        self.assertEqual(r['export_kwh'],10);self.assertIsNone(r['consumed_kwh'])
    def test_unsupported_boundaries_are_not_extrapolated(self):
        r=self.calculate([row(600),row(3000)],seconds=3600)
        self.assertAlmostEqual(r['coverage_fraction'],2/3);self.assertIsNone(r['consumed_kwh']);self.assertEqual(len(r['missing_intervals']),2)
        counter=calculate_energy([row(counter=100),row(3600,counter=110)],'HX-A',event_time(START)+timedelta(seconds=600),event_time(START)+timedelta(seconds=3000),config('COUNTER'))
        self.assertIsNone(counter['consumed_kwh'])
    def test_explicit_linear_boundary_interpolation(self):
        records=[row(power=0),row(3600,power=10)]
        r=calculate_energy(records,'HX-A',event_time(START)+timedelta(seconds=900),event_time(START)+timedelta(seconds=2700),config(allow_boundary_interpolation=True))
        self.assertEqual(r['consumed_kwh'],2.5);self.assertEqual(r['coverage_fraction'],1.)
        schema_validate('energy.schema.json',r)
    def test_declared_interval_average(self):
        for semantics,value in [('INTERVAL_AVERAGE_START',10),('INTERVAL_AVERAGE_END',20)]:
            r=self.calculate([row(power=10),row(3600,power=20)],config(power_semantics=semantics))
            self.assertEqual(r['consumed_kwh'],value);self.assertEqual(r['load_profile'],[]);self.assertIsNone(r['peak_kw'])
    def test_time_asset_and_policy_validation(self):
        for records in ([row(),row(3600,asset='OTHER')],[dict(row(),timestamp='2026-10-09T00:00:00'),row(3600)]):
            with self.assertRaises(ValueError):self.calculate(records)
        with self.assertRaises(ValueError):config(maximum_gap_seconds=0)
        with self.assertRaises(ValueError):calculate_energy([], 'HX-A',START,START,config())
        with self.assertRaises(ValueError):calculate_energy([], 'HX-A',START,event_time(START)+timedelta(days=8),config())
    def test_legacy_provenance_not_inferred_from_source_name(self):
        rows=[row(),row(3600)]
        for item in rows:item.pop('acquisition')
        r=self.calculate(rows);self.assertIsNone(r['source_kind']);self.assertIsNone(r['consumed_kwh'])
    def test_replay_lineage_and_playback_speed(self):
        rows=[row(source='REPLAYED',asset='REPLAY-1'),row(3600,source='REPLAYED',asset='REPLAY-1')]
        one=self.calculate(rows);twenty=self.calculate(copy.deepcopy(rows))
        self.assertEqual(one,twenty);self.assertEqual(one['source_kind'],'REPLAYED');self.assertEqual(one['energy_method'],'SIMULATED')
        self.assertTrue(any('run-1' in assumption for assumption in one['assumptions']))
        changed=copy.deepcopy(rows);changed[-1]['acquisition']['replay_run_id']='run-2'
        with self.assertRaises(ValueError):self.calculate(changed)
    def test_real_verified_power_method(self):
        r=self.calculate([row(source='LIVE'),row(3600,source='LIVE')])
        self.assertEqual(r['energy_method'],'CALCULATED_POWER');self.assertEqual(r['active_power_unit_status'],'VERIFIED')
    def test_loss_efficiency_oracle_and_missing_inputs(self):
        records=[row(),row(7200)]
        for item in records:
            item.update(current_l1=10,current_l2=10,current_l3=10)
        r=self.calculate(records,loss_model=loss_model())
        self.assertAlmostEqual(r['loss_kw'],1);self.assertAlmostEqual(r['loss_kwh'],2)
        self.assertAlmostEqual(r['efficiency_percent'],90.9090909091,places=8)
        missing=self.calculate(records)
        self.assertIsNone(missing['loss_kw']);self.assertIsNone(missing['efficiency_percent'])
    def test_ineligible_loss_boundary_units_live_synthetic_and_zero_output(self):
        records=[row(power=0),row(3600,power=0)]
        for item in records:item.update(current_l1=10,current_l2=10,current_l3=10)
        self.assertIsNone(self.calculate(records,loss_model=loss_model())['efficiency_percent'])
        for model in (replace(loss_model(),energized=False),replace(loss_model(),output_boundary_reference=None),replace(loss_model(),measurement_side='HV')):
            self.assertIsNone(self.calculate(records,loss_model=model)['loss_kw'])
        self.assertIsNone(efficiency_percent(0,0));self.assertIsNone(efficiency_percent(None,1))
        with self.assertRaises(ValueError):efficiency_percent(10,-1)
        live=[row(source='LIVE'),row(3600,source='LIVE')]
        self.assertIsNone(self.calculate(live,loss_model=loss_model())['loss_kw'])
    def test_equal_service_simulated_conservation(self):
        records=[row(),row(7200)]
        for item in records:item.update(current_l1=10,current_l2=10,current_l3=10)
        r=self.calculate(records,loss_model=loss_model(),alternative_loss_model=loss_model('fictional-alternative-v1',.4,.2))
        self.assertEqual(r['consumed_kwh'],20);self.assertAlmostEqual(r['estimated_savings_kwh'],.8)
        self.assertIn('Simulated opportunity',r['conservation_recommendation'])
        self.assertTrue(any('Same delivered service 20.0 kWh' in e for e in r['conservation_evidence']))
    def test_no_loss_from_partial_current_or_temporal_support(self):
        records=[row(),row(3600),row(7200,power=None)]
        for item in records:item.update(current_l1=10,current_l2=10,current_l3=10)
        r=self.calculate(records,loss_model=loss_model());self.assertIsNone(r['loss_kwh'])
        records[-1]['active_power_total']=10;records[1]['current_l1']=None
        r=self.calculate(records,loss_model=loss_model());self.assertIsNone(r['loss_kwh'])
    def test_counter_profile_unavailable_and_empty_window(self):
        records=[row(power=None,counter=100),row(3600,power=None,counter=110)]
        r=self.calculate(records,config('COUNTER'));self.assertEqual(r['load_profile'],[])
        self.assertIn('INSTANTANEOUS_LOAD_PROFILE_UNAVAILABLE',r['limitation_codes'])
        r=calculate_energy([],'HX-A',START,event_time(START)+timedelta(hours=1),config())
        self.assertIsNone(r['consumed_kwh']);self.assertEqual(r['coverage_fraction'],0)
        schema_validate('energy.schema.json',r)
    def test_counter_units_do_not_require_instantaneous_power_units(self):
        records=[row(power=None,counter=100),row(3600,power=None,counter=110)]
        for item in records:
            item['acquisition']['field_units']['active_power_total']='UNKNOWN'
            item['acquisition']['field_verification']['active_power_total']='UNVERIFIED'
        r=self.calculate(records,config('COUNTER'))
        self.assertEqual(r['consumed_kwh'],10);self.assertEqual(r['active_power_unit_status'],'UNKNOWN')
    def test_large_integer_counter_preserves_small_difference(self):
        r=self.calculate([row(counter=2**60),row(3600,counter=2**60+1)],config('COUNTER'))
        self.assertEqual(r['consumed_kwh'],1)
    def test_reset_and_gap_diagnostics_both_survive(self):
        r=self.calculate([row(counter=110),row(3600,counter=2)],config('COUNTER',maximum_gap_seconds=10))
        self.assertEqual(r['reset_count'],1);self.assertEqual(r['gap_count'],1);self.assertIsNone(r['consumed_kwh'])
    def test_record_bound_rejects_without_truncating(self):
        with self.assertRaises(ValueError):self.calculate([row(),row(1),row(2)],config(maximum_records=2))
    def test_conservation_rejects_different_service_boundary(self):
        records=[row(),row(3600)]
        for item in records:item.update(current_l1=10,current_l2=10,current_l3=10)
        alternative=replace(loss_model('alternative',.4,.2),output_boundary_reference='different physical output boundary')
        r=self.calculate(records,loss_model=loss_model(),alternative_loss_model=alternative)
        self.assertIsNone(r['estimated_savings_kwh']);self.assertIn('SIMULATED_EQUAL_SERVICE_COMPARISON_INELIGIBLE',r['limitation_codes'])
    def test_sustained_advice_does_not_sum_disconnected_overload(self):
        from ml.pipeline.asset_config import AssetConfig
        from ml.tests._h05_fixtures import example
        asset=AssetConfig.from_dict(example('asset-valid'))
        records=[row(0),row(200),row(400),row(600),row(800),row(1000)]
        for i,item in enumerate(records):
            item['apparent_power_total']=120 if i in (0,1,4,5) else 50
            item['acquisition']['field_units']['apparent_power_total']='kVA'
            item['acquisition']['field_verification']['apparent_power_total']='SYNTHETIC'
        r=self.calculate(records,config(overload_duration_seconds=300),asset_config=asset)
        self.assertIsNone(r['conservation_recommendation'])
    def test_sustained_loading_advice_without_loss(self):
        from ml.pipeline.asset_config import AssetConfig
        asset=AssetConfig.from_dict(__import__('ml.tests._h05_fixtures',fromlist=['example']).example('asset-valid'))
        records=[row(),row(3600)]
        for item in records:
            item['apparent_power_total']=120
            item['acquisition']['field_units']['apparent_power_total']='kVA'
            item['acquisition']['field_verification']['apparent_power_total']='SYNTHETIC'
        r=self.calculate(records,config(overload_duration_seconds=300),asset_config=asset)
        self.assertIn('Operator review',r['conservation_recommendation']);self.assertIsNone(r['loss_kw'])

if __name__=='__main__':unittest.main()
