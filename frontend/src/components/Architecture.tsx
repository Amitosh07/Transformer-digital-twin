import React, { useState } from 'react';
import {
  Server,
  Database,
  Cpu,
  Layers,
  FileCode2,
  Code2,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';

export const Architecture: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'topology' | 'blueprint' | 'schema' | 'api'>('topology');

  const schemaTree = [
    {
      group: 'identity',
      fields: ['transformer_id: string', 'timestamp: datetime (ISO-8601)'],
      notes: 'Primary alignment key for multi-table SCADA joining',
    },
    {
      group: 'electrical',
      fields: [
        'phase_voltage_l1, l2, l3 (V)',
        'current_l1, l2, l3 (A)',
        'neutral_current (A)',
      ],
      notes: 'Explicitly excludes VL12, VL23, VL31 (unverified)',
    },
    {
      group: 'thermal',
      fields: [
        'oil_temperature (OTI)',
        'winding_temperature (WTI)',
        'ambient_temperature (ATI)',
      ],
      notes: 'Source units preserved until engineering units verified',
    },
    {
      group: 'oil_condition & protection',
      fields: [
        'oil_level (OLI)',
        'oil_temp_alarm (0/1)',
        'oil_temp_trip (0/1)',
        'magnetic_oil_gauge_alarm (0/1)',
      ],
      notes: 'Status booleans, strictly not converted to temperatures',
    },
    {
      group: 'derived_twin',
      fields: [
        'loading_percent (%)',
        'thermal_model_temperature',
        'thermal_residual (Obs - Model)',
        'anomaly_score (0.0–1.0)',
        'health_index (0–100)',
        'maintenance_priority (NORMAL/WATCH/PLAN/URGENT)',
        'reason_codes[]',
      ],
      notes: 'Produced by Twin/ML layer for backend & dashboard consumption',
    },
  ];

  const apiEndpoints = [
    {
      method: 'GET',
      path: '/health',
      desc: 'System health check and database connection state',
    },
    {
      method: 'GET',
      path: '/api/v1/transformers',
      desc: 'List all monitored transformer asset records and nameplates',
    },
    {
      method: 'GET',
      path: '/api/v1/transformers/{id}/latest',
      desc: 'Returns latest canonical telemetry and derived Digital Twin analytics',
    },
    {
      method: 'GET',
      path: '/api/v1/transformers/{id}/health',
      desc: 'Detailed 6-pillar Health Index and contributing reason codes',
    },
    {
      method: 'GET',
      path: '/api/v1/transformers/{id}/alerts',
      desc: 'Active alerts with severity, trigger, evidence, and actions',
    },
    {
      method: 'POST',
      path: '/api/v1/telemetry',
      desc: 'Ingests new canonical telemetry packet and triggers inference',
    },
    {
      method: 'POST',
      path: '/api/v1/simulate/replay',
      desc: 'Controls historical SCADA playback (1x to 50x replay speed)',
    },
  ];

  return (
    <section id="architecture" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/80">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono uppercase tracking-wider mb-3">
            <Server className="w-3.5 h-3.5 text-cyan-400" />
            Microservices & Data Contracts
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-display font-extrabold text-slate-100 tracking-tight">
            System Architecture & Data Schema
          </h2>
        </div>
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 p-1 rounded-xl text-xs font-mono">
          <button
            onClick={() => setActiveTab('topology')}
            className={`px-3 py-1.5 rounded-lg transition ${
              activeTab === 'topology' ? 'bg-amber-500 text-black font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Topology
          </button>
          <button
            onClick={() => setActiveTab('blueprint')}
            className={`px-3 py-1.5 rounded-lg transition ${
              activeTab === 'blueprint' ? 'bg-amber-500 text-black font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            CAD Blueprint
          </button>
          <button
            onClick={() => setActiveTab('schema')}
            className={`px-3 py-1.5 rounded-lg transition ${
              activeTab === 'schema' ? 'bg-amber-500 text-black font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Canonical Schema
          </button>
          <button
            onClick={() => setActiveTab('api')}
            className={`px-3 py-1.5 rounded-lg transition ${
              activeTab === 'api' ? 'bg-amber-500 text-black font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            FastAPI /v1/
          </button>
        </div>
      </div>

      {/* Tab 1: Topology View */}
      {activeTab === 'topology' && (
        <div className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 text-xs font-mono">
            {/* Step 1: Simulator & SCADA Ingestion */}
            <div className="bg-[#06080E] border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-amber-400 font-bold px-2 py-0.5 rounded bg-amber-950/60 border border-amber-800">
                  TIER 1: INGESTION
                </span>
                <h4 className="text-sm font-bold text-slate-100 mt-3 mb-2">SCADA & Simulator</h4>
                <p className="text-slate-400 text-[11px] leading-relaxed font-sans mb-3">
                  Historical replay engine (1x–50x) and MQTT / HTTP streaming supporting Kaggle 5-CSVs and upcoming CPRI live telemetry.
                </p>
              </div>
              <div className="pt-3 border-t border-slate-900 text-[10px] text-slate-500">
                Tech: Python, MQTT, Synthetic SCADA
              </div>
            </div>

            {/* Step 2: Canonical Adapter & Validation */}
            <div className="bg-[#06080E] border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-cyan-400 font-bold px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-800">
                  TIER 2: DATA CONTRACT
                </span>
                <h4 className="text-sm font-bold text-slate-100 mt-3 mb-2">Canonical Schema v1.0</h4>
                <p className="text-slate-400 text-[11px] leading-relaxed font-sans mb-3">
                  Pydantic data models enforcing strict types, range verification, missing-data preservation, and exclusion of VL12/23/31.
                </p>
              </div>
              <div className="pt-3 border-t border-slate-900 text-[10px] text-slate-500">
                Tech: Pydantic v2, Canonical Spec
              </div>
            </div>

            {/* Step 3: Intelligence & Digital Twin */}
            <div className="bg-[#06080E] border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-purple-400 font-bold px-2 py-0.5 rounded bg-purple-950/60 border border-purple-800">
                  TIER 3: TWIN INTELLIGENCE
                </span>
                <h4 className="text-sm font-bold text-slate-100 mt-3 mb-2">ML & Physics Models</h4>
                <p className="text-slate-400 text-[11px] leading-relaxed font-sans mb-3">
                  IEEE thermodynamic differential equations, multivariate isolation forest anomaly detector, and 6-pillar Health Index engine.
                </p>
              </div>
              <div className="pt-3 border-t border-slate-900 text-[10px] text-slate-500">
                Tech: Scikit-learn, NumPy, Physics ODE
              </div>
            </div>

            {/* Step 4: Backend & Presentation */}
            <div className="bg-[#06080E] border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-emerald-400 font-bold px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800">
                  TIER 4: SERVICE & UX
                </span>
                <h4 className="text-sm font-bold text-slate-100 mt-3 mb-2">FastAPI & Modern Web</h4>
                <p className="text-slate-400 text-[11px] leading-relaxed font-sans mb-3">
                  PostgreSQL with time-series indexing, RESTful /api/v1/ routes, and modern React TypeScript cyber-physical dashboard.
                </p>
              </div>
              <div className="pt-3 border-t border-slate-900 text-[10px] text-slate-500">
                Tech: FastAPI, PostgreSQL, React, Vite
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: CAD Blueprint View */}
      {activeTab === 'blueprint' && (
        <div className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-2xl overflow-hidden">
          <div className="relative rounded-xl overflow-hidden border border-slate-800">
            <img
              src="/assets/transformer_schematic.jpg"
              alt="Smart Grid Transformer Digital Twin Architectural CAD Schematic"
              className="w-full h-auto object-cover"
            />
          </div>
        </div>
      )}

      {/* Tab 3: Canonical Schema Tree */}
      {activeTab === 'schema' && (
        <div className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-6 shadow-2xl">
          <div className="text-xs font-mono text-slate-400 mb-4 pb-3 border-b border-slate-800 flex items-center justify-between">
            <span>Canonical Data Schema (dataschema.md v1.0.0)</span>
            <span className="text-emerald-400">STATUS: APPROVED CONTRACT</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 font-mono text-xs">
            {schemaTree.map((item, idx) => (
              <div key={idx} className="bg-[#06080E] border border-slate-800 p-4 rounded-xl">
                <div className="text-amber-400 font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <ChevronRight className="w-4 h-4 text-amber-500" />
                  {item.group}
                </div>
                <ul className="space-y-1 text-slate-200 text-[11px] mb-3">
                  {item.fields.map((f, i) => (
                    <li key={i} className="text-slate-300">• {f}</li>
                  ))}
                </ul>
                <div className="text-[10px] text-slate-500 pt-2 border-t border-slate-900">
                  {item.notes}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: FastAPI Endpoints */}
      {activeTab === 'api' && (
        <div className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-6 shadow-2xl font-mono text-xs">
          <div className="text-slate-400 mb-4 pb-3 border-b border-slate-800 flex items-center justify-between">
            <span>FastAPI Endpoints (backend_README.md v1.0.0)</span>
            <span className="text-cyan-400">PREFIX: /api/v1</span>
          </div>

          <div className="space-y-2.5">
            {apiEndpoints.map((ep, i) => (
              <div
                key={i}
                className="bg-[#06080E] border border-slate-800/80 p-3 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-2"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      ep.method === 'GET'
                        ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                        : 'bg-amber-950 text-amber-400 border border-amber-800'
                    }`}
                  >
                    {ep.method}
                  </span>
                  <span className="text-slate-200 font-semibold">{ep.path}</span>
                </div>
                <span className="text-slate-400 text-[11px] font-sans sm:text-right">{ep.desc}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
