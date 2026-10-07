import React from 'react';
import { HealthComponents } from '../types';
import { ShieldCheck, AlertTriangle, Flame, Zap, Gauge, Droplets, Bell, Cpu } from 'lucide-react';

interface HealthIndexDialProps {
  score: number;
  components: HealthComponents;
  reasonCodes: string[];
}

export const HealthIndexDial: React.FC<HealthIndexDialProps> = ({
  score,
  components,
  reasonCodes,
}) => {
  // Normalize score
  const safeScore = Math.max(0, Math.min(100, score));

  // Determine grade & color
  let statusText = 'HEALTHY';
  let strokeColor = '#10B981'; // emerald
  let glowColor = 'rgba(16, 185, 129, 0.3)';
  let bgBadge = 'bg-emerald-950/60 text-emerald-300 border-emerald-800/80';

  if (safeScore < 50) {
    statusText = 'CRITICAL';
    strokeColor = '#EF4444'; // crimson
    glowColor = 'rgba(239, 68, 68, 0.4)';
    bgBadge = 'bg-rose-950/70 text-rose-300 border-rose-800/80';
  } else if (safeScore < 70) {
    statusText = 'DEGRADED';
    strokeColor = '#F59E0B'; // amber
    glowColor = 'rgba(245, 158, 11, 0.35)';
    bgBadge = 'bg-amber-950/70 text-amber-300 border-amber-800/80';
  } else if (safeScore < 85) {
    statusText = 'WATCH';
    strokeColor = '#06B6D4'; // cyan
    glowColor = 'rgba(6, 182, 212, 0.3)';
    bgBadge = 'bg-cyan-950/70 text-cyan-300 border-cyan-800/80';
  }

  // Circular gauge calculations
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  // Use a 270 degree arc
  const arcLength = circumference * 0.75;
  const strokeDashoffset = arcLength - (arcLength * safeScore) / 100;

  return (
    <div className="bg-[#0A0E17] border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col justify-between">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300">
            6-Pillar Composite Health Index
          </span>
        </div>
        <span
          className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full border ${bgBadge}`}
        >
          {statusText}
        </span>
      </div>

      {/* Main Dial & Radial Score */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-6 my-4">
        <div className="relative w-44 h-44 flex items-center justify-center">
          <svg className="w-full h-full -rotate-135" viewBox="0 0 180 180">
            {/* Background track */}
            <circle
              cx="90"
              cy="90"
              r={radius}
              stroke="rgba(51, 65, 85, 0.3)"
              strokeWidth="12"
              fill="transparent"
              strokeDasharray={arcLength}
              strokeDashoffset="0"
              strokeLinecap="round"
            />
            {/* Value stroke */}
            <circle
              cx="90"
              cy="90"
              r={radius}
              stroke={strokeColor}
              strokeWidth="12"
              fill="transparent"
              strokeDasharray={arcLength}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              style={{
                transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.5s ease',
                filter: `drop-shadow(0 0 8px ${glowColor})`,
              }}
            />
          </svg>

          {/* Centered Numbers */}
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-4xl font-display font-extrabold text-slate-100 tracking-tight">
              {safeScore.toFixed(0)}
            </span>
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-widest">
              / 100 INDEX
            </span>
          </div>
        </div>

        {/* Breakdown of 6 Components */}
        <div className="flex-1 w-full space-y-2 text-xs font-mono">
          <div className="flex items-center justify-between text-slate-400">
            <span className="flex items-center gap-1.5">
              <Flame className="w-3.5 h-3.5 text-rose-400" /> Thermal State (25%)
            </span>
            <span className="font-semibold text-slate-200">{components.thermal}%</span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-rose-500 rounded-full transition-all duration-500"
              style={{ width: `${components.thermal}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-slate-400 pt-1">
            <span className="flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-400" /> Electrical Balance (20%)
            </span>
            <span className="font-semibold text-slate-200">{components.electrical}%</span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-amber-500 rounded-full transition-all duration-500"
              style={{ width: `${components.electrical}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-slate-400 pt-1">
            <span className="flex items-center gap-1.5">
              <Gauge className="w-3.5 h-3.5 text-cyan-400" /> Load Headroom (15%)
            </span>
            <span className="font-semibold text-slate-200">{components.loading}%</span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan-500 rounded-full transition-all duration-500"
              style={{ width: `${components.loading}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-slate-400 pt-1">
            <span className="flex items-center gap-1.5">
              <Droplets className="w-3.5 h-3.5 text-blue-400" /> Oil & Conservator (15%)
            </span>
            <span className="font-semibold text-slate-200">{components.oil}%</span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${components.oil}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-slate-400 pt-1">
            <span className="flex items-center gap-1.5">
              <Bell className="w-3.5 h-3.5 text-purple-400" /> Protection State (15%)
            </span>
            <span className="font-semibold text-slate-200">{components.alarm}%</span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-500 rounded-full transition-all duration-500"
              style={{ width: `${components.alarm}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-slate-400 pt-1">
            <span className="flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-emerald-400" /> Anomaly Margin (10%)
            </span>
            <span className="font-semibold text-slate-200">{components.anomaly}%</span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-500"
              style={{ width: `${components.anomaly}%` }}
            />
          </div>
        </div>
      </div>

      {/* Contributing Reason Codes */}
      {reasonCodes.length > 0 && (
        <div className="pt-3 border-t border-slate-800/80">
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 mb-2">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Contributing Reason Codes:
          </div>
          <div className="flex flex-wrap gap-1.5">
            {reasonCodes.map((code) => (
              <span
                key={code}
                className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-200"
              >
                #{code}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
