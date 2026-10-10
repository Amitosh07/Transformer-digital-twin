import React from 'react';
import { Users, Brain, Server, Layout, Terminal } from 'lucide-react';

export const Team: React.FC = () => {
  const members = [
    {
      role: 'Person 1 — ML + Digital Twin / Team Lead',
      name: 'Amitosh Nigam',
      title: 'Digital Twin Architect & ML Lead',
      icon: <Brain className="w-6 h-6 text-amber-400" />,
      responsibilities: [
        'Author of Canonical Schema v1.0.0 & ML Contract v1.0.0',
        'Backend thermal residual modelling',
        'Multivariate anomaly detection & 6-pillar Health Index engine',
        'Evaluation rigor: zero temporal data leakage',
      ],
      tag: 'LEAD ARCHITECT',
    },
    {
      role: 'Person 2 — Backend + Database Architect',
      name: 'Core Backend Engineer',
      title: 'FastAPI & Data Platform Lead',
      icon: <Server className="w-6 h-6 text-cyan-400" />,
      responsibilities: [
        'FastAPI asynchronous REST microservices (/api/v1/)',
        'PostgreSQL time-series models with composite indexing',
        'Alembic database migrations & Pydantic request validation',
        'Canonical telemetry ingestion & ML result persistence',
      ],
      tag: 'BACKEND & DB',
    },
    {
      role: 'Person 3 — Frontend + Dashboard Lead',
      name: 'Senior Frontend Engineer',
      title: 'Presentation & UI/UX Architect',
      icon: <Layout className="w-6 h-6 text-emerald-400" />,
      responsibilities: [
        'Cyber-physical SCADA monitoring interface in React + TS',
        '60 FPS 3-phase vector canvas & thermal residual visualizations',
        'Real-time Health Index gauges & prescriptive dispatch cards',
        'Mobile-first responsive design, light/dark themes, accessibility',
      ],
      tag: 'FRONTEND & UX',
    },
    {
      role: 'Person 4 — Simulator + DevOps Engineer',
      name: 'Simulation & DevOps Lead',
      title: 'Synthetic SCADA & Infrastructure Lead',
      icon: <Terminal className="w-6 h-6 text-purple-400" />,
      responsibilities: [
        'Historical SCADA replay engine with 1x–50x speed scaling',
        'Deterministic fault injection library (Overload, Thermal, Imbalance)',
        'MQTT live streaming & synthetic telemetry generation',
        'Docker & Docker Compose one-command orchestration',
      ],
      tag: 'SIMULATOR & DEVOPS',
    },
  ];

  return (
    <section id="team" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-400 text-xs font-mono uppercase tracking-wider mb-4">
          <Users className="w-3.5 h-3.5 text-purple-400" />
          Dataschema.md Section 20 Ownership
        </div>
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-display font-extrabold text-slate-100 tracking-tight">
          Four Pillars of Engineering
        </h2>
        <p className="mt-4 text-base sm:text-lg text-slate-400 leading-relaxed font-sans">
          Clear module boundaries and strict API contracts allowed our four-person team to build autonomously without merge conflicts or architectural drift.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {members.map((m, idx) => (
          <div
            key={idx}
            className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between hover:border-slate-700 transition group"
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center group-hover:scale-105 transition">
                  {m.icon}
                </div>
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
                  {m.tag}
                </span>
              </div>

              <div className="text-xs font-mono text-amber-400 mb-1">{m.role}</div>
              <h3 className="text-xl font-display font-bold text-slate-100 mb-1">{m.name}</h3>
              <div className="text-xs text-slate-400 font-sans mb-4">{m.title}</div>

              <div className="pt-3 border-t border-slate-800/80">
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-2">
                  Key Deliverables
                </div>
                <ul className="space-y-1.5 text-xs font-mono text-slate-300">
                  {m.responsibilities.map((r, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-amber-500 shrink-0">›</span>
                      <span className="text-[11px] leading-relaxed">{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="mt-6 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-500">
              <span>Boundary Verified</span>
              <span className="text-emerald-400">CONTRACT REVIEW</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
