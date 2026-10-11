export function ImpactMetrics() {
  const evidence = [
    ['Health and readiness','Scores, coverage and reasons are supplied by the backend. Unavailable analytics do not establish a healthy asset.'],
    ['Source and time','Measurement time, analysis time and last successful poll are shown separately. Replay data remains historical.'],
    ['Forecast release','Operational risk and confidence require backend release evidence. Predictive lead time has not been established.'],
    ['Integration evidence','Live backend-to-browser acceptance, outage reduction, latency and compliance claims require measured evidence.'],
  ];
  return <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800"><h2 className="text-3xl font-bold text-slate-100 mb-8">Monitoring with visible evidence</h2>
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">{evidence.map(([title,text]) => <article key={title} className="bg-[#0A0E17] border border-slate-800 rounded-xl p-6"><h3 className="text-amber-300 mb-3">{title}</h3><p className="text-sm text-slate-400">{text}</p></article>)}</div></section>;
}
