import React, { useState } from 'react';
import { Copy, Check, Sparkles, ArrowUpRight } from 'lucide-react';
import { GithubIcon } from './GithubIcon';

export const PitchDeckCTA: React.FC = () => {
  const [copied, setCopied] = useState(false);

  const command = `git clone https://github.com/Amitosh07/Transformer-digital-twin.git
cd Transformer-digital-twin
docker compose up --build`;

  const handleCopy = () => {
    navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
      <div className="bg-gradient-to-b from-[#0F1422] to-[#0A0D15] border border-amber-500/20 rounded-3xl p-8 sm:p-14 shadow-2xl relative overflow-hidden text-center">
        {/* Glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-amber-500/10 rounded-full blur-[140px] pointer-events-none" />

        <div className="max-w-3xl mx-auto space-y-6 relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            One-Command Reproducibility
          </div>

          <h2 className="text-3xl sm:text-4xl md:text-5xl font-display font-extrabold text-slate-100 tracking-tight">
            Spin Up the Full Digital Twin Stack
          </h2>

          <p className="text-slate-300 font-sans text-base sm:text-lg leading-relaxed">
            FastAPI microservices, PostgreSQL time-series database, Scikit-learn feature engine, and the modern UI run synchronously with a single Docker Compose instruction.
          </p>

          {/* Terminal Command Window */}
          <div className="max-w-xl mx-auto rounded-xl overflow-hidden border border-slate-800 bg-[#06080E] shadow-2xl text-left my-6">
            <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 text-xs font-mono text-slate-400">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80"></span>
                <span className="ml-2 text-slate-300">bash — terminal</span>
              </div>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-amber-400 transition"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <pre className="p-4 text-xs font-mono text-amber-400/90 leading-relaxed overflow-x-auto">
              <code>{command}</code>
            </pre>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <a
              href="#demo"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-black font-semibold text-sm font-mono shadow-[0_0_25px_rgba(245,158,11,0.4)] transition transform hover:-translate-y-0.5 active:translate-y-0"
            >
              <Sparkles className="w-4 h-4 fill-black" />
              <span>Launch Live Twin Studio</span>
            </a>

            <a
              href="https://github.com/Amitosh07/Transformer-digital-twin"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-200 text-sm font-mono transition"
            >
              <GithubIcon className="w-4 h-4" />
              <span>Explore GitHub Repository</span>
              <ArrowUpRight className="w-4 h-4 text-slate-500" />
            </a>
          </div>
        </div>
      </div>
    </section>
  );
};
