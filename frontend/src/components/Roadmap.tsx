import React from 'react';
import { Milestone, CheckCircle2, Clock, Compass, Shield } from 'lucide-react';

export const Roadmap: React.FC = () => {
  const phases = [
    {
      quarter: 'PHASE 1 • COMPLETED',
      title: 'Canonical Architecture & Kaggle Baseline',
      status: 'COMPLETE',
      statusClass: 'text-emerald-400 bg-emerald-950/60 border-emerald-800',
      description:
        'Established Canonical Schema v1.0.0 and ML Contract v1.0.0. Ingested and aligned Kaggle 5-file dataset with zero zero-filling and strict exclusion of unverified line voltages.',
      deliverables: [
        'Multi-table DeviceTimeStamp alignment',
        'Data hygiene verification & zero-leakage pipeline',
        'Canonical TransformerRecord boundary definition',
      ],
    },
    {
      quarter: 'PHASE 2 • COMPLETED',
      title: 'Thermodynamic Twin & Fault Simulator',
      status: 'COMPLETE',
      statusClass: 'text-emerald-400 bg-emerald-950/60 border-emerald-800',
      description:
        'Engineered the backend top-oil thermal model, isolating the Thermal Residual (Observed - Model). Built 6-pillar Health Index engine and deterministic fault injection suite.',
      deliverables: [
        'Continuous Thermal Residual ΔT tracking',
        'Deterministic fault injection (Overload, Thermal, Imbalance)',
        'FastAPI REST endpoints and PostgreSQL time-series schema',
      ],
    },
    {
      quarter: 'PHASE 3 • CURRENT (HACKATHON TRACK)',
      title: 'CPRI & PowerNext Testbed Ingestion',
      status: 'IN PROGRESS',
      statusClass: 'text-amber-400 bg-amber-950/60 border-amber-800 animate-pulse',
      description:
        'Developing pluggable data adapters for Central Power Research Institute (CPRI) physical transformer test rigs and live PowerNext telemetry feeds over MQTT.',
      deliverables: [
        'CPRI high-voltage lab testbed adapter',
        'MQTT streaming broker integration for live telemetry',
        'Prescriptive maintenance ERP / Maximo webhook hooks',
      ],
    },
    {
      quarter: 'PHASE 4 • UPCOMING',
      title: 'Substation Edge Gateway Deployment',
      status: 'PLANNED',
      statusClass: 'text-cyan-400 bg-cyan-950/60 border-cyan-800',
      description:
        'Containerized edge deployment on substation industrial IoT gateways (IEC 61850 / DNP3) enabling local sub-second inference even during backhaul network loss.',
      deliverables: [
        'IEC 61850 substation bus protocol support',
        'Offline edge inference fallback buffer',
        'DISCOM pilot rollout across 50 urban distribution feeders',
      ],
    },
  ];

  return (
    <section id="roadmap" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono uppercase tracking-wider mb-4">
          <Compass className="w-3.5 h-3.5 text-cyan-400" />
          Production Trajectory
        </div>
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-display font-extrabold text-slate-100 tracking-tight">
          From Baseline to Utility Grid
        </h2>
        <p className="mt-4 text-base sm:text-lg text-slate-400 leading-relaxed font-sans">
          A disciplined engineering trajectory connecting academic data validation to live substation operational deployment.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {phases.map((phase, idx) => (
          <div
            key={idx}
            className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-[10px] font-mono text-slate-400 font-bold">
                  {phase.quarter}
                </span>
                <span
                  className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${phase.statusClass}`}
                >
                  {phase.status}
                </span>
              </div>

              <h3 className="text-lg font-display font-bold text-slate-100 mb-2">
                {phase.title}
              </h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed mb-4">
                {phase.description}
              </p>

              <div className="pt-3 border-t border-slate-800/80">
                <ul className="space-y-1.5 text-[11px] font-mono text-slate-300">
                  {phase.deliverables.map((d, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="mt-6 pt-3 border-t border-slate-800/80 text-[10px] font-mono text-slate-500">
              MILESTONE 0{idx + 1}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
