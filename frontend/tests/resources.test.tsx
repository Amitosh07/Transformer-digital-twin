import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { EnergyCard, NameplateCard, RULCard } from '../src/components/ResourceCards';
import { HealthIndexDial } from '../src/components/HealthIndexDial';
import { PrescriptiveActionCard } from '../src/components/PrescriptiveActionCard';
import { chartPath, ThermalResidualChart, thermalPoints } from '../src/components/ThermalResidualChart';
import { contactLabel, displayNumber, freshness, thermalReady } from '../src/monitoring';
import { makeLatest, rulOracle, energyOracle } from './fixtures';
import { energySchema, rulSchema } from '../src/api/contracts';
import { codeLabel, unitLabel, valueLabel } from '../src/components/console/presentation';
it('rejects contradictory unavailable resource numbers',()=>{
 expect(energySchema.safeParse({...energyOracle('unknown-units'),consumed_kwh:20}).success).toBe(false);
 expect(rulSchema.safeParse({...rulOracle('zero-rate').rul!,rul_value:80}).success).toBe(false);
});
const term = (label: string) => screen.getByText(label, { selector: 'dt' }).nextElementSibling;
it('renders conditional RUL distinctly from a simulated scenario',()=>{
 render(<RULCard result={{...rulOracle('constant').rul!,rul_status:'CONDITIONAL_ESTIMATE',simulated:false,source_kind:'LIVE'}}/>);
 expect(screen.getByText('Conditional estimate')).toBeVisible();expect(screen.getByText('80.00 h')).toBeVisible();expect(screen.queryByText(/Simulated scenario/)).not.toBeInTheDocument();
});
it('renders H00 synthetic RUL with hours, assumptions and range',()=>{
 render(<RULCard result={rulOracle('constant').rul}/>);expect(screen.getByText('80.00 h')).toBeVisible();expect(screen.getByText(/Simulated scenario endpoint — not a real transformer lifespan/)).toBeVisible();expect(term('Uncertainty')).toHaveTextContent('Scenario range');expect(screen.getByText('Assumptions')).toBeVisible();
});
it('renders zero separately from unavailable RUL',()=>{
 render(<RULCard result={rulOracle('endpoint').rul}/>);expect(screen.getByText('0.00 h')).toBeVisible();expect(screen.getByText('End threshold reached')).toBeVisible();
});
it('renders no crossing without presenting infinity',()=>{
 render(<RULCard result={rulOracle('zero-rate').rul}/>);expect(screen.getByText('Unavailable',{selector:'.resource-value'})).toBeVisible();expect(screen.getByText(/No finite crossing/)).toBeVisible();expect(screen.queryByText(/Infinity/)).not.toBeInTheDocument();
});
it('renders operational insufficient-input reasons without a lifespan',()=>{
 const result=rulOracle('real-insufficient').rul!;render(<RULCard result={result}/>);expect(screen.getByText('Insufficient data')).toBeVisible();expect(screen.getByText('Unavailable',{selector:'.resource-value'})).toBeVisible();expect(screen.getByText('Required inputs')).toBeVisible();
 expect(screen.getByText('Technical details').closest('details')).toHaveTextContent('INSUFFICIENT_DATA');
});
it.each(['constant-10kw-2h','linear-ramp','counter-reset','long-gap','unknown-units'])('renders H00 energy %s without estimating missing loss or efficiency',(name)=>{
 const result=energyOracle(name);render(<EnergyCard result={result}/>);expect(term('Method')).toHaveTextContent(codeLabel(result.energy_method));
 expect(screen.getByText(result.consumed_kwh==null?'Unavailable':valueLabel(result.consumed_kwh,'kWh'),{selector:'strong'})).toBeVisible();
 expect(term('Loss power')).toHaveTextContent('Unavailable');expect(term('Efficiency')).toHaveTextContent('Unavailable');expect(term('Resets')).toHaveTextContent(String(result.reset_count));
 expect(screen.getByText('Technical details').closest('details')).toHaveTextContent(result.energy_method);
});
it('does not infer units or verified configuration from positive values',()=>{
 const asset=makeLatest().transformer;asset.configuration_metadata=null;render(<NameplateCard asset={asset}/>);
 expect(screen.getAllByText(/^100 \(unit unknown\)$/).length).toBeGreaterThan(0);expect(screen.getAllByText(/Unverified/).length).toBeGreaterThan(1);expect(screen.getAllByText(/Configuration required/).length).toBeGreaterThan(0);
});
it('distinguishes null, zero, unknown contact and cleared contact',()=>{
 expect(displayNumber(null,'A')).toBe('Unavailable');expect(displayNumber(0,'A')).toBe('0 A');expect(contactLabel(null)).toBe('Unknown contact');expect(contactLabel(0)).toBe('Cleared');expect(contactLabel(1)).toBe('Active');
 const {rerender}=render(<HealthIndexDial analytics={{...makeLatest().analytics!,health_index:0}}/>);expect(screen.getByText('0.00')).toBeVisible();
 rerender(<HealthIndexDial analytics={null}/>);expect(screen.getAllByText(/Unavailable/).length).toBeGreaterThan(0);expect(screen.queryByText('0.00')).not.toBeInTheDocument();
});
it('keeps operational risk gated even if an unreleased response supplies a number',()=>{
 render(<PrescriptiveActionCard analytics={{...makeLatest().analytics!,fault_risk:.9,prediction_confidence:.99}}/>);
 expect(term('Operational fault risk')).toHaveTextContent('Unavailable — release prerequisites unmet');expect(term('Forecast confidence')).toHaveTextContent('Unavailable — unreleased');
 expect(screen.queryByText(/0\.90 \(probability\)|0\.99 \(fraction\)/)).not.toBeInTheDocument();
});
it('formats display units and precision without changing values or filling nulls',()=>{
 expect(valueLabel(36.794,'DEG_C')).toBe('36.79 °C');expect(valueLabel(36.794,'DEG C')).toBe('36.79 °C');expect(valueLabel(36.794,'-C')).toBe('36.79 °C');expect(valueLabel(36.794,'_C')).toBe('36.79 °C');expect(valueLabel(36.794,'°C')).toBe('36.79 °C');
 expect(valueLabel(84.9,'percent')).toBe('84.90 %');expect(valueLabel(0.9231,'1')).toBe('0.92');expect(valueLabel(10.869,'kW')).toBe('10.87 kW');
 expect(valueLabel(null,'DEG_C')).toBe('Unavailable');expect(valueLabel(undefined,'kW')).toBe('Unavailable');expect(valueLabel(0,'A')).toBe('0.00 A');
 expect(valueLabel(12.3456,'UNKNOWN')).toBe('12.35 (unit unknown)');expect(valueLabel(12.3456,null)).toBe('12.35 (unit unknown)');expect(valueLabel(1,'STATUS')).toBe('1 (status)');
 expect(unitLabel('K')).toBe('K');expect(unitLabel('UNKNOWN')).toBeNull();
 const raw={value:36.794};valueLabel(raw.value,'DEG_C');expect(raw.value).toBe(36.794);
 expect(codeLabel('INSUFFICIENT_DATA')).toBe('Insufficient data');expect(codeLabel('RAPID_TEMP_RISE')).toBe('Rapid temp rise');expect(codeLabel('MQTT_UNAVAILABLE')).toBe('MQTT unavailable');
 expect(codeLabel('Inspect supplied backend evidence')).toBe('Inspect supplied backend evidence');expect(codeLabel('fictional-modbus')).toBe('fictional-modbus');expect(codeLabel(null)).toBe('Unavailable');
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

