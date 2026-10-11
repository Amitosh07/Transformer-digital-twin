import { useCallback, useEffect, useRef, useState } from 'react';
import { api, historyWindow } from '../api/client';
import { measurements } from '../api/contracts';
import { usePolling } from '../hooks/usePolling';
import { contactLabel, displayNumber, freshness, POLL_MS, STALE_MS, thermalReady } from '../monitoring';
import { HealthIndexDial } from './HealthIndexDial';
import { ThermalResidualChart, thermalPoints } from './ThermalResidualChart';
import { PrescriptiveActionCard } from './PrescriptiveActionCard';
import { EnergyCard, NameplateCard, RULCard, panel } from './ResourceCards';

function Status({ state }: { state: { loading: boolean; error: string | null; retry: () => void } }) {
  const { loading, error, retry } = state;
  return <>{loading && <p role="status">Loading API response…</p>}{error && <div role="alert" className="text-amber-300">{error} — retained data may be stale. <button onClick={retry} className="underline">Retry</button></div>}</>;
}
function lifecycleWindow(event: string | null) {
  const query = historyWindow(event);
  query.set('from', new Date(Date.parse(query.get('to')!) - 86400000).toISOString());
  query.set('limit', '50'); query.set('status', 'OPEN'); query.delete('order');
  return query;
}
export function InteractiveTwinStudio() {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState('');
  const [energyWindow, setEnergyWindow] = useState('1h');
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const registryLoad = useCallback((signal: AbortSignal) => api.registry(signal, offset), [offset]);
  const registry = usePolling('registry:' + offset, registryLoad, 30000);
  useEffect(() => { if (registry.data && !registry.data.items.some(a => a.id === selected)) setSelected(registry.data.items[0]?.id ?? ''); }, [registry.data, selected]);
  const latestLoad = useCallback((signal: AbortSignal) => api.latest(selected, signal), [selected]);
  const latest = usePolling(selected, latestLoad, POLL_MS, !!selected);
  const eventRef = useRef<string | null>(null);
  useEffect(() => { eventRef.current = latest.data?.telemetry?.timestamp ?? null; }, [latest.data?.telemetry?.timestamp,selected]);
  const historyLoad = useCallback(async (signal: AbortSignal) => {
    const query = historyWindow(eventRef.current);
    const [telemetry, analytics] = await Promise.all([api.telemetry(selected, query, signal), api.analytics(selected, query, signal)]);
    return { telemetry, analytics, from: query.get('from'), to: query.get('to') };
  }, [selected]);
  // Wait for latest so a replay's bounded history is anchored to its event time.
  const history = usePolling(selected, historyLoad, 15000, !!latest.data);
  const alertsLoad = useCallback((signal: AbortSignal) => api.alerts(selected, lifecycleWindow(eventRef.current), signal), [selected]);
  const maintenanceLoad = useCallback((signal: AbortSignal) => api.maintenance(selected, lifecycleWindow(eventRef.current), signal), [selected]);
  const alerts = usePolling(selected, alertsLoad, 15000, !!latest.data);
  const maintenance = usePolling(selected, maintenanceLoad, 15000, !!latest.data);
  const mqttLoad = useCallback((signal: AbortSignal) => api.mqtt(signal), []);
  const mqtt = usePolling('mqtt', mqttLoad, 15000);
  const rulLoad = useCallback((signal: AbortSignal) => api.rul(selected, signal), [selected]);
  const energyEnd = latest.data?.telemetry?.timestamp ?? null;
  const energyLoad = useCallback((signal: AbortSignal) => {
    const query = new URLSearchParams({window: energyWindow === '2h' ? '1h' : energyWindow,anchor:'latest'});
    if (energyWindow === '2h' && energyEnd) { query.set('from',new Date(Date.parse(energyEnd)-7200000).toISOString());query.set('to',energyEnd); }
    return api.energy(selected,signal,query);
  }, [selected,energyWindow,energyEnd]);
  // Poll persisted H06 resources; failures retain their visible error states.
  const rul = usePolling(selected, rulLoad, POLL_MS, !!selected);
  const energy = usePolling(selected, energyLoad, 15000, !!selected);
  const projectionLoad = useCallback((signal: AbortSignal) => api.projection(selected, signal), [selected]);
  const projection = usePolling(selected, projectionLoad, POLL_MS, !!selected);
  const asset = latest.data?.transformer ?? registry.data?.items.find(a => a.id === selected);
  const telemetry = latest.data?.telemetry;
  const analytics = latest.data?.analytics;
  const units = telemetry?.acquisition?.field_units;
  const thermalUnit = analytics?.metadata?.thermal_temperature_unit ?? analytics?.metadata?.units?.thermal_model_temperature;
  const status = freshness(telemetry, latest.lastSuccess, now, latest.error);
  return <section id="demo" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto text-slate-200 space-y-6">
    <header><p className="text-amber-400 font-mono">API MONITORING</p><h2 className="text-3xl font-bold">Transformer monitoring studio</h2>
      <p className="text-slate-400">Backend observations and analytics. Poll {POLL_MS / 1000}s; event-age threshold {STALE_MS / 1000}s is a configured demo default.</p></header>
    <Status state={registry} />
    <label className="block">Asset <select aria-label="Asset" value={selected} onChange={e => setSelected(e.target.value)} className="bg-slate-900 border border-slate-700 rounded p-2 ml-3 max-w-full">
      <option value="">Select a registered asset</option>{registry.data?.items.map(a => <option key={a.id} value={a.id}>{a.name} ({a.id})</option>)}
    </select></label>
    {registry.data?.total === 0 && <p>No registered assets</p>}
    {registry.data && <div className="space-x-4"><span>Registry: {registry.data.total} assets · page {Math.floor(offset / 50) + 1}</span>
      <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous assets</button>
      <button disabled={offset + 50 >= registry.data.total} onClick={() => setOffset(offset + 50)}>Next assets</button></div>}
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" aria-label="Asset portfolio">
      {registry.data?.items.map(a => <button key={a.id} onClick={() => setSelected(a.id)} className={panel + (a.id === selected ? ' border-amber-500' : '')}>
        <strong>{a.name}</strong><p>{a.id}</p><p>{a.id === selected ? status : 'Not assessed — select asset'}</p>
        <p>Configuration: {a.configuration_metadata?.status ?? 'UNVERIFIED'}</p></button>)}
    </div>
    {registry.data && <p>Current registry page: {latest.data ? '1 selected asset response available' : '0 assessed assets'}; {Math.max(0,registry.data.items.length - (latest.data ? 1 : 0))} assets not assessed. No inferred portfolio health.</p>}
    {selected && <>
      <Status state={latest} />
      <section className={panel} aria-label="Source and freshness"><h3>{selected} · {status}</h3>
        <p>Source: {telemetry?.acquisition?.source_kind ?? 'UNKNOWN'} · {telemetry?.acquisition?.source_name ?? telemetry?.source_name ?? 'Unknown source'}</p>
        <p>Measurement event: {telemetry?.timestamp ?? 'No observations'} · Analytics event: {analytics?.timestamp ?? 'Unavailable'}</p>
        <p>Last successful API poll: {latest.lastSuccess == null ? 'Never' : new Date(latest.lastSuccess).toISOString()}</p>
        <p>Received at: {telemetry?.received_at ?? 'Unknown'} · Expected cadence: {displayNumber(telemetry?.acquisition?.expected_interval_seconds,'s')}</p>
        <p>Timezone: {telemetry?.acquisition?.timezone_status ?? 'UNKNOWN'} · Gateway: {telemetry?.acquisition?.gateway_id ?? 'Unknown'} · Snapshot: {telemetry?.acquisition?.snapshot_id ?? 'Unknown'}</p>
        <p>Replay origin/run: {telemetry?.acquisition?.origin_transformer_id ?? 'None supplied'} / {telemetry?.acquisition?.replay_run_id ?? 'None supplied'}</p>
        <p>Analytics availability: {latest.data?.analytics_availability?.status ?? 'Unknown'} · {latest.data?.analytics_availability?.reasons.join(', ') || 'No availability evidence supplied'}</p>
        <p>Bundle/configuration: {analytics?.metadata?.versions?.bundle_id ?? 'Unknown'} / {analytics?.metadata?.versions?.configuration_version ?? 'Unknown'}</p>
        <p>Inference: {analytics?.inference_status ?? 'Unavailable'} · Reasons: {analytics?.reason_codes?.join(', ') || 'None supplied'}</p>
        {telemetry && analytics && Date.parse(analytics.timestamp) < Date.parse(telemetry.timestamp) && <p className="text-amber-300">Analytics predates telemetry — stale analysis</p>}
      </section>
      <section className={panel} aria-label="Canonical measurements"><h3>Canonical measurements</h3>
        {!telemetry ? <p>No observations</p> : <><dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">{measurements.map(field => <div key={field}>
          <dt>{field === 'winding_temperature' ? 'Winding measurement (WTI status is not temperature)' : field.replaceAll('_',' ')}</dt>
          <dd>{displayNumber(telemetry[field], units?.[field])} · {telemetry.acquisition?.field_verification[field] ?? 'UNVERIFIED'}</dd></div>)}</dl>
          <p>Oil temperature alarm: {contactLabel(telemetry.oil_temp_alarm)} · Oil temperature trip: {contactLabel(telemetry.oil_temp_trip)} · Oil gauge alarm: {contactLabel(telemetry.magnetic_oil_gauge_alarm)}</p></>}
        <p>Thermal model: {thermalReady(analytics) ? displayNumber(analytics?.thermal_model_temperature,thermalUnit) : 'Unavailable — thermal component not ready'} · Residual: {thermalReady(analytics) ? displayNumber(analytics?.thermal_residual,thermalUnit) : 'Unavailable'}</p>
        <p>Anomaly score: {displayNumber(analytics?.anomaly_score,'score')} · Flag: {analytics?.anomaly_flag == null ? 'Unknown' : analytics.anomaly_flag ? 'Detected' : 'Not detected'}</p>
      </section>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6"><HealthIndexDial analytics={analytics} /><PrescriptiveActionCard analytics={analytics} /></div>
      <Status state={history} />
      {history.data && <p>History: {history.data.from} → {history.data.to} · Showing {history.data.telemetry.items.length} of {history.data.telemetry.total} telemetry observations (bounded page, maximum 100). {history.data.telemetry.total > 100 && 'Partial history page; not full window coverage.'}</p>}
      <ThermalResidualChart data={thermalPoints(history.data?.telemetry.items ?? [],history.data?.analytics.items ?? [],units?.oil_temperature)} unit={units?.oil_temperature} gapSeconds={(telemetry?.acquisition?.expected_interval_seconds ?? 5) * 2} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="lg:col-span-2"><Status state={rul} /><Status state={energy} /><Status state={projection} /></div>
        <section className={panel} aria-label="Alerts"><h3>Open backend alerts</h3><Status state={alerts} />
          {alerts.data?.total === 0 && <p>No open alerts reported in the queried 24-hour event-time window</p>}{alerts.data && <p>Showing {alerts.data.items.length} of {alerts.data.total} in the queried 24-hour window · Latest global open count: {latest.data?.open_alerts_count ?? 'Unknown'}</p>}
          {alerts.data?.items.map(a => <article key={a.id}><strong>{a.severity}: {a.alert_type}</strong><p>{a.trigger} · {a.threshold_or_reason}</p><p>{a.recommended_action}</p><p>{a.status} · Last seen: {a.last_seen_at}</p><details><summary>Evidence</summary><pre className="whitespace-pre-wrap break-words">{JSON.stringify(a.evidence,null,2)}</pre></details></article>)}</section>
        <section className={panel} aria-label="Maintenance"><h3>Open backend maintenance actions</h3><Status state={maintenance} />
          {maintenance.data?.total === 0 && <p>No open recommendations reported in the queried 24-hour event-time window</p>}{maintenance.data && <p>Showing {maintenance.data.items.length} of {maintenance.data.total} in the queried 24-hour window</p>}
          {maintenance.data?.items.map(m => <article key={m.id}><strong>{m.priority}: {m.recommendation}</strong><p>{m.status} · {m.timestamp} · {m.reason_codes.join(', ')}</p></article>)}</section>
      </div>
      {asset && <NameplateCard asset={asset} />}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RULCard projection={projection.data} result={rul.data?.rul ?? analytics?.rul} message={rul.loading ? 'Checking RUL API…' : rul.error ? 'RUL API not available: ' + rul.error : 'No persisted RUL result'} />
        <div><label>Energy event-time window <select aria-label="Energy event-time window" className="bg-slate-900 p-2" value={energyWindow} onChange={e=>setEnergyWindow(e.target.value)}>{['1h','2h','6h','24h','7d'].map(window=><option key={window}>{window}</option>)}</select></label><EnergyCard result={energy.data} message={energy.loading ? 'Checking energy API…' : energy.error ? 'Energy API not available: ' + energy.error : 'No energy result'} /></div>
      </div>
    </>}
    <section className={panel} aria-label="MQTT status"><h3>Backend MQTT transport diagnostics</h3><Status state={mqtt} />
      {mqtt.data && <><p>Enabled: {String(mqtt.data.enabled)} · Connected: {String(mqtt.data.connected)} · Queue: {mqtt.data.queue_depth}</p>
        <p>Committed: {mqtt.data.committed_count} · Conflicted: {mqtt.data.conflicted_count} · Dropped: {mqtt.data.dropped_count}</p>
        <p>Last transport message: {mqtt.data.last_message_at ?? 'Unknown'} · Error: {mqtt.data.last_error ?? 'None reported'}</p></>}
      <p>Transport status does not refresh measurement event time or establish a committed receipt for this observation.</p></section>
  </section>;
}
