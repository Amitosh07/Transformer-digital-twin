import { trendPath } from './presentation';
import { useState } from 'react';
import type { Telemetry } from '../../api/contracts';
import { EventTime } from './TelemetryPanels';

const channels = {
  'Oil temperature': ['oil_temperature'], 'Oil level': ['oil_level'],
  'Phase currents': ['current_l1', 'current_l2', 'current_l3'],
  'Phase voltages': ['phase_voltage_l1', 'phase_voltage_l2', 'phase_voltage_l3'],
  'Active power': ['active_power_total'],
} as const;
export function TrendCharts({ records, total, gap = 10 }: { records: Telemetry[]; total: number; gap?: number }) {
  const [channel, setChannel] = useState<keyof typeof channels>('Oil temperature');
  const fields = channels[channel], unit = records.at(-1)?.acquisition?.field_units[fields[0]];
  const values = records.flatMap(r => fields.map(f => r.acquisition?.field_units[f] === unit && unit !== 'UNKNOWN' ? r[f] : null)).filter((n): n is number => typeof n === 'number');
  const min = values.length ? Math.min(...values) : 0, max = values.length ? Math.max(...values) : 1;
  const colors = ['#186ca0', '#cf8530', '#6a52ae'];
  return <section className="console-panel" aria-label="Telemetry trends"><div className="section-heading"><div><h3>Telemetry trends</h3><p>Recent event-time observations · gaps stay disconnected</p></div><select aria-label="Trend channel" value={channel} onChange={e => setChannel(e.target.value as keyof typeof channels)}>{Object.keys(channels).map(c => <option key={c}>{c}</option>)}</select></div>
    {!records.length ? <div className="empty-state">No observations available</div> : !values.length || !unit || unit === 'UNKNOWN' ? <div className="empty-state">No values with a declared compatible unit</div> : <>
      <div className="chart-legend">{fields.map((f, i) => <span key={f}><i style={{ background: colors[i] }}/>{f.replaceAll('_', ' ')} · {unit}</span>)}</div>
      <svg viewBox="0 0 800 210" role="img" aria-label={`${channel} event-time trend`} className="trend-svg">{[35, 105, 175].map((y, i) => <g key={y}><line x1="55" x2="755" y1={y} y2={y} stroke="#dce5ed" strokeDasharray="3 3"/><text x="8" y={y+4} fill="#62758a" fontSize="11">{(max-(max-min)*i/2).toFixed(1)}</text></g>)}{fields.map((f,i) => <path key={f} d={trendPath(records,f,unit,min,max,gap)} fill="none" stroke={colors[i]} strokeWidth="2"/>)}<text x="55" y="200" fill="#62758a" fontSize="11">{new Date(records[0].timestamp).toLocaleTimeString()}</text><text x="695" y="200" fill="#62758a" fontSize="11">{new Date(records.at(-1)!.timestamp).toLocaleTimeString()}</text></svg>
    </>}
    <footer className="chart-footer">{records.length} of {total} observations · bounded to latest hour, newest 300 rows. {total > records.length && 'Partial window coverage.'} Gap display policy: {gap}s (demo default). <EventTime value={records.at(-1)?.timestamp}/></footer>
  </section>;
}
