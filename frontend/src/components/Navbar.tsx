import React, { useState, useEffect } from 'react';
import { Cpu, Sun, Moon, Sparkles, Menu, X, ArrowUpRight } from 'lucide-react';
import { GithubIcon } from './GithubIcon';

interface NavbarProps {
  isDark: boolean;
  onToggleTheme: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ isDark, onToggleTheme }) => {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { label: 'Problem', href: '#problem' },
    { label: 'Solution', href: '#solution' },
    { label: 'Live Studio', href: '#demo', highlight: true },
    { label: 'Pipeline', href: '#pipeline' },
    { label: 'Architecture', href: '#architecture' },
    { label: 'Roadmap', href: '#roadmap' },
  ];

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-[#080B11]/90 backdrop-blur-md border-b border-slate-800 shadow-xl py-3'
          : 'bg-transparent py-5'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          {/* Logo & SCADA Status Badge */}
          <div className="flex items-center gap-4">
            <a href="#" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center shadow-[0_0_15px_rgba(245,158,11,0.4)] group-hover:scale-105 transition">
                <Cpu className="w-5 h-5 text-black font-bold" />
              </div>
              <div className="flex flex-col">
                <span className="font-display font-extrabold text-base tracking-tight text-slate-100 flex items-center gap-1.5">
                  TRANSFORMER <span className="text-amber-400">TWIN</span>
                </span>
                <span className="text-[10px] font-mono text-slate-400 tracking-wider">
                  CPRI / POWERNEXT TRACK
                </span>
              </div>
            </a>

            {/* Live Telemetry Heartbeat Pill */}
            <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
              <span className="text-emerald-400 font-semibold">SYNCHRONIZED</span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">SCHEMA V1.0.0</span>
            </div>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center gap-1 lg:gap-2">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono transition ${
                  link.highlight
                    ? 'text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 font-bold border border-amber-500/30'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                {link.label}
              </a>
            ))}
          </nav>

          {/* Actions & Utilities */}
          <div className="flex items-center gap-2.5">
            {/* Theme Toggle */}
            <button
              onClick={onToggleTheme}
              aria-label="Toggle Light/Dark Theme"
              className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-100 hover:border-slate-700 transition"
            >
              {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-cyan-400" />}
            </button>

            {/* GitHub Link */}
            <a
              href="https://github.com/Amitosh07/Transformer-digital-twin"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300 hover:text-white hover:border-slate-700 transition"
            >
              <GithubIcon className="w-4 h-4" />
              <span>GitHub</span>
            </a>

            {/* Launch Demo CTA */}
            <a
              href="#demo"
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-black font-semibold text-xs font-mono shadow-[0_0_20px_rgba(245,158,11,0.35)] transition transform active:scale-95"
            >
              <Sparkles className="w-3.5 h-3.5 fill-black" />
              <span>Launch Studio</span>
            </a>

            {/* Mobile Menu Toggle */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 md:hidden rounded-lg bg-slate-900 border border-slate-800 text-slate-300"
              aria-label="Toggle Mobile Menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden mt-3 p-4 bg-[#0B0F19] border border-slate-800 rounded-2xl shadow-2xl flex flex-col gap-2 font-mono text-xs">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition flex items-center justify-between"
              >
                <span>{link.label}</span>
                <ArrowUpRight className="w-3.5 h-3.5 text-slate-500" />
              </a>
            ))}
            <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
              <a
                href="https://github.com/Amitosh07/Transformer-digital-twin"
                target="_blank"
                rel="noopener noreferrer"
                className="text-slate-400 hover:text-white flex items-center gap-1.5 py-1"
              >
                <GithubIcon className="w-4 h-4" />
                <span>Repository</span>
              </a>
              <span className="text-[10px] text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800">
                CANONICAL V1.0.0
              </span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
