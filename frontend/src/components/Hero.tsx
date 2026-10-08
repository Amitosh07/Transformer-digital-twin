import React from 'react';
import {
  Sparkles,
  ArrowRight,
  Shield,
  Activity,
  FileCode2,
  CheckCircle2,
  Flame,
  Zap,
} from 'lucide-react';

export const Hero: React.FC = () => {
  return (
    <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto overflow-hidden">
      {/* Background Gradients */}
      <div className="absolute top-10 left-10 w-96 h-96 bg-amber-500/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute top-20 right-10 w-96 h-96 bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        {/* Left Column: Editorial Headline & Value Prop */}
        <div className="lg:col-span-7 space-y-6">
          {/* Eyebrow Pill */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300 shadow-lg">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
            <span className="text-amber-400 font-semibold">CYBER-PHYSICAL SCADA TWIN</span>
            <span className="text-slate-600">/</span>
            <span className="text-slate-400">IEEE THERMAL COMPLIANT</span>
          </div>

          {/* Main Title */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-display font-extrabold text-slate-100 tracking-tight leading-[1.08]">
            Prevent Substation Failures <br className="hidden sm:inline" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 via-amber-200 to-amber-500">
              Before Trip Switches Fire.
            </span>
          </h1>

          {/* Subtitle / Copy in human natural voice */}
          <p className="text-base sm:text-lg text-slate-300 leading-relaxed font-sans max-w-2xl">
            Standard grid monitoring treats transformers like black boxes, tripping power only after thermal catastrophe strikes. Our Digital Twin pairs <strong>IEEE thermodynamic modeling</strong> with <strong>multivariate anomaly detection</strong> to isolate thermal residuals (ΔT = T<sub>obs</sub> − T<sub>model</sub>)—giving utilities <strong>48 hours of advance foresight</strong>.
          </p>

          {/* Key Checklist Badges */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono text-slate-300 pt-2">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Canonical Schema v1.0.0 (Zero zero-filling)</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Physics-derived Thermal Residual (ΔT)</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>6-Pillar Explainable Health Index (0–100)</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>FastAPI & Docker Compose Orchestration</span>
            </div>
          </div>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center gap-4 pt-4">
            <a
              href="#demo"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-black font-semibold text-sm font-mono shadow-[0_0_25px_rgba(245,158,11,0.4)] transition transform hover:-translate-y-0.5 active:translate-y-0"
            >
              <Sparkles className="w-4 h-4 fill-black" />
              <span>Launch Live Twin Studio</span>
              <ArrowRight className="w-4 h-4" />
            </a>

            <a
              href="#architecture"
              className="inline-flex items-center gap-2 px-5 py-3.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-200 text-sm font-mono transition"
            >
              <FileCode2 className="w-4 h-4 text-cyan-400" />
              <span>Inspect Architecture</span>
            </a>
          </div>
        </div>

        {/* Right Column: Holographic Digital Twin CAD Showcase */}
        <div className="lg:col-span-5 relative">
          <div className="relative rounded-2xl overflow-hidden border border-slate-800 bg-[#0A0E17] shadow-2xl group">
            {/* Holographic Cutaway Asset */}
            <img
              src="/assets/transformer_hero.jpg"
              alt="Transformer Digital Twin 3D CAD Holographic Telemetry"
              className="w-full h-auto object-cover transform group-hover:scale-102 transition duration-700"
            />

            {/* Glowing Sensor Hotspot Pins */}
            <div className="absolute top-[38%] left-[45%] -translate-x-1/2 -translate-y-1/2">
              <div className="relative flex items-center justify-center">
                <span className="w-3.5 h-3.5 rounded-full bg-amber-500 animate-ping absolute"></span>
                <span className="w-3 h-3 rounded-full bg-amber-400 shadow-[0_0_12px_#f59e0b] relative"></span>
              </div>
            </div>

            <div className="absolute bottom-[28%] right-[22%] -translate-x-1/2 -translate-y-1/2">
              <div className="relative flex items-center justify-center">
                <span className="w-3.5 h-3.5 rounded-full bg-cyan-500 animate-ping absolute"></span>
                <span className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_12px_#06b6d4] relative"></span>
              </div>
            </div>

            {/* Floating Live Telemetry Badge Overlay */}
            <div className="absolute bottom-4 left-4 right-4 bg-slate-950/85 backdrop-blur-md border border-slate-800/90 rounded-xl p-3 shadow-2xl flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded-lg bg-amber-500/20 text-amber-400">
                  <Activity className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-slate-200 font-semibold">TRANS-DT-104 (Substation)</div>
                  <div className="text-[10px] text-slate-400">33/11 kV • 20 MVA Step-Down</div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-emerald-400 font-bold">HEALTH: 94 / 100</div>
                <div className="text-[10px] text-slate-400">ΔT RESIDUAL: +1.2°C</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Live SCADA Telemetry Stream Ticker Banner */}
      <div className="mt-16 bg-[#0B0F19] border border-slate-800 rounded-xl p-3 overflow-hidden shadow-lg">
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 shrink-0 font-semibold">
            <Activity className="w-3.5 h-3.5 animate-pulse" />
            <span>LIVE CANONICAL STREAM</span>
          </div>

          <div className="flex items-center gap-8 text-slate-400 overflow-x-auto whitespace-nowrap scrollbar-none py-1">
            <span className="flex items-center gap-1.5">
              <span className="text-slate-500">Asset:</span> <strong className="text-slate-200">TX-104</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-500">Phase I<sub>L1</sub>:</span> <strong className="text-amber-400">348.2 A</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-500">Phase I<sub>L2</sub>:</span> <strong className="text-cyan-400">345.9 A</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-500">Phase I<sub>L3</sub>:</span> <strong className="text-emerald-400">350.1 A</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-500">Neutral I<sub>NUT</sub>:</span> <strong className="text-slate-200">3.2 A</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-500">Top-Oil (OTI):</span> <strong className="text-slate-200">58.4°C</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-500">Winding (WTI):</span> <strong className="text-slate-200">71.2°C</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-500">Thermal Residual:</span> <strong className="text-emerald-400">+1.2°C</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-500">Power Factor:</span> <strong className="text-slate-200">0.96</strong>
            </span>
          </div>
        </div>
      </div>
    </section>
  );
};
