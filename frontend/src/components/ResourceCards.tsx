import type { RUL, Energy, Asset, Projection } from '../api/contracts';

import { clockLabel, codeLabel, numberLabel, timeLabel, unitLabel, valueLabel } from './console/presentation';
import { CodeList, KeyValues, TechnicalDetails } from './console/TelemetryPanels';



export const panel = 'bg-[#0A0E17] border border-slate-800 rounded-xl p-5 shadow-xl space-y-3';
const card = panel + ' resource-card';

function TextList({ items, empty = 'None supplied' }: { items: string[]; empty?: string }) {
  return items.length ? <ul className="text-list">{items.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p>{empty}</p>;
}
const windowLabel = (start?: string | null, end?: string | null) => `${start ? timeLabel(start) : 'Unknown start'} to ${end ? timeLabel(end) : 'unknown end'}`;
const degradationUnit = (unit?: string | null) => unit === '1' ? 'dimensionless' : unitLabel(unit) ?? 'unknown unit';

export function RULCard({ result, message, projection }: { result?: RUL | null; message?: string; projection?: Projection | null }) {

  return <section className={card} aria-label="RUL"><h3 className="text-lg text-amber-300">Remaining scenario time (RUL)</h3>

    {!result ? <p>{message || 'Not yet available — no persisted RUL result'}</p> : <>

      {result.simulated && <p className="resource-notice">Simulated scenario endpoint — not a real transformer lifespan.</p>}

      <div className="resource-hero"><div><span>Status</span><strong className="resource-status">{codeLabel(result.rul_status)}</strong></div><div><span>Remaining time</span><strong className="resource-value">{valueLabel(result.rul_value, 'h')}</strong></div></div>

      {result.rul_status === 'NO_CROSSING_WITHIN_HORIZON' && <p className="resource-notice">No finite crossing within the declared horizon; no infinite lifespan claim.</p>}

      <KeyValues items={[
        ['Method', codeLabel(result.rul_method)], ['Source', codeLabel(result.source_kind, 'Unknown')],
        ['Target', codeLabel(result.rul_target_definition)], ['Endpoint', valueLabel(result.end_threshold, result.degradation_unit)],
        ['Duty scenario', codeLabel(result.future_duty_scenario, 'Unspecified')], ['Forecast horizon', valueLabel(result.forecast_horizon_hours, 'h')],
        ['Bounds', `${valueLabel(result.rul_lower, 'h')} – ${valueLabel(result.rul_upper, 'h')}`], ['Uncertainty', codeLabel(result.uncertainty_kind, 'No uncertainty estimate')],
        ['Coverage', valueLabel(result.coverage_fraction, 'fraction')], ['Coverage window', windowLabel(result.coverage_start, result.coverage_end)],
      ]}/>

      {projection?.timestamp && Date.parse(projection.timestamp) === Date.parse(result.timestamp) && projection.projected_curve.length > 0 && projection.forecast_horizon_hours && projection.end_threshold && <figure className="resource-figure" aria-label="Synthetic degradation projection">

        <svg viewBox="0 0 500 175" role="img" aria-label="Declared degradation trajectory and endpoint" className="w-full">

          <line x1="20" x2="480" y1="140" y2="140" stroke="#c9d6e0" />

          <line x1="20" x2="480" y1="20" y2="20" stroke="#c77a12" strokeDasharray="5 5" />

          <text x="480" y="14" fill="#8a5a12" fontSize="10" textAnchor="end">Endpoint {numberLabel(projection.end_threshold)}</text>

          <polyline fill="none" stroke="#1d6fa3" strokeWidth="2" points={projection.projected_curve.map(p => `${20+460*p.elapsed_hours/projection.forecast_horizon_hours!},${140-120*p.degradation/projection.end_threshold!}`).join(' ')} />

          <text x="20" y="156" fill="#526d83" fontSize="10">0 h</text><text x="480" y="156" fill="#526d83" fontSize="10" textAnchor="end">{numberLabel(projection.forecast_horizon_hours, 'compact')} h</text>

          <text x="250" y="170" fill="#526d83" fontSize="10" textAnchor="middle">Elapsed scenario time</text>

        </svg>

        <figcaption>Backend scenario projection of degradation ({degradationUnit(projection.degradation_unit)}) against the declared endpoint (dashed). Scenario bounds are not confidence intervals.</figcaption>

      </figure>}

      <h4>Required inputs</h4><TextList items={result.required_inputs} empty="None reported"/>

      <h4>Assumptions</h4><TextList items={result.assumptions}/>

      <h4>Limitations</h4><TextList items={result.limitation_codes.map(c => codeLabel(c))}/>

      <TechnicalDetails><KeyValues items={[
        ['Status code', result.rul_status], ['Method code', result.rul_method], ['Model version', result.model_version], ['Configuration', result.config_version ?? 'Unknown'],
        ['Result event', result.timestamp], ['Limitation codes', <CodeList key="codes" codes={result.limitation_codes}/>],
      ]}/></TechnicalDetails>

    </>}

  </section>;

}

/** Supplied points only; null readings and declared gaps break the line instead of being joined. */
function profilePath(points: Energy['load_profile'], min: number, range: number, maxGapSeconds: number | null) {
  const start = Date.parse(points[0].timestamp), span = Math.max(1, Date.parse(points.at(-1)!.timestamp) - start);
  let last: number | null = null;
  return points.map(p => {
    const time = Date.parse(p.timestamp), v = p.active_power_total;
    if (v == null) { last = null; return ''; }
    const move = last == null || (maxGapSeconds != null && time - last > maxGapSeconds * 1000); last = time;
    return `${move ? 'M' : 'L'}${62 + (time - start) / span * 418},${range ? 130 - (v - min) / range * 110 : 75}`;
  }).join(' ');
}
function LoadProfileChart({ points, unit, maxGapSeconds }: { points: Energy['load_profile']; unit: string | null; maxGapSeconds: number | null }) {
  const symbol = unitLabel(unit);
  const values = points.map(p => p.active_power_total).filter((v): v is number => v != null);
  if (points.length < 2 || !values.length) return null;
  if (!symbol) return <p className="resource-note">Load profile not charted: power unit unknown.</p>;
  const min = Math.min(...values), max = Math.max(...values), range = max - min;
  const path = profilePath(points, min, range, maxGapSeconds);
  return <figure className="resource-figure" aria-label="Supplied load profile">
    <svg viewBox="0 0 500 175" role="img" aria-label={`Active power load profile (${symbol})`} className="w-full">
      <text x="4" y="10" fill="#4f6578" fontSize="10" fontWeight="600">{symbol}</text>
      {(range ? [[20, max], [130, min]] : [[75, max]]).map(([y, v]) => <g key={y}><line x1="62" x2="480" y1={y} y2={y} stroke="#dce5ed" strokeDasharray="3 3"/><text x="56" y={y + 4} fill="#62758a" fontSize="10" textAnchor="end">{numberLabel(v)}</text></g>)}
      <path d={path} fill="none" stroke="#1d6fa3" strokeWidth="2"/>
      <text x="62" y="152" fill="#526d83" fontSize="10">{clockLabel(points[0].timestamp)}</text><text x="480" y="152" fill="#526d83" fontSize="10" textAnchor="end">{clockLabel(points.at(-1)!.timestamp)}</text>
      <text x="271" y="170" fill="#526d83" fontSize="10" textAnchor="middle">Event time</text>
    </svg>
    <figcaption>Active power observations supplied with this energy result ({points.length} points). Missing readings{maxGapSeconds != null ? ` and gaps over ${numberLabel(maxGapSeconds, 'compact')} s` : ''} are shown as breaks.</figcaption>
  </figure>;
}

export function EnergyCard({ result, message }: { result?: Energy | null; message?: string }) {

  return <section className={card} aria-label="Energy"><h3 className="text-lg text-cyan-300">Energy over event-time window</h3>

    {!result ? <p>{message || 'Not yet available — energy resource requires H05/H06'}</p> : <>

      <p className="resource-meta">Status: {codeLabel(result.energy_status)} · Source: {codeLabel(result.source_kind, 'Unknown')} · Power unit evidence: {codeLabel(result.active_power_unit_status)}</p>

      <div className="resource-hero"><div><span>Consumed energy</span><strong className="resource-value">{valueLabel(result.consumed_kwh, result.energy_unit)}</strong></div><div><span>Window</span><small>{windowLabel(result.window_start, result.window_end)}</small></div></div>

      <KeyValues items={[
        ['Method', codeLabel(result.energy_method)], ['Calculation', codeLabel(result.calculation_method)],
        ['Covered total', valueLabel(result.covered_consumed_kwh, result.energy_unit)], ['Peak power', valueLabel(result.peak_kw, result.provenance.power_unit)],
        ['Coverage', `${numberLabel(result.coverage_seconds, 'compact')} s`], ['Coverage fraction', numberLabel(result.coverage_fraction)],
        ['Gaps', String(result.gap_count)], ['Resets', String(result.reset_count)],
        ['Loss power', valueLabel(result.loss_kw, 'kW')], ['Loss energy', valueLabel(result.loss_kwh, 'kWh')],
        ['Efficiency', valueLabel(result.efficiency_percent, '%')], ['Loss method', codeLabel(result.loss_method)],
      ]}/>

      <LoadProfileChart points={result.load_profile} unit={result.provenance.power_unit} maxGapSeconds={result.provenance.maximum_gap_seconds}/>

      {result.missing_intervals.length > 0 && <><h4>Missing intervals</h4><TextList items={result.missing_intervals.map(interval => `${windowLabel(interval.start, interval.end)}: ${codeLabel(interval.reason)}`)}/></>}

      <p>Scenario savings estimate: {valueLabel(result.estimated_savings_kwh, 'kWh')} — supplied advisory only, not measured savings.</p>

      <p>Recommendation: {result.conservation_recommendation ?? 'No supported recommendation'}</p>

      {result.conservation_evidence.length > 0 && <TextList items={result.conservation_evidence}/>}

      <KeyValues items={[['Counter semantics', codeLabel(result.provenance.counter_semantics, 'Unknown')], ['Continuity evidence', codeLabel(result.provenance.continuity_evidence, 'Unknown')], ['Measurement side', codeLabel(result.provenance.measurement_side)]]}/>

      <h4>Limitations</h4><TextList items={result.limitation_codes.map(c => codeLabel(c))}/>

      <details className="tech-details"><summary>Assumptions ({result.assumptions.length})</summary><div className="tech-details-body"><TextList items={result.assumptions}/></div></details>

      <details className="tech-details"><summary>Supplied load profile ({result.load_profile.length} observations)</summary><div className="tech-details-body">{result.load_profile.length === 0 ? <p>No observations</p> : result.load_profile.map((p,i) => <p key={i}>{timeLabel(p.timestamp)}: {valueLabel(p.active_power_total,result.provenance.power_unit)}</p>)}</div></details>

      <TechnicalDetails><KeyValues items={[
        ['Status code', result.energy_status], ['Method code', result.energy_method], ['Calculation code', result.calculation_method], ['Unit evidence code', result.active_power_unit_status],
        ['Counter unit', result.provenance.counter_unit ?? 'Unknown'], ['Calculation version', result.calculation_version], ['Configuration', result.config_version ?? 'Unknown'], ['Register map', result.map_version ?? 'Unknown'],
        ['Window', `${result.window_start} to ${result.window_end}`], ['Limitation codes', <CodeList key="codes" codes={result.limitation_codes}/>],
      ]}/></TechnicalDetails>

    </>}

  </section>;

}

export function NameplateCard({ asset }: { asset: Asset }) {

  const fields: [string, string, number | string | null | undefined][] = [

    ['Rated power','rated_power_kva',asset.rated_power_kva], ['HV voltage','rated_voltage_hv',asset.rated_voltage_hv], ['LV voltage','rated_voltage_lv',asset.rated_voltage_lv],

    ['Rated line current','rated_current_a',asset.rated_current_a], ['Rated frequency','rated_frequency_hz',asset.rated_frequency_hz], ['Vector group','vector_group',asset.vector_group],

    ['Impedance','impedance_percent',asset.impedance_percent], ['Cooling','cooling_class',asset.cooling_class], ['Oil type','oil_type',asset.oil_type], ['Insulation','insulation_type',asset.insulation_type],

  ];

  return <section className={card} aria-label="Nameplate"><h3 className="text-lg">Asset configuration: {asset.name}</h3>

    <p className="resource-meta">{asset.configuration_metadata ? codeLabel(asset.configuration_metadata.status) : 'Unverified — evidence missing'} · Version: {asset.configuration_metadata?.version ?? 'Unknown'} · Side: {codeLabel(asset.measurement_side, 'Unknown')}</p>

    <dl className="nameplate-grid grid grid-cols-1 sm:grid-cols-2 gap-3">{fields.map(([label,field,value]) => {

      const meta = asset.configuration_metadata?.field_metadata[field];

      return <div key={field}><dt className="text-slate-400">{label}</dt><dd><strong>{typeof value === 'number' ? valueLabel(value,meta?.unit,'compact') : value ?? 'Configuration required'}</strong> · {codeLabel(meta?.verification, 'Unverified')}<div className="text-xs">{meta?.provenance ?? 'Provenance missing'} · Evidence: {meta?.evidence_reference ?? 'Missing'}</div></dd></div>;

    })}</dl>

    <TechnicalDetails summary="Technical details: temperature rise, CT/PT ratios and loss parameters">

      <pre className="text-xs whitespace-pre-wrap break-words">{JSON.stringify({ temperature_rise_limits:asset.temperature_rise_limits ?? null, ct_ratio:asset.ct_ratio ?? null, pt_ratio:asset.pt_ratio ?? null, loss_parameters:asset.loss_parameters ?? null, field_metadata:asset.configuration_metadata?.field_metadata ?? null },null,2)}</pre>

      <p>Populated values alone do not establish verification or standards compliance.</p>

    </TechnicalDetails>

  </section>;

}
