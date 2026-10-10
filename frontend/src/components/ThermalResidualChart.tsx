import type { Telemetry, AnalyticsPoint } from '../api/contracts';
import { panel } from './ResourceCards';
import { displayNumber, thermalReady } from '../monitoring';

export interface ThermalPoint { timestamp: string; observed: number | null; model: number | null; }
export function thermalPoints(telemetry: Telemetry[], analytics: AnalyticsPoint[], displayUnit?: string | null): ThermalPoint[] {
  const byTime = new Map(analytics.map(a => [Date.parse(a.timestamp),a]));
  return telemetry.map(t => {
    const a = byTime.get(Date.parse(t.timestamp));
    const unit = t.acquisition?.field_units.oil_temperature;
    const modelUnit = a?.metadata?.thermal_temperature_unit ?? a?.metadata?.units?.thermal_model_temperature;
    return { timestamp:t.timestamp, observed:unit && unit === displayUnit ? t.oil_temperature : null,
      model: thermalReady(a) && unit && unit === displayUnit && unit === modelUnit ? a?.thermal_model_temperature ?? null : null };
  });
}
export function chartPath(data: ThermalPoint[], field: 'observed' | 'model', gapSeconds: number): string {
  const values = data.flatMap(p => [p.observed,p.model]).filter((v):v is number => v != null);
  if (!values.length) return '';
  const min = Math.min(...values)-5, max = Math.max(...values)+5;
  const start = Date.parse(data[0].timestamp), span = Math.max(1,Date.parse(data[data.length-1].timestamp)-start);
  let previous: ThermalPoint | null = null;
  return data.map(p => {
    const value = p[field];
    if (value == null) { previous=null; return ''; }
    const move = !previous || Date.parse(p.timestamp)-Date.parse(previous.timestamp)>gapSeconds*1000;
    previous=p;
    return `${move ? 'M':'L'} ${40+(Date.parse(p.timestamp)-start)/span*520} ${175-(value-min)/(max-min)*150}`;
  }).join(' ');
}
export function ThermalResidualChart({ data, unit, gapSeconds=10 }: { data: ThermalPoint[]; unit?: string | null; gapSeconds?: number }) {
  return <section className={panel} aria-label="Thermal history"><h3 className="text-lg text-cyan-300">Observed oil / backend thermal model</h3>
    <p>Unit: {unit ?? 'Unknown source unit'} · Gaps above {gapSeconds}s remain disconnected (demo display policy).</p>
    {!data.length ? <p>No observations</p> : <>
      <svg viewBox="0 0 600 200" role="img" aria-label="Event-time thermal history" className="w-full">
        <path data-testid="observed-path" d={chartPath(data,'observed',gapSeconds)} stroke="#f59e0b" fill="none" strokeWidth="2" />
        <path d={chartPath(data,'model',gapSeconds)} stroke="#06b6d4" fill="none" strokeWidth="2" />
      </svg>
      <details><summary>History observations ({data.length})</summary>{data.map((p,i)=><p key={i}>{p.timestamp} · Observed {displayNumber(p.observed,unit)} · Model {displayNumber(p.model,unit)}</p>)}</details>
    </>}
  </section>;
}
