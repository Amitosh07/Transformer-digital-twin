import type { Analytics } from '../api/contracts';
import { panel } from './ResourceCards';

export function HealthIndexDial({ analytics }: { analytics: Analytics | null | undefined }) {
  const score = analytics?.health_index;
  const components = analytics?.health_components;
  const names = ['thermal','electrical','loading','oil','alarm','anomaly'] as const;
  const reasons = [...(analytics?.health_reason_codes ?? []), ...(analytics?.metadata?.extended_health_reason_codes ?? [])];
  return <section className={panel} aria-label="Health index">
    <h3 className="text-lg text-amber-300">Backend health index</h3>
    <div className="flex flex-col sm:flex-row items-center gap-6">
      <div className="relative w-44 h-44 shrink-0">
        <svg viewBox="0 0 180 180" className="w-full h-full -rotate-90" aria-hidden="true">
          <circle cx="90" cy="90" r="70" fill="none" stroke="#1e293b" strokeWidth="12" />
          {score != null && <circle cx="90" cy="90" r="70" fill="none" stroke="#f59e0b" strokeWidth="12" strokeDasharray={440} strokeDashoffset={440*(1-score/100)} />}
        </svg>
        <div className="absolute inset-0 flex items-center justify-center text-4xl">{score == null ? 'Unavailable' : Number(score.toFixed(2))}<span className="text-xs"> / 100</span></div>
      </div>
      <dl className="grid grid-cols-2 gap-3 flex-1">{names.map(name => <div key={name}><dt>{name}</dt><dd>{components?.[name] ?? 'Unavailable'}</dd></div>)}</dl>
    </div>
    <p>Readiness: {analytics?.metadata?.components?.health?.status ?? analytics?.inference_status ?? 'UNAVAILABLE'}</p>
    <p>Health coverage: {analytics?.metadata?.health_coverage ?? 'Unknown'} · Component weights: not supplied by API</p>
    <p>{reasons.join(', ') || 'No health reasons supplied'}</p>
  </section>;
}
