import React, { useState } from 'react';
import { DigitalTwinAnalytics, MaintenancePriority } from '../types';
import { Wrench, CheckCircle2, AlertOctagon, Clock, Copy, Check, FileJson } from 'lucide-react';

interface PrescriptiveActionCardProps {
  analytics: DigitalTwinAnalytics;
}

export const PrescriptiveActionCard: React.FC<PrescriptiveActionCardProps> = ({ analytics }) => {
  const [copied, setCopied] = useState(false);
  const [showJson, setShowJson] = useState(false);

  const priorityConfigs: Record<
    MaintenancePriority,
    { label: string; badgeClass: string; borderClass: string; icon: React.ReactNode }
  > = {
    NORMAL: {
      label: 'PRIORITY: NORMAL (SCHEDULED)',
      badgeClass: 'bg-emerald-950/70 text-emerald-300 border-emerald-800',
      borderClass: 'border-slate-800',
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
    },
    WATCH: {
      label: 'PRIORITY: WATCH (ELEVATED)',
      badgeClass: 'bg-cyan-950/70 text-cyan-300 border-cyan-800',
      borderClass: 'border-cyan-800/40',
      icon: <Clock className="w-4 h-4 text-cyan-400" />,
    },
    PLAN: {
      label: 'PRIORITY: PLAN (INTERVENTION NEEDED)',
      badgeClass: 'bg-amber-950/70 text-amber-300 border-amber-800',
      borderClass: 'border-amber-800/50',
      icon: <Clock className="w-4 h-4 text-amber-400" />,
    },
    URGENT: {
      label: 'PRIORITY: URGENT (DISPATCH CREW)',
      badgeClass: 'bg-rose-950/80 text-rose-300 border-rose-800 animate-pulse',
      borderClass: 'border-rose-800/60 shadow-[0_0_20px_rgba(239,68,68,0.2)]',
      icon: <AlertOctagon className="w-4 h-4 text-rose-400" />,
    },
  };

  const currentCfg = priorityConfigs[analytics.maintenance_priority] || priorityConfigs.NORMAL;

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(analytics, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`bg-[#0A0E17] border ${currentCfg.borderClass} rounded-xl p-5 shadow-xl flex flex-col justify-between transition-all duration-300`}
    >
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Wrench className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300">
            Prescriptive Maintenance Dispatch Engine
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowJson(!showJson)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-mono text-slate-300 transition"
          >
            <FileJson className="w-3.5 h-3.5 text-cyan-400" />
            {showJson ? 'Hide Contract JSON' : 'Inspect Contract JSON'}
          </button>

          <span
            className={`flex items-center gap-1.5 text-xs font-mono font-bold px-2.5 py-1 rounded-full border ${currentCfg.badgeClass}`}
          >
            {currentCfg.icon}
            {currentCfg.label}
          </span>
        </div>
      </div>

      {showJson ? (
        <div className="my-3 relative">
          <div className="flex items-center justify-between bg-slate-900 px-3 py-1.5 rounded-t border border-slate-800 text-[11px] font-mono text-slate-400">
            <span>Canonical Output payload (mlcontract.md v1.0.0)</span>
            <button
              onClick={handleCopyJson}
              className="flex items-center gap-1 text-slate-300 hover:text-amber-400"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre className="max-h-52 overflow-y-auto bg-[#06080E] border-x border-b border-slate-800 p-3 text-[11px] font-mono text-slate-300 rounded-b">
            {JSON.stringify(analytics, null, 2)}
          </pre>
        </div>
      ) : (
        <div className="my-3 space-y-3">
          {/* Action Callout */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5">
            <div className="text-[11px] font-mono uppercase text-slate-400 tracking-wider mb-1">
              Automated Operator Recommendation
            </div>
            <p className="text-sm text-slate-100 font-medium leading-relaxed">
              {analytics.maintenance_recommendation}
            </p>
          </div>

          {/* Fault classification & Confidence */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
            <div className="bg-slate-900/50 border border-slate-800/80 p-2.5 rounded-lg flex flex-col justify-between">
              <span className="text-slate-400 text-[10px] uppercase">Predicted Fault State</span>
              <span className="font-semibold text-amber-400 text-sm mt-0.5">
                {analytics.predicted_fault || 'NOMINAL_OPERATION'}
              </span>
            </div>

            <div className="bg-slate-900/50 border border-slate-800/80 p-2.5 rounded-lg flex flex-col justify-between">
              <span className="text-slate-400 text-[10px] uppercase">Inference Confidence</span>
              <div className="flex items-center justify-between mt-0.5">
                <span className="font-semibold text-emerald-400 text-sm">
                  {analytics.prediction_confidence !== null && analytics.prediction_confidence !== undefined
                    ? `${(analytics.prediction_confidence * 100).toFixed(0)}%`
                    : 'N/A (UNRELEASED)'}
                </span>
                <span className="text-[10px] text-slate-400">Schema v{analytics.schema_version}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer Info */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-slate-800/80 text-xs font-mono text-slate-400">
        <div className="flex items-center gap-2">
          <span>Asset: <strong className="text-slate-200">{analytics.transformer_id}</strong></span>
          <span className="text-slate-600">•</span>
          <span>
            Fault Risk:{' '}
            {analytics.fault_risk !== null && analytics.fault_risk !== undefined ? (
              <strong className={analytics.fault_risk > 0.5 ? 'text-rose-400' : 'text-emerald-400'}>
                {(analytics.fault_risk * 100).toFixed(0)}%
              </strong>
            ) : (
              <strong className="text-slate-400">UNAVAILABLE (INSUFFICIENT_VALIDATION)</strong>
            )}
          </span>
        </div>

        <button
          onClick={handleCopyJson}
          className="flex items-center gap-1.5 text-slate-400 hover:text-amber-400 transition"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? 'Copied to Clipboard' : 'Copy Dispatch JSON'}</span>
        </button>
      </div>
    </div>
  );
};
