import { clockLabel, codeLabel, numberLabel, operatingState, timeLabel } from './presentation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, ArrowLeft, ArrowRight, Bell, ChevronLeft, ChevronRight, LayoutGrid, Menu, Radio, RefreshCw, Search, Wrench, Zap } from 'lucide-react';
import { api } from '../../api/client';
import type { Asset, Telemetry } from '../../api/contracts';
import { registryLoader, useAssetData, usePortfolio } from '../../hooks/useConsoleData';
import { usePolling } from '../../hooks/usePolling';
import { usePhysics } from '../../hooks/usePhysics';
import { PhysicsFeatureCards } from './PhysicsFeatureCards';
import { freshness } from '../../monitoring';
import { HealthIndexDial } from '../HealthIndexDial';
import { PrescriptiveActionCard } from '../PrescriptiveActionCard';
import { EnergyCard, NameplateCard, RULCard } from '../ResourceCards';
import { Badge, CodeList, EventTime, FeaturePanels, KeyValues, Reading, SourceStrip, TechnicalDetails, TransformerDrawing } from './TelemetryPanels';
import { TrendCharts } from './TrendCharts';
import './console.css';

const navigation = [
  { id: 'overview', label: 'Overview', icon: LayoutGrid },
  { id: 'monitoring', label: 'Transformer monitoring', icon: Zap },
  { id: 'alarms', label: 'Live alarms / events', icon: Bell },
  { id: 'maintenance', label: 'Predictive maintenance', icon: Wrench },
];
const descriptions: Record<string, string> = {
  overview: 'Latest telemetry and condition status for each registered transformer.',
  monitoring: 'Measurements, trends and backend condition assessments for the selected transformer.',
  alarms: 'Alarm and event lifecycle records for the selected transformer.',
  maintenance: 'Backend health index, maintenance assessment, remaining-time scenario and energy results for the selected transformer.',
};
const phaseFields: [keyof Telemetry, string][] = [
  ['current_l2', 'Phase L2 current'], ['current_l3', 'Phase L3 current'], ['phase_voltage_l2', 'Phase L2 voltage'], ['phase_voltage_l3', 'Phase L3 voltage'],
  ['apparent_power_total', 'Apparent power (total)'], ['reactive_power_total', 'Reactive power (total)'], ['neutral_current', 'Neutral current'],
  ['winding_temperature', 'WTI source indicator (status, not temperature)'], ['power_factor_l1', 'Power factor L1'],
];
const assetOption = (asset: Asset) => asset.name.includes(asset.id) ? asset.name : `${asset.id} · ${asset.name}`;
export function RequestStatus({ state, label }: { state: { loading: boolean; error: string | null; retry: () => void }; label: string }) {
  return <>{state.loading && <p role="status" className="request-status">{label}: loading…</p>}{state.error && <div role="alert" className="request-error">{label}: {state.error}. Retained data may be stale. <button onClick={state.retry}>Retry</button></div>}</>;
}
export function MonitoringConsole() {
  const [area, setArea] = useState('overview'), [selected, setSelected] = useState(''), [sidebar, setSidebar] = useState(false);
  const [search, setSearch] = useState(''), [statusFilter, setStatusFilter] = useState('all'), [alarmFilter, setAlarmFilter] = useState('all'), [page, setPage] = useState(0);
  const [now, setNow] = useState(Date.now);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const registry = usePolling('active-registry', registryLoader, 60000);
  const assets = useMemo(() => registry.data ?? [], [registry.data]);
  const selectedAsset = assets.some(a => a.id === selected) ? selected : '';
  const matching = useMemo(() => assets.filter(a => `${a.id} ${a.name}`.toLowerCase().includes(search.toLowerCase())), [assets, search]);
  const pageSize = 5;
  const pageCount = Math.max(1, Math.ceil(matching.length / pageSize)), currentPage = Math.min(page, pageCount - 1);
  const visible = matching.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  const portfolio = usePortfolio(visible.map(a => a.id), area === 'overview');
  const detail = useAssetData(area === 'overview' ? '' : selectedAsset, area);
  const livePhysicsDemo = import.meta.env.VITE_LIVE_PHYSICS_DEMO_ENABLED === 'true';
  const physics = usePhysics(selectedAsset, area === 'monitoring' && livePhysicsDemo);
  const latest = detail.latest;
  const mqttLoad = useCallback((s: AbortSignal) => api.mqtt(s), []);
  const mqtt = usePolling('mqtt', mqttLoad, 15000);
  const choose = (id: string) => { setSelected(id); setArea('monitoring'); setSidebar(false); };
  const asset = latest.data?.transformer ?? assets.find(a => a.id === selectedAsset);
  const t = latest.data?.telemetry, a = latest.data?.analytics;
  const state = operatingState(latest.data, latest.error);
  const matchingStatus = visible.filter(asset => {
    const snapshot = portfolio.data?.[asset.id], s = operatingState(snapshot?.data, snapshot?.error);
    const alarms = snapshot?.data?.open_alerts_count;
    return (statusFilter === 'all' || (statusFilter === 'warnings' ? ['danger','warning'].includes(s.tone) : !snapshot?.data?.analytics || !!snapshot.error)) && (alarmFilter === 'all' || (alarmFilter === 'open' ? alarms != null && alarms > 0 : alarms == null));
  });
  const title = navigation.find(n => n.id === area)?.label;
  return <div className="monitoring-console">
    <aside className={'console-sidebar ' + (sidebar ? 'expanded' : '')}><a className="console-brand" href="#" onClick={e => { e.preventDefault(); setArea('overview'); }}><span className="brand-mark"><Zap size={24} aria-hidden="true"/></span><span>TRANSFORMER<span>DIGITAL TWIN</span></span></a><div className="sidebar-section-label">OPERATIONS CONSOLE</div><nav aria-label="Main navigation">{navigation.map(n => <button key={n.id} aria-current={area === n.id ? 'page' : undefined} className={area === n.id ? 'active' : ''} onClick={() => { setArea(n.id); setSidebar(false); }}><n.icon size={18} aria-hidden="true"/><span>{n.label}</span>{area === n.id && <ChevronRight size={14} aria-hidden="true"/>}</button>)}</nav></aside>
    <div className="console-workspace"><header className="console-topbar"><button className="mobile-menu" aria-label="Toggle navigation" onClick={() => setSidebar(!sidebar)}><Menu size={20}/></button><div className="topbar-location"><span>Transformer Digital Twin</span></div><div className="topbar-status"><Badge tone={mqtt.error ? 'danger' : mqtt.data?.connected ? 'info' : 'neutral'}><span className="status-dot" aria-hidden="true"/>{mqtt.error ? 'API connection error' : mqtt.data?.connected ? 'MQTT connected' : 'Transport disconnected or unknown'}</Badge><span className="topbar-update" title={timeLabel(mqtt.lastSuccess)}>API checked {clockLabel(mqtt.lastSuccess)}</span></div></header>
    <main className="console-main"><div className="page-heading"><div><div className="eyebrow">Asset operations</div><h1>{area === 'overview' ? 'Transformer overview' : title}</h1><p>{descriptions[area]}</p></div><div className="heading-actions"><button className="button-secondary" onClick={() => { registry.retry(); if (area === 'overview') portfolio.retry(); else { latest.retry(); if (area === 'monitoring' && livePhysicsDemo) physics.retry(); } }}><RefreshCw size={14} aria-hidden="true"/> Refresh</button></div></div>
    {area === 'overview' ? <>
      <RequestStatus state={registry} label="Asset registry"/>
      <div className="overview-summary"><div><LayoutGrid aria-hidden="true"/><span>Active transformers<strong>{registry.data ? assets.length : '—'}</strong></span></div><div><Activity aria-hidden="true"/><span>Assets on this page<strong>{visible.length} of {matching.length}</strong></span></div><div><Radio aria-hidden="true"/><span>Delivery transport<strong>{mqtt.data?.connected ? 'MQTT connected' : 'Unconfirmed'}</strong></span></div></div>
      <div className="overview-toolbar"><label className="search-field"><Search size={17} aria-hidden="true"/><input aria-label="Search assets" placeholder="Search asset ID or name…" value={search} onChange={e => { setSearch(e.target.value); setPage(0); }}/></label><label>Status on page<select aria-label="Status filter" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="all">All assessments</option><option value="warnings">Warnings / protection</option><option value="unavailable">Unavailable / errors</option></select></label><label>Alarms on page<select aria-label="Alarm filter" value={alarmFilter} onChange={e => setAlarmFilter(e.target.value)}><option value="all">All alarm states</option><option value="open">Open alerts</option><option value="unknown">Unknown</option></select></label></div>
      <div className="section-heading"><h2>Asset inventory <span>{matching.length} matching</span></h2></div><RequestStatus state={portfolio} label="Visible asset readings"/>
      {registry.data && !assets.length && <div className="empty-state">No registered assets. No local samples are substituted.</div>}
      <section className="asset-grid" aria-label="Asset portfolio">{matchingStatus.map(asset => <TransformerCard key={asset.id} asset={asset} snapshot={portfolio.data?.[asset.id]} now={now} choose={choose}/> )}</section>
      {!!assets.length && !matchingStatus.length && <div className="empty-state">No matching assets on this page. Other pages may contain matching assessments.</div>}
      <div className="pagination"><span>Page {currentPage+1} of {pageCount} · {matchingStatus.length} shown</span><button disabled={currentPage === 0} onClick={() => setPage(currentPage-1)}><ChevronLeft size={16} aria-hidden="true"/>Previous</button><button disabled={currentPage+1 >= pageCount} onClick={() => setPage(currentPage+1)}>Next<ChevronRight size={16} aria-hidden="true"/></button></div>
    </> : <>
      <div className="detail-toolbar"><button className="button-secondary" onClick={() => setArea('overview')}><ArrowLeft size={15} aria-hidden="true"/>Asset overview</button><label>Selected asset<select aria-label="Asset" value={selectedAsset} onChange={e => setSelected(e.target.value)}><option value="">Select registered asset</option>{assets.map(asset => <option key={asset.id} value={asset.id}>{assetOption(asset)}</option>)}</select></label><Badge tone={state.tone}>{state.label}</Badge></div>
      {!selectedAsset ? <div className="empty-state">Select an asset from the overview or registry selector to monitor its data.</div> : <>
        <RequestStatus state={latest} label="Latest telemetry"/>
        <SourceStrip data={latest.data} lastSuccess={latest.lastSuccess} error={latest.error} now={now}/>
        {area === 'monitoring' && <>
          <section className="console-panel equipment-panel" aria-label="Selected transformer measurements"><div className="section-heading"><div><h2>{selectedAsset}</h2><p>{asset?.name ?? 'Registered asset'} · {codeLabel(asset?.measurement_side, 'Unknown')} measurement side</p></div><Badge tone={state.tone}>{state.label}</Badge></div><div className="equipment-layout"><div className="equipment-readings"><Reading label="Oil temperature" field="oil_temperature" record={t}/><Reading label="Oil level" field="oil_level" record={t}/><Reading label="Ambient temperature" field="ambient_temperature" record={t}/></div><div className="equipment-center"><TransformerDrawing/><span className="equipment-caption">Illustrative schematic · {selectedAsset}</span></div><div className="equipment-readings"><Reading label="Phase L1 voltage" field="phase_voltage_l1" record={t}/><Reading label="Phase L1 current" field="current_l1" record={t}/><Reading label="Active power (total)" field="active_power_total" record={t}/></div></div><div className="phase-readings">{phaseFields.map(([f, label]) => <Reading key={f} label={label} field={f} record={t}/>)}</div></section>
          <RequestStatus state={detail.history} label="History"/><TrendCharts records={detail.history.data?.telemetry.items ?? []} total={detail.history.data?.telemetry.total ?? 0} gap={(t?.acquisition?.expected_interval_seconds ?? 5)*2}/>
          <FeaturePanels data={latest.data} label="Transformer monitoring features"><PhysicsFeatureCards state={physics} enabled={livePhysicsDemo} now={now}/></FeaturePanels>
        </>}
        {area === 'alarms' && <AlarmsPanel asset={selectedAsset} openCount={latest.data?.open_alerts_count} alerts={detail.alerts}/>}
        {area === 'maintenance' && <><div className="analytics-grid"><HealthIndexDial analytics={a}/><PrescriptiveActionCard analytics={a}/></div><section className="console-panel"><div className="section-heading"><div><h2>Maintenance actions</h2><p>Persisted backend recommendations for {selectedAsset} in the 24 hours before the latest measurement.</p></div></div><RequestStatus state={detail.maintenance} label="Maintenance"/>{detail.maintenance.data?.total === 0 && <p>No recommendations returned in the bounded window.</p>}{detail.maintenance.data?.items.map(m => <article className="maintenance-row" key={m.id}><div className="maintenance-row-heading"><Badge>{codeLabel(m.priority)}</Badge><strong>{m.recommendation}</strong></div><p>{m.reason_codes.length ? m.reason_codes.map(c => codeLabel(c)).join(', ') : 'No reasons supplied'} · {codeLabel(m.status)} · <EventTime value={m.timestamp}/></p><TechnicalDetails><KeyValues items={[['Record ID', m.id], ['Priority code', m.priority], ['Status code', m.status], ['Reason codes', <CodeList key="codes" codes={m.reason_codes}/>]]}/></TechnicalDetails></article>)}</section><div className="analytics-grid"><div><RequestStatus state={detail.rul} label="RUL"/><RequestStatus state={detail.projection} label="Scenario curve"/><RULCard result={detail.rul.data?.rul ?? a?.rul} projection={detail.projection.data} message="No persisted RUL result"/></div><div><RequestStatus state={detail.energy} label="Energy"/><EnergyCard result={detail.energy.data} message="No bounded-window energy result"/></div></div>{asset && <NameplateCard asset={asset}/>}</>}
      </>}
    </>}
    <footer className="console-footer"><span>POWERNext / Transformer Digital Twin</span><span>API contract 1.1.0</span></footer>
    </main></div>
  </div>;
}
type AlertsState = ReturnType<typeof useAssetData>['alerts'];
function evidenceLines(evidence: Record<string, unknown>) {
  return Object.entries(evidence).map(([key, value]) => {
    const label = key === 'reason_codes' ? 'Reported reasons' : codeLabel(key);
    if (Array.isArray(value) && value.every(v => typeof v === 'string')) return `${label}: ${value.length ? value.map(v => codeLabel(v)).join(', ') : 'none'}`;
    if (typeof value === 'number') return `${label}: ${numberLabel(value, 'compact')}`;
    if (typeof value === 'string') return `${label}: ${codeLabel(value)}`;
    if (typeof value === 'boolean') return `${label}: ${value ? 'Yes' : 'No'}`;
    if (value == null) return `${label}: Unavailable`;
    return `${label}: see technical details`;
  });
}
function AlarmsPanel({ asset, openCount, alerts }: { asset: string; openCount?: number; alerts: AlertsState }) {
  return <section className="console-panel" aria-label="Alerts"><div className="section-heading"><div><h2>Alarms & events</h2><p>{asset} · 24-hour event-time window · open alerts at latest reading: {openCount ?? 'Unknown'}</p></div><Bell size={18} aria-hidden="true"/></div><RequestStatus state={alerts} label="Events"/>{alerts.data?.items.length === 0 && <div className="empty-state">No events returned in this window. This is not a healthy-state assertion.</div>}
    {!!alerts.data?.items.length && <div className="table-scroll"><table><thead><tr><th>Severity</th><th>Event</th><th>Evidence</th><th>Event time</th><th>Lifecycle</th></tr></thead><tbody>{alerts.data.items.map(event => {
      const lines = evidenceLines(event.evidence);
      return <tr key={event.id}><td><Badge tone={event.severity === 'CRITICAL' ? 'danger' : event.severity === 'WARNING' ? 'warning' : 'info'}>{codeLabel(event.severity)}</Badge></td><td><strong>{codeLabel(event.alert_type)}</strong><small>{event.transformer_id}</small></td><td className="evidence-cell">{lines.length ? <ul className="text-list">{lines.map((line, i) => <li key={i}>{line}</li>)}</ul> : <p>No evidence fields supplied.</p>}{event.recommended_action && <p className="evidence-action">Backend recommendation: {event.recommended_action}</p>}<TechnicalDetails><KeyValues items={[['Alert ID', event.id], ['Alert type', event.alert_type], ['Trigger', event.trigger], ['Threshold or reason', event.threshold_or_reason], ['Severity code', event.severity], ['Status code', event.status]]}/><pre>{JSON.stringify(event.evidence,null,2)}</pre></TechnicalDetails></td><td><EventTime value={event.timestamp}/></td><td>{codeLabel(event.status)}<small>Last seen <EventTime value={event.last_seen_at}/></small></td></tr>;
    })}</tbody></table></div>}
    {alerts.data && <p className="disclosure">Showing {alerts.data.items.length} of {alerts.data.total}; older events outside the window are not included.</p>}</section>;
}
function TransformerCard({ asset, snapshot, now, choose }: { asset: Asset; snapshot?: import('../../hooks/useConsoleData').AssetSnapshot; now: number; choose: (id: string) => void }) {
  const data = snapshot?.data, t = data?.telemetry, state = operatingState(data, snapshot?.error);
  return <button className="transformer-card" onClick={() => choose(asset.id)} aria-label={`Monitor ${asset.id}`}><div className="asset-card-heading"><Badge tone={state.tone}>{state.label}</Badge><ArrowRight size={16} aria-hidden="true"/></div><div className="asset-card-identity"><TransformerDrawing small/><div><h3>{asset.id}</h3>{asset.name !== asset.id && <p>{asset.name}</p>}<small>{codeLabel(t?.acquisition?.source_kind, 'Unknown')} source</small></div></div><div className="asset-card-readings"><Reading label="Voltage L1" field="phase_voltage_l1" record={t}/><Reading label="Current L1" field="current_l1" record={t}/><Reading label="Oil temperature" field="oil_temperature" record={t}/><Reading label="Active power" field="active_power_total" record={t}/></div><div className="asset-card-footer"><div><EventTime value={t?.timestamp}/><small>{freshness(t,snapshot?.lastSuccess ?? null,now,snapshot?.error ?? null)}</small></div><span className="asset-card-alerts">Open alerts: {data?.open_alerts_count ?? 'Unknown'}</span></div></button>;
}
