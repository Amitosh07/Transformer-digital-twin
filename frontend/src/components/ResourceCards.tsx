import type { RUL, Energy, Asset, Projection } from '../api/contracts';

import { displayNumber } from '../monitoring';



export const panel = 'bg-[#0A0E17] border border-slate-800 rounded-xl p-5 shadow-xl space-y-3';

export function RULCard({ result, message, projection }: { result?: RUL | null; message?: string; projection?: Projection | null }) {

  return <section className={panel} aria-label="RUL"><h3 className="text-lg text-amber-300">Remaining scenario time / RUL</h3>

    {!result ? <p>{message || 'Not yet available — no persisted RUL result'}</p> : <>

      <p>{result.simulated ? 'SIMULATED — scenario endpoint, not a real transformer lifespan' : result.rul_status === 'CONDITIONAL_ESTIMATE' ? 'Conditional estimate' : 'Operational prerequisites / status'}</p>

      <p>{result.rul_status}</p><strong>{displayNumber(result.rul_value, 'h')}</strong>

      {result.rul_status === 'NO_CROSSING_WITHIN_HORIZON' && <p>No finite crossing within the declared horizon; no infinite lifespan claim.</p>}

      <p>Method: {result.rul_method} · Source: {result.source_kind ?? 'UNKNOWN'}</p>

      <p>Target: {result.rul_target_definition} · Endpoint: {displayNumber(result.end_threshold, result.degradation_unit)}</p>

      <p>Scenario: {result.future_duty_scenario ?? 'Unspecified'} · Horizon: {displayNumber(result.forecast_horizon_hours, 'h')}</p>

      <p>Bounds: {displayNumber(result.rul_lower, 'h')} – {displayNumber(result.rul_upper, 'h')} · {result.uncertainty_kind ?? 'No uncertainty estimate'}</p>

      <p>Coverage: {displayNumber(result.coverage_fraction, 'fraction')} · {result.coverage_start ?? 'Unknown'} → {result.coverage_end ?? 'Unknown'}</p>

      <p>Result event: {result.timestamp} · Model: {result.model_version} · Configuration: {result.config_version ?? 'Unknown'}</p>

      {projection?.timestamp && Date.parse(projection.timestamp) === Date.parse(result.timestamp) && projection.projected_curve.length > 0 && projection.forecast_horizon_hours && projection.end_threshold && <figure aria-label="Synthetic degradation projection">

        <svg viewBox="0 0 500 160" role="img" aria-label="Declared degradation trajectory and endpoint" className="w-full">

          <line x1="20" x2="480" y1="20" y2="20" stroke="#f59e0b" strokeDasharray="5 5" />

          <polyline fill="none" stroke="#22d3ee" strokeWidth="2" points={projection.projected_curve.map(p => `${20+460*p.elapsed_hours/projection.forecast_horizon_hours!},${140-120*p.degradation/projection.end_threshold!}`).join(' ')} />

          <text x="20" y="157" fill="white" fontSize="10">0 hours</text><text x="390" y="157" fill="white" fontSize="10">{projection.forecast_horizon_hours} hours</text>

        </svg>

        <figcaption>Actual H05 scenario points · D ({projection.degradation_unit ?? 'unknown unit'}) · endpoint {projection.end_threshold}. Scenario bounds are not confidence intervals.</figcaption>

      </figure>}

      <p>Required inputs: {result.required_inputs.join(', ') || 'None reported'}</p>

      <p>Assumptions: {result.assumptions.join('; ') || 'None supplied'}</p><p>Limitations: {result.limitation_codes.join(', ') || 'None supplied'}</p>

    </>}

  </section>;

}

export function EnergyCard({ result, message }: { result?: Energy | null; message?: string }) {

  return <section className={panel} aria-label="Energy"><h3 className="text-lg text-cyan-300">Energy over event-time window</h3>

    {!result ? <p>{message || 'Not yet available — energy resource requires H05/H06'}</p> : <>

      <p>{result.energy_status} · {result.source_kind ?? 'UNKNOWN'} · Unit evidence: {result.active_power_unit_status}</p>

      <p>Method: {result.energy_method} · Calculation: {result.calculation_method}</p>

      <strong>{displayNumber(result.consumed_kwh, result.energy_unit)}</strong>

      <p>Covered total: {displayNumber(result.covered_consumed_kwh, result.energy_unit)} · Peak: {displayNumber(result.peak_kw, result.provenance.power_unit)}</p>

      <p>{result.window_start} → {result.window_end}</p>

      <p>Coverage: {result.coverage_seconds} s · {result.coverage_fraction} fraction · Gaps: {result.gap_count} · Resets: {result.reset_count}</p>

      <ul>{result.missing_intervals.map((interval, i) => <li key={i}>{interval.start} → {interval.end}: {interval.reason}</li>)}</ul>

      <p>Loss: {displayNumber(result.loss_kw, 'kW')} / {displayNumber(result.loss_kwh, 'kWh')} · Efficiency: {displayNumber(result.efficiency_percent, 'percent')} · Loss method: {result.loss_method ?? 'Unavailable'}</p>

      <p>Scenario savings estimate: {displayNumber(result.estimated_savings_kwh, 'kWh')} — supplied advisory only, not measured savings.</p>

      <p>{result.conservation_recommendation ?? 'No supported recommendation'} · Evidence: {result.conservation_evidence.join('; ') || 'Unavailable'}</p>

      <p>Counter: {result.provenance.counter_semantics ?? 'Unknown'} · Continuity: {result.provenance.continuity_evidence ?? 'Unknown'} · Side: {result.provenance.measurement_side}</p>

      <p>Assumptions: {result.assumptions.join('; ') || 'None supplied'} · Limitations: {result.limitation_codes.join(', ') || 'None supplied'}</p>

      <details><summary>Supplied load profile ({result.load_profile.length} observations)</summary>{result.load_profile.length === 0 ? <p>No observations</p> : result.load_profile.map((p,i) => <p key={i}>{p.timestamp}: {displayNumber(p.active_power_total,result.provenance.power_unit)}</p>)}</details>

    </>}

  </section>;

}

export function NameplateCard({ asset }: { asset: Asset }) {

  const fields: [string, string, number | string | null | undefined][] = [

    ['Rated power','rated_power_kva',asset.rated_power_kva], ['HV voltage','rated_voltage_hv',asset.rated_voltage_hv], ['LV voltage','rated_voltage_lv',asset.rated_voltage_lv],

    ['Rated line current','rated_current_a',asset.rated_current_a], ['Rated frequency','rated_frequency_hz',asset.rated_frequency_hz], ['Vector group','vector_group',asset.vector_group],

    ['Impedance','impedance_percent',asset.impedance_percent], ['Cooling','cooling_class',asset.cooling_class], ['Oil type','oil_type',asset.oil_type], ['Insulation','insulation_type',asset.insulation_type],

  ];

  return <section className={panel} aria-label="Nameplate"><h3 className="text-lg">Asset configuration: {asset.name}</h3>

    <p>{asset.configuration_metadata?.status ?? 'UNVERIFIED — evidence missing'} · Version: {asset.configuration_metadata?.version ?? 'Unknown'} · Side: {asset.measurement_side ?? 'UNKNOWN'}</p>

    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3">{fields.map(([label,field,value]) => {

      const meta = asset.configuration_metadata?.field_metadata[field];

      return <div key={field}><dt className="text-slate-400">{label}</dt><dd>{typeof value === 'number' ? displayNumber(value,meta?.unit) : value ?? 'Configuration required'} · {meta?.verification ?? 'UNVERIFIED'}<div className="text-xs">{meta?.provenance ?? 'Provenance missing'} · Evidence: {meta?.evidence_reference ?? 'Missing'}</div></dd></div>;

    })}</dl>

    <details><summary>Temperature rise, CT/PT ratios and loss parameters with field evidence</summary>

      <pre className="text-xs whitespace-pre-wrap break-words">{JSON.stringify({ temperature_rise_limits:asset.temperature_rise_limits ?? null, ct_ratio:asset.ct_ratio ?? null, pt_ratio:asset.pt_ratio ?? null, loss_parameters:asset.loss_parameters ?? null, field_metadata:asset.configuration_metadata?.field_metadata ?? null },null,2)}</pre>

      <p>Populated values alone do not establish verification or standards compliance.</p>

    </details>

  </section>;

}

