import React from 'react';
import {
  ShieldCheck,
  Thermometer,
  Cpu,
  RotateCcw,
  Database,
  Server,
  Zap,
  BarChart3,
} from 'lucide-react';

export const FeaturesGrid: React.FC = () => {
  const features = [
    {
      icon: <Thermometer className="w-5 h-5 text-amber-400" />,
      title: 'Physics-Informed Thermal Residual',
      description:
        'Displays backend thermal estimates and residuals with reported units and component readiness.',
      tag: 'CORE INNOVATION',
    },
    {
      icon: <ShieldCheck className="w-5 h-5 text-emerald-400" />,
      title: '6-Pillar Transparent Health Index',
      description:
        'Displays backend health scores and component values. Weights are shown only where evidence is available.',
      tag: 'EXPLAINABLE AI',
    },
    {
      icon: <Cpu className="w-5 h-5 text-cyan-400" />,
      title: 'Multivariate Anomaly Engine',
      description:
        'Continuous 0.0–1.0 abnormality scoring analyzing 3-phase current imbalance, neutral zero-sequence current, and rapid rate-of-rise thermal trajectories.',
      tag: 'ML INFERENCE',
    },
    {
      icon: <RotateCcw className="w-5 h-5 text-purple-400" />,
      title: 'Deterministic Fault Injection & Replay',
      description:
        'Comprehensive simulator capable of replaying Kaggle SCADA logs at 1x–50x speed and injecting Overload, Thermal Stress, Current Imbalance, and Oil Leak scenarios.',
      tag: 'SIMULATOR & REPLAY',
    },
    {
      icon: <Database className="w-5 h-5 text-rose-400" />,
      title: 'Canonical Schema Boundary v1.1.0',
      description:
        'Strict schema insulation layer quarantining vendor quirks. Prohibits silent zero-filling and excludes unverified line voltages (VL12, VL23, VL31).',
      tag: 'DATA HYGIENE',
    },
    {
      icon: <Server className="w-5 h-5 text-amber-400" />,
      title: 'FastAPI & PostgreSQL Microservices',
      description:
        'RESTful architecture; deployment acceptance remains pending with Pydantic validation, Alembic migrations, time-series indexing on (transformer_id, timestamp), and Docker Compose.',
      tag: 'ARCHITECTURE',
    },
  ];

  return (
    <section id="features" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono uppercase tracking-wider mb-4">
          <Zap className="w-3.5 h-3.5 text-amber-400" />
          Technical Depth & Engineering
        </div>
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-display font-extrabold text-slate-100 tracking-tight">
          Engineered for Utility Realities
        </h2>
        <p className="mt-4 text-base sm:text-lg text-slate-400 leading-relaxed font-sans">
          Source evidence, configuration verification and deployment acceptance remain explicit. Standards compliance has not been established.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {features.map((feat, i) => (
          <div
            key={i}
            className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-6 shadow-xl hover:border-slate-700 transition flex flex-col justify-between group"
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center group-hover:scale-105 transition">
                  {feat.icon}
                </div>
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
                  {feat.tag}
                </span>
              </div>

              <h3 className="text-lg font-display font-bold text-slate-100 mb-2">
                {feat.title}
              </h3>
              <p className="text-sm text-slate-400 font-sans leading-relaxed">
                {feat.description}
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-500">
              <span>Verified Module</span>
              <span className="text-emerald-400">STATUS: READY</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
