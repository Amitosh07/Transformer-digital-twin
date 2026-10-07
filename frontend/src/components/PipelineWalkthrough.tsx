import React, { useState } from 'react';
import {
  Database,
  ArrowRight,
  Filter,
  CheckCircle2,
  Cpu,
  Layers,
  Send,
  Terminal,
} from 'lucide-react';

interface PipelineStage {
  id: number;
  title: string;
  badge: string;
  icon: React.ReactNode;
  summary: string;
  details: string[];
  codeSnippet: string;
}

export const PipelineWalkthrough: React.FC = () => {
  const [activeStage, setActiveStage] = useState(0);

  const stages: PipelineStage[] = [
    {
      id: 1,
      title: 'Raw SCADA Ingestion',
      badge: 'INGESTION LAYER',
      icon: <Database className="w-5 h-5 text-amber-400" />,
      summary:
        'Supports both baseline Kaggle 5-file datasets (CurrentVoltage, Overview, Power, PowerFactor, TotalPower) and future live CPRI/PowerNext utility streams.',
      details: [
        'Time-indexed alignment using primary DeviceTimeStamp key',
        'Handles high-frequency SCADA feeds without assuming uniform intervals',
        'Raw vendor column names quarantined strictly within ingestion perimeter',
      ],
      codeSnippet: `# Raw Data Boundary Quarantine
raw_feed = load_scada_streams([
    "CurrentVoltage.csv", "Overview.csv", 
    "Power.csv", "PowerFactor.csv", "TotalPower.csv"
])
aligned_feed = join_on_timestamp(raw_feed, key="DeviceTimeStamp")`,
    },
    {
      id: 2,
      title: 'Modular Source Adapters',
      badge: 'TRANSLATION LAYER',
      icon: <Filter className="w-5 h-5 text-cyan-400" />,
      summary:
        'Converts diverse utility/vendor schemas into the unified Canonical Schema v1.0.0 without modifying downstream models or UI.',
      details: [
        'Translates VL1 -> phase_voltage_l1, IL1 -> current_l1, OTI -> oil_temperature',
        'Explicitly excludes unverified line-to-line voltages (VL12, VL23, VL31)',
        'Extensible adapter pattern allows adding new CPRI utility formats in minutes',
      ],
      codeSnippet: `class KaggleSourceAdapter(BaseAdapter):
    def transform(self, raw: dict) -> CanonicalTransformerRecord:
        return CanonicalTransformerRecord(
            transformer_id=self.asset_id,
            timestamp=parse_iso(raw["DeviceTimeStamp"]),
            current_l1=raw["IL1"],
            oil_temperature=raw["OTI"],
            # VL12, VL23, VL31 explicitly excluded
        )`,
    },
    {
      id: 3,
      title: 'Canonical Validation & Hygiene',
      badge: 'DATA INTEGRITY',
      icon: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
      summary:
        'Guarantees data quality by strictly prohibiting silent zero-filling and flagging missing sensor values properly.',
      details: [
        'Missing data is never converted to zero unless zero is physically valid',
        'Distinguishes between missing telemetry and true zero current flow',
        'Validates physical engineering bounds (e.g. ambient -10°C to +60°C)',
      ],
      codeSnippet: `# Non-Negotiable Data Hygiene Rule
def validate_telemetry(record: CanonicalRecord) -> ValidatedRecord:
    for field, val in record.items():
        if val is None and field in CRITICAL_FIELDS:
            raise InsufficientDataException(f"Missing critical {field}")
        # Never convert missing to zero!
    return record`,
    },
    {
      id: 4,
      title: 'Feature Engineering Pipeline',
      badge: 'FEATURE STORE',
      icon: <Layers className="w-5 h-5 text-purple-400" />,
      summary:
        'Derives physics-aligned electrical and thermal features with zero future-data leakage.',
      details: [
        'Calculates 3-phase current imbalance % and neutral zero-sequence magnitude',
        'Computes rolling thermal slope, rate of change, and load utilization %',
        'Enforces strict temporal order (Past -> Train, Middle -> Val, Latest -> Test)',
      ],
      codeSnippet: `def engineer_features(rec: CanonicalRecord, history: Window):
    return {
        "current_imbalance_pct": calc_imbalance(rec.il1, rec.il2, rec.il3),
        "neutral_magnitude": rec.inut,
        "load_utilization": rec.apparent_power / rec.rated_power_kva,
        "oil_temp_rate": calc_slope(history.oil_temp),
        "ambient_delta": rec.oil_temperature - rec.ambient_temperature
    }`,
    },
    {
      id: 5,
      title: 'Digital Twin & ML Engine',
      badge: 'INTELLIGENCE CORE',
      icon: <Cpu className="w-5 h-5 text-amber-400" />,
      summary:
        'Executes the dual intelligence layer: IEEE thermal behavioral modeling and multivariate anomaly detection.',
      details: [
        'Simulates expected thermal state and extracts Thermal Residual (Observed - Model)',
        'Computes continuous Anomaly Score (0.0 to 1.0) and proxy fault risk',
        'Aggregates the transparent 6-pillar Health Index (0 to 100)',
      ],
      codeSnippet: `# Digital Twin Execution
model_temp = ieee_thermal_model(load_ratio, ambient_temp)
residual = observed_temp - model_temp
anomaly_score = isolation_forest.score(features)
health_index = compute_health_index(
    thermal, electrical, loading, oil, alarm, anomaly
)`,
    },
    {
      id: 6,
      title: 'Prescriptive Action & API Delivery',
      badge: 'SERVICE LAYER',
      icon: <Send className="w-5 h-5 text-cyan-400" />,
      summary:
        'Translates intelligence into prioritized maintenance actions and serves them over versioned FastAPI /api/v1/ endpoints.',
      details: [
        'Assigns priority tiers: NORMAL, WATCH, PLAN, URGENT',
        'Generates machine-readable reason codes (e.g. HIGH_OIL_TEMP, RAPID_TEMP_RISE)',
        'Exposes RESTful endpoints for real-time dashboards and SCADA integration',
      ],
      codeSnippet: `@router.get("/transformers/{id}/latest")
async def get_latest_twin(id: str) -> TwinResponse:
    # Stable analytical contract matching mlcontract.md v1.0.0
    return TwinResponse(
        transformer_id=id,
        health_index=68.4,
        maintenance_priority="PLAN",
        reason_codes=["HIGH_OIL_TEMP", "RAPID_TEMP_RISE"]
    )`,
    },
  ];

  return (
    <section id="pipeline" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
      {/* Header */}
      <div className="text-center max-w-3xl mx-auto mb-12">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono uppercase tracking-wider mb-4">
          <Terminal className="w-3.5 h-3.5 text-cyan-400" />
          Dataschema.md Section 22 Boundary
        </div>
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-display font-extrabold text-slate-100 tracking-tight">
          The 6-Stage Canonical Pipeline
        </h2>
        <p className="mt-4 text-base sm:text-lg text-slate-400 leading-relaxed font-sans">
          A zero-leakage, contract-driven architecture guaranteeing that raw SCADA mess never enters machine learning algorithms or dashboard interfaces.
        </p>
      </div>

      {/* Interactive Horizontal / Vertical Stage Stepper */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mb-8">
        {stages.map((stage, idx) => (
          <button
            key={stage.id}
            onClick={() => setActiveStage(idx)}
            className={`p-3 rounded-xl border text-left transition flex flex-col justify-between ${
              activeStage === idx
                ? 'bg-amber-500/15 border-amber-500 shadow-lg text-amber-300 font-bold'
                : 'bg-[#0B0F19] border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between w-full mb-2">
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/40 border border-slate-800">
                0{stage.id}
              </span>
              {stage.icon}
            </div>
            <div className="text-xs font-semibold text-slate-200 line-clamp-1">{stage.title}</div>
          </button>
        ))}
      </div>

      {/* Stage Detail Showcase Panel */}
      <div className="bg-[#0A0E17] border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left Details */}
          <div className="lg:col-span-6 space-y-5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-400">
                {stages[activeStage].badge}
              </span>
              <span className="text-xs font-mono text-slate-500">Stage {stages[activeStage].id} of 6</span>
            </div>

            <h3 className="text-2xl font-display font-bold text-slate-100">
              {stages[activeStage].title}
            </h3>

            <p className="text-sm sm:text-base text-slate-300 font-sans leading-relaxed">
              {stages[activeStage].summary}
            </p>

            <ul className="space-y-2 text-xs font-mono text-slate-400 pt-1">
              {stages[activeStage].details.map((item, i) => (
                <li key={i} className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>

            <div className="pt-2 flex items-center gap-3">
              <button
                onClick={() => setActiveStage((prev) => (prev > 0 ? prev - 1 : stages.length - 1))}
                className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300 hover:text-white"
              >
                ← Previous Stage
              </button>
              <button
                onClick={() => setActiveStage((prev) => (prev < stages.length - 1 ? prev + 1 : 0))}
                className="px-3 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/40 text-xs font-mono text-amber-300 hover:bg-amber-500/30 font-semibold"
              >
                Next Stage →
              </button>
            </div>
          </div>

          {/* Right Code Block */}
          <div className="lg:col-span-6">
            <div className="rounded-xl overflow-hidden border border-slate-800 bg-[#06080E] shadow-xl">
              <div className="flex items-center justify-between px-4 py-2 bg-slate-900/80 border-b border-slate-800 text-[11px] font-mono text-slate-400">
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-500/80"></span>
                  <span className="w-2 h-2 rounded-full bg-yellow-500/80"></span>
                  <span className="w-2 h-2 rounded-full bg-green-500/80"></span>
                  <span className="ml-2 text-slate-300">stage_{stages[activeStage].id}_contract.py</span>
                </span>
                <span>PYTHON 3.11</span>
              </div>
              <pre className="p-4 text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
                <code>{stages[activeStage].codeSnippet}</code>
              </pre>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
