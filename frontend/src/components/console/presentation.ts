import type { Latest, Telemetry } from '../../api/contracts';

const celsius = new Set(['DEGC', 'DEGREESC', 'DEGREEC', 'CELSIUS', 'DEGREESCELSIUS', '°C', 'C°']);

/** Display symbol for a declared unit; never converts values or guesses an undeclared unit. */
export function unitLabel(unit?: string | null) {
  if (unit == null || !unit.trim() || unit === 'UNKNOWN') return null;
  const key = unit.trim().toUpperCase().replace(/[\s_-]/g, '');
  if (celsius.has(key) || unit.trim() === '-C' || unit.trim() === '_C') return '°C';
  if (key === 'PERCENT') return '%';
  return unit.trim();
}
function unitSuffix(unit?: string | null) {
  const label = unitLabel(unit);
  if (label == null) return ' (unit unknown)';
  if (label === '1') return '';
  if (label === 'SOURCE_UNIT') return ' (source unit)';
  if (['STATUS', 'fraction', 'probability'].includes(label)) return ` (${label.toLowerCase()})`;
  return ` ${label}`;
}
const formats = {
  fixed: new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  compact: new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }),
};
export type Precision = keyof typeof formats;

/** Display precision only; never fills, estimates or changes API measurements. */
export function numberLabel(value: number | null | undefined, precision: Precision = 'fixed') {
  return value == null ? 'Unavailable' : formats[precision].format(value);
}
export function valueLabel(value: number | null | undefined, unit?: string | null, precision: Precision = 'fixed') {
  if (value == null) return 'Unavailable';
  return numberLabel(value, unit === 'STATUS' ? 'compact' : precision) + unitSuffix(unit);
}

const acronyms = new Set(['API', 'CT', 'DGA', 'FEM', 'HI', 'HV', 'ID', 'LV', 'ML', 'MQTT', 'OK', 'PT', 'RUL', 'SQL', 'UTC', 'WTI']);
/** Readable label for a machine code (e.g. INSUFFICIENT_DATA -> Insufficient data); free text passes through. */
export function codeLabel(code: string | null | undefined, fallback = 'Unavailable') {
  if (code == null || code === '') return fallback;
  if (!/^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$/.test(code) || (!code.includes('_') && code !== code.toUpperCase())) return code;
  const words = code.split('_').map(w => acronyms.has(w.toUpperCase()) ? w.toUpperCase() : w.toLowerCase());
  return words.join(' ').replace(/^./, c => c.toUpperCase());
}
/** Backend-supplied description when present, otherwise the neutral readable code label. */
export function reasonLabel(code: string, descriptions?: Record<string, string> | null) {
  return descriptions?.[code] ?? codeLabel(code);
}

export function timeLabel(value?: string | number | null) {
  if (value == null) return 'Unavailable';
  return new Date(value).toLocaleString(undefined, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short' });
}
export function clockLabel(value?: string | number | null) {
  if (value == null) return 'Unavailable';
  return new Date(value).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
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
