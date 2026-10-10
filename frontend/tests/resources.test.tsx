import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { EnergyCard, NameplateCard, RULCard } from '../src/components/ResourceCards';
import { HealthIndexDial } from '../src/components/HealthIndexDial';
import { PrescriptiveActionCard } from '../src/components/PrescriptiveActionCard';
import { chartPath, ThermalResidualChart, thermalPoints } from '../src/components/ThermalResidualChart';
import { contactLabel, displayNumber, freshness, thermalReady } from '../src/monitoring';
import { makeLatest, rulOracle, energyOracle } from './fixtures';
import { energySchema, rulSchema } from '../src/api/contracts';
it('rejects contradictory unavailable resource numbers',()=>{
 expect(energySchema.safeParse({...energyOracle('unknown-units'),consumed_kwh:20}).success).toBe(false);
 expect(rulSchema.safeParse({...rulOracle('zero-rate').rul!,rul_value:80}).success).toBe(false);
});
it('renders conditional RUL distinctly from a simulated scenario',()=>{
 render(<RULCard result={{...rulOracle('constant').rul!,rul_status:'CONDITIONAL_ESTIMATE',simulated:false,source_kind:'LIVE'}}/>);
 expect(screen.getByText('Conditional estimate')).toBeVisible();expect(screen.getByText('80 h')).toBeVisible();
});
it('renders H00 synthetic RUL with hours, assumptions and range',()=>{
 render(<RULCard result={rulOracle('constant').rul}/>);expect(screen.getByText('80 h')).toBeVisible();expect(screen.getByText(/SIMULATED — scenario/)).toBeVisible();expect(screen.getByText(/SCENARIO_RANGE/)).toBeVisible();expect(screen.getByText(/Assumptions:/)).toBeVisible();
});
it('renders zero separately from unavailable RUL',()=>{
 render(<RULCard result={rulOracle('endpoint').rul}/>);expect(screen.getByText('0 h')).toBeVisible();expect(screen.getByText('END_THRESHOLD_REACHED')).toBeVisible();
});
it('renders no crossing without presenting infinity',()=>{
 render(<RULCard result={rulOracle('zero-rate').rul}/>);expect(screen.getByText('Unavailable')).toBeVisible();expect(screen.getByText(/No finite crossing/)).toBeVisible();expect(screen.queryByText('Infinity')).not.toBeInTheDocument();
});
it('renders operational insufficient-input reasons without a lifespan',()=>{
 render(<RULCard result={rulOracle('real-insufficient').rul}/>);expect(screen.getByText('INSUFFICIENT_DATA')).toBeVisible();expect(screen.getByText('Unavailable')).toBeVisible();expect(screen.getByText(/Required inputs:/)).toBeVisible();
});
it.each(['constant-10kw-2h','linear-ramp','counter-reset','long-gap','unknown-units'])('renders H00 energy %s without estimating missing loss or efficiency',(name)=>{
 const result=energyOracle(name);render(<EnergyCard result={result}/>);expect(screen.getByText(new RegExp('Method: '+result.energy_method))).toBeVisible();
 expect(screen.getByText(result.consumed_kwh==null?'Unavailable':result.consumed_kwh+' kWh',{selector:'strong'})).toBeVisible();
 expect(screen.getByText(/Loss: Unavailable/)).toBeVisible();expect(screen.getByText(new RegExp('Resets: '+result.reset_count))).toBeVisible();
});
it('does not infer units or verified configuration from positive values',()=>{
 const asset=makeLatest().transformer;asset.configuration_metadata=null;render(<NameplateCard asset={asset}/>);
 expect(screen.getByText(/100 \(unit unknown\)/)).toBeVisible();expect(screen.getAllByText(/UNVERIFIED/).length).toBeGreaterThan(1);expect(screen.getAllByText(/Configuration required/).length).toBeGreaterThan(0);
});
it('distinguishes null, zero, unknown contact and cleared contact',()=>{
 expect(displayNumber(null,'A')).toBe('Unavailable');expect(displayNumber(0,'A')).toBe('0 A');expect(contactLabel(null)).toBe('Unknown contact');expect(contactLabel(0)).toBe('Cleared');expect(contactLabel(1)).toBe('Active');
 const {rerender}=render(<HealthIndexDial analytics={{...makeLatest().analytics!,health_index:0}}/>);expect(screen.getByText('0')).toBeVisible();
 rerender(<HealthIndexDial analytics={null}/>);expect(screen.getAllByText(/Unavailable/).length).toBeGreaterThan(0);
});
it('keeps operational risk gated even if an unreleased response supplies a number',()=>{
 render(<PrescriptiveActionCard analytics={{...makeLatest().analytics!,fault_risk:.9,prediction_confidence:.99}}/>);
 expect(screen.getByText(/Operational fault risk: Unavailable/)).toBeVisible();expect(screen.getByText(/Forecast confidence: Unavailable/)).toBeVisible();
});
it('shows empty history and breaks chart segments at missing observations and gaps',()=>{
 render(<ThermalResidualChart data={[]}/>);expect(screen.getByText('No observations')).toBeVisible();
 const points=[{timestamp:'2026-10-09T00:00:00Z',observed:0,model:null},{timestamp:'2026-10-09T00:00:05Z',observed:null,model:null},{timestamp:'2026-10-09T00:01:00Z',observed:10,model:null}];
 const path=chartPath(points,'observed',10);expect(path.match(/M/g)).toHaveLength(2);expect(path).not.toContain('L ');
});
it('does not chart thermal model values with unknown units or unavailable readiness',()=>{
 const t=makeLatest().telemetry!;const a=makeLatest().analytics!;
 expect(thermalPoints([t],[a],null)[0]).toMatchObject({observed:null,model:null});
 expect(thermalReady({...a,metadata:{thermal_readiness:'READY',components:{thermal:{status:'UNAVAILABLE',unit:null,coverage_fraction:null,reasons:[]}}}})).toBe(false);
});
it('separates replay event age, legacy unknown provenance and failed API freshness',()=>{
 const t=makeLatest().telemetry!;const now=Date.parse(t.timestamp)+11000;
 expect(freshness(t,now,now,null)).toBe('Stale measurement');
 expect(freshness({...t,acquisition:{...t.acquisition!,source_kind:'REPLAYED'}},now,now,null)).toMatch(/Historical replay/);
 expect(freshness({...t,acquisition:null},now,now,null)).toBe('Unknown provenance');
 expect(freshness(t,now,now,'offline')).toMatch(/retained data/);
 expect(freshness(null,null,now,'offline')).toMatch(/Disconnected/);
});

