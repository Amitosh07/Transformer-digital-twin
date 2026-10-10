import type { Latest, Telemetry } from '../../api/contracts';

/** Display precision only; never fills, estimates or changes API measurements. */
export function valueLabel(value: number | null | undefined, unit?: string | null) {
  if (value == null) return 'Unavailable';
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(value)}${unit && unit !== 'UNKNOWN' ? ` ${unit}` : ' (unit unknown)'}`;
}

export function timeLabel(value?: string | number | null) {
  if (value == null) return 'Unavailable';
  return new Date(value).toLocaleString(undefined, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short' });
}
export function operatingState(data?: Latest | null, error?: string | null) {
  if (error) return { label: 'API error', tone: 'danger' };
  if (!data) return { label: 'Awaiting API assessment', tone: 'neutral' };
  if (!data?.telemetry) return { label: 'No observations', tone: 'neutral' };
  if (data.telemetry.oil_temp_trip === 1 || data.analytics?.metadata?.maintenance_trip_latched) return { label: 'Trip / latched protection', tone: 'danger' };
  if (data.telemetry.oil_temp_alarm === 1 || data.telemetry.magnetic_oil_gauge_alarm === 1) return { label: 'Protection alarm', tone: 'warning' };
  if (data.open_alerts_count > 0) return { label: `${data.open_alerts_count} open alerts`, tone: 'warning' };
  if (!data.analytics || data.analytics_availability?.status !== 'AVAILABLE') return { label: 'Assessment unavailable', tone: 'neutral' };
  if (data.analytics.anomaly_flag) return { label: 'Model anomaly', tone: 'warning' };
  return { label: 'No active warning reported', tone: 'info' };
}
export function trendPath(records: Telemetry[], field: keyof Telemetry, unit: string | undefined, minimum: number, maximum: number, gap: number) {
  if (!records.length || !unit || unit === 'UNKNOWN') return '';
  const start = Date.parse(records[0].timestamp), span = Math.max(1, Date.parse(records.at(-1)!.timestamp) - start);
  let last: number | null = null;
  return records.map(r => {
    const v = r[field], time = Date.parse(r.timestamp);
    if (typeof v !== 'number' || r.acquisition?.field_units[field] !== unit) { last = null; return ''; }
    const move = last == null || time - last > gap * 1000; last = time;
    return `${move ? 'M' : 'L'}${55 + (time - start) / span * 700},${175 - (v - minimum) / Math.max(1, maximum - minimum) * 140}`;
  }).join(' ');
}
