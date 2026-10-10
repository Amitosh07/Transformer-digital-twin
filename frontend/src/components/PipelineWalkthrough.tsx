import { useState } from 'react';
const stages = [
  ['Acquire','Sources send canonical, nullable telemetry with acquisition provenance. Source labels do not establish authorization or unit verification.'],
  ['Validate','The backend validates identity, timestamps, finite values and protection contacts. Exact retries are idempotent; changed observations conflict.'],
  ['Prepare','The ML runtime prepares inference against a candidate state. Component readiness, coverage and unit limitations accompany its outputs.'],
  ['Commit','Telemetry, analytics, effects, receipt and checkpoint share a SQL transaction. Candidate state is installed only after successful commit.'],
  ['Monitor','The browser requests registry, latest and bounded history. It displays backend outputs without calculating replacement analytics.'],
];
export function PipelineWalkthrough() {
  const [active,setActive] = useState(0);
  return <section id="pipeline" className="py-20 px-4 max-w-7xl mx-auto"><h2 className="text-3xl text-slate-100 font-bold">Data pipeline walkthrough</h2>
    <p className="text-slate-400 my-4">Architecture explanation; this section contains no live measurements and does not prove deployment acceptance.</p>
    <div className="flex flex-wrap gap-3 mb-5">{stages.map(([title],i) => <button key={title} onClick={() => setActive(i)} aria-pressed={active===i} className={'rounded-xl px-4 py-3 border ' + (active===i ? 'border-amber-500 text-amber-300':'border-slate-700 text-slate-300')}>{i+1}. {title}</button>)}</div>
    <article className="rounded-xl border border-slate-800 bg-[#0A0E17] p-6 text-slate-300"><h3 className="text-lg text-cyan-300">{stages[active][0]}</h3><p>{stages[active][1]}</p>
      <pre className="text-xs mt-5 overflow-x-auto">{'GET /api/v1/transformers/{id}/latest\nGET /api/v1/transformers/{id}/telemetry?from=<UTC>&to=<UTC>&limit=100\nGET /api/v1/transformers/{id}/analytics?from=<UTC>&to=<UTC>&limit=100'}</pre>
    </article></section>;
}
