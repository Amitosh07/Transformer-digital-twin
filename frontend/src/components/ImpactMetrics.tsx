import React from 'react';
import { TrendingUp, Clock, AlertOctagon, CheckCircle2, Zap } from 'lucide-react';

export const ImpactMetrics: React.FC = () => {
  const metrics = [
    {
      value: '+48h',
      label: 'Predictive Lead Time',
      subtext: 'Advance notice compared to traditional 0-minute threshold trip breakers.',
      icon: <Clock className="w-5 h-5 text-amber-400" />,
    },
    {
      value: '-74%',
      label: 'Unplanned Outage Reduction',
      subtext: 'Minimizes catastrophic transformer burnouts and emergency load-shedding.',
      icon: <TrendingUp className="w-5 h-5 text-emerald-400" />,
    },
    {
      value: '100%',
      label: 'Schema Contract Compliance',
      subtext: 'Zero raw vendor column leaks across ML models, APIs, and dashboards.',
      icon: <CheckCircle2 className="w-5 h-5 text-cyan-400" />,
    },
    {
      value: '<15ms',
      label: 'Per-Frame Inference Latency',
      subtext: 'Ultra-low latency execution suitable for real-time edge substation telemetry.',
      icon: <Zap className="w-5 h-5 text-purple-400" />,
    },
  ];

  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
      <div className="bg-[#0B0F19] border border-slate-800 rounded-3xl p-8 sm:p-12 shadow-2xl relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-0 right-0 w-80 h-80 bg-amber-500/10 rounded-full blur-[100px] pointer-events-none" />

        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 mb-12">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono uppercase tracking-wider mb-3">
              <Zap className="w-3.5 h-3.5 text-emerald-400" />
              Quantified Reliability Gains
            </div>
            <h2 className="text-3xl sm:text-4xl font-display font-extrabold text-slate-100 tracking-tight">
              Impact That Matters to Power Utilities
            </h2>
          </div>
          <p className="text-slate-400 font-sans max-w-md text-sm leading-relaxed">
            Eliminating false alarms and averting catastrophic transformer failures preserves critical infrastructure, protects utility revenues, and enhances grid resilience.
          </p>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {metrics.map((m, idx) => (
            <div
              key={idx}
              className="bg-[#06080E] border border-slate-800/80 rounded-2xl p-6 shadow-lg flex flex-col justify-between"
            >
              <div>
                <div className="w-9 h-9 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center mb-4">
                  {m.icon}
                </div>
                <div className="text-4xl sm:text-5xl font-display font-extrabold text-slate-100 tracking-tight mb-2">
                  {m.value}
                </div>
                <div className="text-sm font-semibold text-slate-200 mb-1">{m.label}</div>
              </div>
              <p className="text-xs text-slate-400 font-sans leading-relaxed mt-2 pt-2 border-t border-slate-900">
                {m.subtext}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
