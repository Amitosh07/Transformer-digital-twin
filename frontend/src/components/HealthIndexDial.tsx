import type { Analytics } from '../api/contracts';
import { panel } from './ResourceCards';
import { codeLabel, numberLabel, reasonLabel } from './console/presentation';
import { CodeList, KeyValues, TechnicalDetails } from './console/TelemetryPanels';

export function HealthIndexDial({ analytics }: { analytics: Analytics | null | undefined }) {
  const score = analytics?.health_index;
  const components = analytics?.health_components;
  const names = ['thermal','electrical','loading','oil','alarm','anomaly'] as const;
  const reasons = [...(analytics?.health_reason_codes ?? []), ...(analytics?.metadata?.extended_health_reason_codes ?? [])];
  const readiness = analytics?.metadata?.components?.health?.status ?? analytics?.inference_status;
  return <section className={panel + ' resource-card'} aria-label="Health index">
    <h3 className="text-lg text-amber-300">Backend health index</h3>
    <div className="health-layout flex flex-col sm:flex-row items-center gap-6">
      <div className="health-dial relative w-44 h-44 shrink-0">
        <svg viewBox="0 0 180 180" className="w-full h-full -rotate-90" aria-hidden="true">
          <circle cx="90" cy="90" r="70" fill="none" stroke="#1e293b" strokeWidth="12" />
          {score != null && <circle cx="90" cy="90" r="70" fill="none" stroke="#f59e0b" strokeWidth="12" strokeDasharray={440} strokeDashoffset={440*(1-score/100)} />}
        </svg>
        <div className={'health-score absolute inset-0' + (score == null ? ' unavailable' : '') + ' flex items-center justify-center text-4xl'}>{score == null ? 'Unavailable' : numberLabel(score)}{score != null && <span className="text-xs"> / 100</span>}</div>
      </div>
      <dl className="health-components grid grid-cols-2 gap-3 flex-1">{names.map(name => <div key={name}><dt>{codeLabel(name.toUpperCase())}</dt><dd>{numberLabel(components?.[name])}</dd></div>)}</dl>
    </div>
    <h4>Readiness and coverage</h4>
    <KeyValues items={[['Readiness', codeLabel(readiness, 'Unavailable')], ['Health coverage', analytics?.metadata?.health_coverage == null ? 'Unknown' : numberLabel(analytics.metadata.health_coverage)], ['Component weights', 'Not supplied by API']]}/>
    <h4>Health reasons</h4>
    {reasons.length ? <ul className="text-list">{reasons.map((code, i) => <li key={i}>{reasonLabel(code, analytics?.metadata?.reason_descriptions)}</li>)}</ul> : <p>No health reasons supplied</p>}
    <TechnicalDetails><KeyValues items={[['Readiness code', readiness ?? 'UNAVAILABLE'], ['Health reason codes', <CodeList key="codes" codes={reasons}/>]]}/></TechnicalDetails>
  </section>;
}
