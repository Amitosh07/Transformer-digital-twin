import type { Latest, Telemetry } from '../../api/contracts';
import type { ReactNode } from 'react';
import { contactLabel, freshness, thermalReady } from '../../monitoring';
import { codeLabel, numberLabel, timeLabel, valueLabel as displayNumber } from './presentation';
import { Activity, Droplets, Gauge, Thermometer, Zap, Wrench } from 'lucide-react';

export function EventTime({ value }: { value?: string | null }) {
  return <time dateTime={value ?? undefined} title={value ?? undefined}>{timeLabel(value)}</time>;
}
export function Badge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: string }) {
  return <span className={'console-badge ' + tone}>{children}</span>;
}
/** Collapsed disclosure for exact backend identifiers, codes and raw payloads. */
export function TechnicalDetails({ children, summary = 'Technical details' }: { children: ReactNode; summary?: string }) {
  return <details className="tech-details"><summary>{summary}</summary><div className="tech-details-body">{children}</div></details>;
}
export function KeyValues({ items }: { items: [string, ReactNode][] }) {
  return <dl className="kv-list">{items.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}
export function CodeList({ codes }: { codes: string[] }) {
  return codes.length ? <code className="code-list">{codes.join(', ')}</code> : <span>None supplied</span>;
}
export function Reading({ label, field, record }: { label: string; field: keyof Telemetry; record?: Telemetry | null }) {
  const value = record?.[field];
  const verification = codeLabel(record?.acquisition?.field_verification[field], 'Unverified');
  return <div className="reading" title={`${verification} · ${record?.acquisition?.measurement_side ?? 'Unknown'} side`}><span>{label}</span><strong>{displayNumber(typeof value === 'number' ? value : null, record?.acquisition?.field_units[field])}</strong></div>;
}
export function TransformerDrawing({ small = false }: { small?: boolean }) {
  return <svg className={small ? 'transformer-mini' : 'transformer-drawing'} viewBox="0 0 320 260" role="img" aria-label="Transformer schematic, illustrative equipment only">
    <defs><linearGradient id={small ? 'tank-mini' : 'tank-detail'} x1="0" x2="1"><stop stopColor="#395b7a"/><stop offset=".5" stopColor="#6586a0"/><stop offset="1" stopColor="#35536e"/></linearGradient></defs>
    <path d="M40 226h240" stroke="#ccd7e1" strokeWidth="2"/>
    <path d="M105 57v-28m54 28v-38m55 38v-28" stroke="#203f5d" strokeWidth="10"/>
    {[105,159,214].map(x => <g key={x}>{[26,33,40,47].map(y => <rect key={y} x={x-11} y={y} width="22" height="5" rx="2" fill="#7492ab"/>)}</g>)}
    <rect x="88" y="65" width="143" height="140" rx="5" fill={`url(#${small ? 'tank-mini' : 'tank-detail'})`} stroke="#274760" strokeWidth="2"/>
    <path d="M88 65l22-12h121l-1 13M230 65l15-10v139l-15 11" fill="#90a6b8" stroke="#385770"/>
    {[63,72,81,235,244,253].map(x => <rect key={x} x={x} y="92" width="7" height="97" rx="2" fill="#53718a" stroke="#2e4c64"/>)}
    <rect x="99" y="78" width="120" height="8" fill="#abc0cd"/>
    <rect x="108" y="99" width="105" height="57" rx="5" fill="#223f55" stroke="#aac0d0"/>
    {[131,163,195].map(x => <g key={x}><rect x={x-10} y="107" width="19" height="40" fill="#b98451"/>{[108,114,120,126,132,138,144].map(y=><ellipse key={y} cx={x} cy={y} rx="10" ry="3" fill="#d7a773" stroke="#9e663d" strokeWidth="1"/>)}</g>)}
    <rect x="121" y="168" width="75" height="17" rx="2" fill="#c6d4df"/><path d="M112 205v15m98-15v15" stroke="#2c4c65" strokeWidth="10"/>
    <rect x="50" y="209" width="220" height="8" rx="2" fill="#526d82"/>
  </svg>;
}
export function SourceStrip({ data, lastSuccess, error, now }: { data?: Latest | null; lastSuccess: number | null; error: string | null; now: number }) {
  const t = data?.telemetry, a = data?.analytics, q = t?.acquisition;
  const reasons = data?.analytics_availability?.reasons ?? [];
  const verification = Object.entries(q?.field_verification ?? {});
  return <section className="source-strip" aria-label="Source and freshness">
    <div><span>Source</span><strong>{codeLabel(q?.source_kind, 'Unknown')} · {q?.source_name ?? 'Unknown provenance'}</strong><small>{q?.source_kind === 'SIMULATED' ? 'Generated telemetry, no physical transformer connection' : q?.source_kind === 'REPLAYED' ? `Historical replay of ${q.origin_kind} / ${q.origin_transformer_id}, run ${q.replay_run_id}` : 'A source label does not establish verified units'}</small></div>
    <div><span>Measurement time</span><strong><EventTime value={t?.timestamp}/></strong><small>{freshness(t, lastSuccess, now, error)}</small></div>
    <div><span>Analytics time</span><strong><EventTime value={a?.timestamp}/></strong><small>{a && t && Date.parse(a.timestamp) < Date.parse(t.timestamp) ? 'Analysis predates telemetry' : codeLabel(data?.analytics_availability?.status)}{reasons.length ? ` · ${reasons.map(r => codeLabel(r)).join(', ')}` : ''}</small></div>
    <div><span>Last API update</span><strong>{timeLabel(lastSuccess)}</strong></div>
    <TechnicalDetails><KeyValues items={[
      ['Snapshot', q?.snapshot_id ?? 'Unknown'], ['Received', timeLabel(t?.received_at)], ['Timezone evidence', q?.timezone_status ?? 'UNKNOWN'],
      ['Expected cadence', displayNumber(q?.expected_interval_seconds, 's', 'compact')], ['Register map', q?.map_version ?? 'Unknown'], ['Sequence', q?.sequence ?? 'Unknown'],
      ['Model bundle', a?.metadata?.versions?.bundle_id ?? 'Unknown'], ['Configuration version', a?.metadata?.versions?.configuration_version ?? 'Unknown'], ['Inference status', a?.inference_status ?? 'Unavailable'],
      ['Analytics availability', <span key="availability">{data?.analytics_availability?.status ?? 'Unavailable'} · <CodeList codes={reasons}/></span>],
      ['Field verification', verification.length ? verification.map(([field, status]) => `${field}: ${status}`).join(', ') : 'Unknown'],
    ]}/></TechnicalDetails>
  </section>;
}
export function FeaturePanels({ data, children, label = 'Six monitoring features' }: { data?: Latest | null; children?: ReactNode; label?: string }) {
  const t = data?.telemetry, a = data?.analytics;
  const thermalUnit = a?.metadata?.thermal_temperature_unit ?? a?.metadata?.units?.thermal_model_temperature;
  const compatible = thermalReady(a) && thermalUnit === t?.acquisition?.field_units.oil_temperature;
  const thermalReasons = a?.metadata?.components?.thermal?.reasons;
  const overloadCodes = a?.reason_codes?.filter(r => r.includes('OVERLOAD')) ?? [];
  const latch = a?.metadata?.maintenance_trip_latched == null ? 'Unknown' : a.metadata.maintenance_trip_latched ? 'Latched' : 'Not latched';
  const features: { title: string; icon: typeof Droplets; state: string; value: string; evidence: string; codes?: string[] }[] = [
    { title: 'Oil-leak detection', icon: Droplets, state: 'Detector unavailable', value: displayNumber(t?.oil_level, t?.acquisition?.field_units.oil_level), evidence: `Oil gauge contact: ${contactLabel(t?.magnetic_oil_gauge_alarm)}. No leak or depletion result is supplied by the API; an oil-level change alone does not confirm leakage.` },
    { title: 'Pressure monitoring', icon: Gauge, state: 'Input unavailable', value: 'Unavailable', evidence: 'No pressure measurement, unit, limits or trend exists in the canonical pipeline. DGA measurements are also unavailable.' },
    { title: 'Electrical-fault monitoring', icon: Zap, state: t?.oil_temp_trip === 1 ? 'Protection contact active' : a?.anomaly_flag ? 'Model anomaly' : 'No confirmed fault result', value: `Trip: ${contactLabel(t?.oil_temp_trip)}`, evidence: `Oil temperature alarm: ${contactLabel(t?.oil_temp_alarm)}. Maintenance trip latch: ${latch}. These are temperature protection contacts, not a short-circuit relay diagnosis; a model anomaly is not a confirmed fault.` },
    { title: 'Thermal capacity', icon: Thermometer, state: codeLabel(a?.metadata?.components?.thermal?.status ?? a?.metadata?.thermal_readiness, 'Assessment unavailable'), value: compatible ? displayNumber(a?.thermal_residual, thermalUnit) + ' residual' : 'Residual unavailable', evidence: `Model temperature: ${thermalReady(a) ? displayNumber(a?.thermal_model_temperature, thermalUnit) : 'Unavailable (component not ready)'}. Thermal state: ${a?.thermal_state ? codeLabel(a.thermal_state) : 'not reported'}. Readiness reasons: ${thermalReasons?.length ? thermalReasons.map(r => codeLabel(r)).join(', ') : 'none supplied'}. Headroom requires verified equipment limits.`, codes: thermalReasons },
    { title: 'Overload capacity', icon: Activity, state: a?.loading_percent == null ? 'Assessment unavailable' : 'Backend loading assessment', value: displayNumber(a?.loading_percent, '%'), evidence: `Backend loading result only. Overload reasons: ${overloadCodes.length ? overloadCodes.map(r => codeLabel(r)).join(', ') : 'none supplied'}. No duration or headroom estimate is supplied.`, codes: overloadCodes },
    { title: 'Predictive maintenance', icon: Wrench, state: a?.maintenance_priority ? `Priority: ${codeLabel(a.maintenance_priority)}` : 'Recommendation unavailable', value: a?.health_index == null ? 'Unavailable' : `${numberLabel(a.health_index)} / 100`, evidence: a?.maintenance_recommendation ?? 'No recommendation supplied. Operational risk and RUL remain unavailable without required evidence.' },
  ];
  return <section className="feature-grid" aria-label={label}>{features.map(f => <article className="feature-panel" key={f.title}><div className="feature-heading"><f.icon size={18} aria-hidden="true"/><h3>{f.title}</h3></div><Badge>{f.state}</Badge><strong className="feature-value">{f.value}</strong><p>{f.evidence}</p>{!!f.codes?.length && <TechnicalDetails><CodeList codes={f.codes}/></TechnicalDetails>}<footer><EventTime value={f.title === 'Pressure monitoring' ? null : f.title === 'Oil-leak detection' || f.title === 'Electrical-fault monitoring' ? t?.timestamp : a?.timestamp}/> · {codeLabel(t?.acquisition?.source_kind, 'Unknown source')}</footer></article>)}{children}</section>;
}
