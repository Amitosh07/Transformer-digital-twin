import React from 'react';
import { AlertTriangle, Flame, ShieldAlert, Database, FileSpreadsheet } from 'lucide-react';

export const Problem: React.FC = () => {
  return (
    <section id="problem" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
      {/* Section Eyebrow */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono uppercase tracking-wider mb-3">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
            Grid Operational Blindspots
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-display font-extrabold text-slate-100 tracking-tight">
            The Silent Substation Catastrophe
          </h2>
        </div>
        <p className="text-slate-400 font-sans max-w-md text-sm sm:text-base leading-relaxed">
          Distribution transformers represent the most vulnerable, capital-intensive nodes in electrical distribution grids. Here is why current monitoring architectures fail.
        </p>
      </div>

      {/* 3 Core Failure Vectors */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Card 1: The Static Threshold Fallacy */}
        <div className="bg-[#0A0E17] border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden group hover:border-slate-700 transition">
          <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400 mb-5">
            <Flame className="w-5 h-5" />
          </div>

          <h3 className="text-lg font-display font-bold text-slate-100 mb-2">
            The Static Threshold Trap
          </h3>
          <p className="text-sm text-slate-400 font-sans leading-relaxed mb-4">
            A temperature reading needs load, ambient conditions and verified asset configuration for interpretation. Protection settings are asset-specific; missing evidence cannot establish a universal safe limit or prove the asset is healthy.
          </p>

          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800/80 text-xs font-mono text-rose-400">
            • 0-minute warning before catastrophic oil trip
          </div>
        </div>

        {/* Card 2: The Black-Box ML Illusion */}
        <div className="bg-[#0A0E17] border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden group hover:border-slate-700 transition">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mb-5">
            <ShieldAlert className="w-5 h-5" />
          </div>

          <h3 className="text-lg font-display font-bold text-slate-100 mb-2">
            Black-Box AI Hallucinations
          </h3>
          <p className="text-sm text-slate-400 font-sans leading-relaxed mb-4">
            Most hackathon AI models throw raw neural networks or XGBoost at telemetry without embedding physical thermodynamics. They suffer from temporal data leakage (mixing future and past data), lack explainability, and cannot tell utility operators <em>why</em> a health score dropped.
          </p>

          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800/80 text-xs font-mono text-amber-400">
            • Zero physical basis & zero explainability
          </div>
        </div>

        {/* Card 3: Dirty Ingestion & Vendor Lock */}
        <div className="bg-[#0A0E17] border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden group hover:border-slate-700 transition">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mb-5">
            <Database className="w-5 h-5" />
          </div>

          <h3 className="text-lg font-display font-bold text-slate-100 mb-2">
            Schema Pollution & Zero-Filling
          </h3>
          <p className="text-sm text-slate-400 font-sans leading-relaxed mb-4">
            Raw SCADA data is messy. CSV files leak unverified line voltages (VL12, VL23), disparate vendor column headers (OTI vs Temp), and intermittent missing sensor readings. Naive systems silently fill gaps with zeroes, creating false alarms that fatigue control room operators.
          </p>

          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800/80 text-xs font-mono text-cyan-400">
            • Fragile architectures break outside sample CSVs
          </div>
        </div>
      </div>
    </section>
  );
};
