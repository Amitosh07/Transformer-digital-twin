import React from 'react';
import { Cpu } from 'lucide-react';
import { GithubIcon } from './GithubIcon';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-slate-800 bg-[#06080E] py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        {/* Brand & Attribution */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-500 flex items-center justify-center text-black font-bold">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <div className="font-display font-bold text-slate-200 text-sm">
              TRANSFORMER DIGITAL TWIN
            </div>
            <div className="text-[11px] font-mono text-slate-500">
              Repository: Amitosh07/Transformer-digital-twin
            </div>
          </div>
        </div>

        {/* Canonical Badge */}
        <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            Canonical Schema v1.0.0
          </span>
          <span className="text-slate-600">•</span>
          <span>Develop Branch Active</span>
        </div>

        {/* Links & Copyright */}
        <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
          <a
            href="https://github.com/Amitosh07/Transformer-digital-twin"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-amber-400 transition flex items-center gap-1"
          >
            <GithubIcon className="w-3.5 h-3.5" />
            <span>GitHub</span>
          </a>
          <a href="#demo" className="hover:text-amber-400 transition">
            Live Demo
          </a>
          <a href="#pipeline" className="hover:text-amber-400 transition">
            Pipeline Spec
          </a>
        </div>
      </div>

      <div className="max-w-7xl mx-auto mt-8 pt-6 border-t border-slate-900 text-center text-xs font-mono text-slate-500">
        Engineered for CPRI & PowerNext Smart Grid Innovation. Governed by IEEE C57.91 thermal loading standards.
      </div>
    </footer>
  );
};
