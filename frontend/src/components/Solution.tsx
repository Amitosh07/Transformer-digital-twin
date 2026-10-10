import React from 'react';
import { Cpu, Thermometer, ShieldCheck, Wrench, ArrowRight } from 'lucide-react';

export const Solution: React.FC = () => {
  return (
    <section id="solution" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        {/* Left Column: Solution Narrative */}
        <div className="lg:col-span-6 space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono uppercase tracking-wider">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            The Cyber-Physical Breakthrough
          </div>

          <h2 className="text-3xl sm:text-4xl md:text-5xl font-display font-extrabold text-slate-100 tracking-tight leading-tight">
            Thermodynamic Residual: <br />
            Physics Meets Machine Learning.
          </h2>

          <p className="text-slate-300 font-sans leading-relaxed text-sm sm:text-base">
            Transformers are physical thermodynamic systems, not random number generators. By pairing <strong>backend thermal modelling</strong> with <strong>machine learning anomaly detection</strong>, our digital twin estimates what the top-oil temperature <em>should</em> be for any given load and ambient air condition.
          </p>

          <p className="text-slate-400 font-sans leading-relaxed text-sm">
            The difference between reality and physics is the <strong>Thermal Residual (ΔT = T<sub>obs</sub> − T<sub>model</sub>)</strong>. When radiator circulation is blocked or winding hotspots develop, the residual diverges instantly—generating proactive work orders before insulation degrades.
          </p>

          {/* 3 Pillars */}
          <div className="space-y-3 pt-2 font-mono text-xs">
            <div className="flex items-start gap-3 p-3 rounded-xl bg-slate-900 border border-slate-800">
              <Thermometer className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-slate-200 block text-sm">Thermodynamic Residual Isolation</strong>
                <span className="text-slate-400">
                  Shows observed and model temperatures with source units, readiness and coverage evidence.
                </span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl bg-slate-900 border border-slate-800">
              <Cpu className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-slate-200 block text-sm">6-Pillar Transparent Health Index</strong>
                <span className="text-slate-400">
                  Explains condition scores across thermal, electrical, loading, oil, alarm, and anomaly factors.
                </span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl bg-slate-900 border border-slate-800">
              <Wrench className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-slate-200 block text-sm">Prescriptive Maintenance Dispatch</strong>
                <span className="text-slate-400">
                  Displays backend maintenance recommendations and their supplied reason codes.
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Mathematical / Technical Comparison Panel */}
        <div className="lg:col-span-6">
          <div className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-6 shadow-2xl relative">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-5 text-xs font-mono">
              <span className="text-slate-400 uppercase tracking-wider">Concept explanation — no live values</span>
              <span className="text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-2 py-0.5 rounded">
                READINESS AND UNIT GATES
              </span>
            </div>

            {/* Differential Equation Card */}
            <div className="p-4 rounded-xl bg-[#06080E] border border-slate-800 text-center font-mono my-4 space-y-2">
              <div className="text-xs text-slate-400 uppercase tracking-widest">Backend thermal residual</div>
              <div className="text-base sm:text-lg font-bold text-amber-400 py-1">
                ΔT = T<sub>observed</sub> − T<sub>model</sub>
              </div>
              <div className="text-[11px] text-slate-400">
                Interpretation requires compatible source units and a ready backend model.
              </div>
            </div>

            {/* Comparative Breakdown Table */}
            <div className="grid grid-cols-2 gap-3 text-xs font-mono pt-2">
              <div className="bg-rose-950/20 border border-rose-900/50 p-3 rounded-xl">
                <div className="text-rose-400 font-bold mb-1">Traditional SCADA</div>
                <ul className="space-y-1 text-slate-400 text-[11px]">
                  <li>• Static threshold trigger</li>
                  <li>• Asset-specific protection settings</li>
                  <li>• No load/ambient awareness</li>
                  <li>• Zero proactive warning</li>
                </ul>
              </div>

              <div className="bg-emerald-950/20 border border-emerald-900/50 p-3 rounded-xl">
                <div className="text-emerald-400 font-bold mb-1">Digital Twin Core</div>
                <ul className="space-y-1 text-slate-300 text-[11px]">
                  <li>• Physics-informed ΔT residual</li>
                  <li>• Real-time model comparison</li>
                  <li>• Ambient-normalized tracking</li>
                  <li>• Backend maintenance advice</li>
                </ul>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400">
                Ready to test the physics engine?
              </span>
              <a
                href="#demo"
                className="inline-flex items-center gap-1.5 text-xs font-mono text-amber-400 hover:text-amber-300 font-semibold"
              >
                <span>Jump to Interactive Studio</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
