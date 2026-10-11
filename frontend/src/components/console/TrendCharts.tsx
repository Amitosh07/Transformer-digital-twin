import { clockLabel, numberLabel, trendPath, unitLabel } from './presentation';
import { useState } from 'react';
import type { Telemetry } from '../../api/contracts';
import { EventTime } from './TelemetryPanels';

const channels = {
  'Oil temperature': ['oil_temperature'], 'Oil level': ['oil_level'],
  'Phase currents': ['current_l1', 'current_l2', 'current_l3'],
  'Phase voltages': ['phase_voltage_l1', 'phase_voltage_l2', 'phase_voltage_l3'],
  'Active power': ['active_power_total'],
} as const;
const seriesNames: Record<string, string> = {
  oil_temperature: 'Oil temperature', oil_level: 'Oil level', active_power_total: 'Active power (total)',
  current_l1: 'Current L1', current_l2: 'Current L2', current_l3: 'Current L3',
  phase_voltage_l1: 'Voltage L1', phase_voltage_l2: 'Voltage L2', phase_voltage_l3: 'Voltage L3',
};
export function TrendCharts({ records, total, gap = 10 }: { records: Telemetry[]; total: number; gap?: number }) {
  const [channel, setChannel] = useState<keyof typeof channels>('Oil temperature');
  const fields = channels[channel], unit = records.at(-1)?.acquisition?.field_units[fields[0]];
  const values = records.flatMap(r => fields.map(f => r.acquisition?.field_units[f] === unit && unit !== 'UNKNOWN' ? r[f] : null)).filter((n): n is number => typeof n === 'number');
  const min = values.length ? Math.min(...values) : 0, max = values.length ? Math.max(...values) : 1;
  const colors = ['#186ca0', '#cf8530', '#6a52ae'];
  const symbol = unitLabel(unit), span = Math.max(1, max - min);
  return <section className="console-panel" aria-label="Telemetry trends"><div className="section-heading"><div><h3>Telemetry trends</h3><p>{channel} readings from the latest hour of event-time history. Breaks mark gaps longer than {gap} s; missing readings are not filled.</p></div><select aria-label="Trend channel" value={channel} onChange={e => setChannel(e.target.value as keyof typeof channels)}>{Object.keys(channels).map(c => <option key={c}>{c}</option>)}</select></div>
    {!records.length ? <div className="empty-state">No observations available</div> : !values.length || !unit || unit === 'UNKNOWN' ? <div className="empty-state">No values with a declared compatible unit</div> : <>
      <div className="chart-legend">{fields.map((f, i) => <span key={f}><i style={{ background: colors[i] }}/>{seriesNames[f] ?? f} ({symbol})</span>)}</div>
      <svg viewBox="0 0 800 220" role="img" aria-label={`${channel} event-time trend`} className="trend-svg">
        <text x="8" y="14" fill="#4f6578" fontSize="11" fontWeight="600">{symbol}</text>
        {[35, 105, 175].map((y, i) => <g key={y}><line x1="55" x2="755" y1={y} y2={y} stroke="#dce5ed" strokeDasharray="3 3"/><text x="50" y={y+4} fill="#62758a" fontSize="11" textAnchor="end">{numberLabel(min + span*(1 - i/2))}</text></g>)}
        {fields.map((f,i) => <path key={f} d={trendPath(records,f,unit,min,max,gap)} fill="none" stroke={colors[i]} strokeWidth="2"/>)}
        <text x="55" y="198" fill="#62758a" fontSize="11">{clockLabel(records[0].timestamp)}</text><text x="755" y="198" fill="#62758a" fontSize="11" textAnchor="end">{clockLabel(records.at(-1)!.timestamp)}</text>
        <text x="408" y="214" fill="#4f6578" fontSize="11" textAnchor="middle">Event time</text>
      </svg>
    </>}
    <footer className="chart-footer"><span>{records.length} of {total} observations (newest 300 rows of the latest hour){total > records.length && ' · partial window coverage'}</span><span>Latest: <EventTime value={records.at(-1)?.timestamp}/></span></footer>
  </section>;
}
