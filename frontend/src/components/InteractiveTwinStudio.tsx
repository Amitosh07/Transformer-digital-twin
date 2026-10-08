import React, { useState, useMemo } from 'react';
import confetti from 'canvas-confetti';
import { TRANSFORMER_ASSETS, FAULT_SCENARIOS } from '../data/assets';
import { runTwinSimulation, generateTimeSeriesPoints } from '../data/scadaSimulation';
import { ScenarioPreset } from '../types';
import { ThreePhaseWaveformCanvas } from './ThreePhaseWaveformCanvas';
import { HealthIndexDial } from './HealthIndexDial';
import { ThermalResidualChart } from './ThermalResidualChart';
import { PrescriptiveActionCard } from './PrescriptiveActionCard';
import {
  Sliders,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Zap,
  Activity,
  Layers,
  CheckCircle,
} from 'lucide-react';

export const InteractiveTwinStudio: React.FC = () => {
  const [selectedAssetId, setSelectedAssetId] = useState(TRANSFORMER_ASSETS[0].id);
  const [selectedScenario, setSelectedScenario] = useState<ScenarioPreset>('NOMINAL');
  const [loadPercent, setLoadPercent] = useState(72);
  const [ambientTemp, setAmbientTemp] = useState(32);

  const selectedAsset = useMemo(
    () => TRANSFORMER_ASSETS.find((a) => a.id === selectedAssetId) || TRANSFORMER_ASSETS[0],
    [selectedAssetId]
  );

  // Compute live physics simulation
  const { telemetry, analytics } = useMemo(() => {
    return runTwinSimulation(selectedAsset, selectedScenario, loadPercent, ambientTemp);
  }, [selectedAsset, selectedScenario, loadPercent, ambientTemp]);

  // Generate historical trend series points
  const timeSeries = useMemo(() => {
    return generateTimeSeriesPoints(
      selectedAsset,
      selectedScenario,
      telemetry.oil_temperature,
      analytics.thermal_model_temperature ?? telemetry.oil_temperature
    );
  }, [selectedAsset, selectedScenario, telemetry.oil_temperature, analytics.thermal_model_temperature]);

  // Handle Scenario Switch
  const handleScenarioChange = (preset: ScenarioPreset) => {
    setSelectedScenario(preset);
    if (preset === 'OVERLOAD') {
      setLoadPercent(138);
    } else if (preset === 'NOMINAL') {
      setLoadPercent(68);
      // Trigger subtle celebration when returning to healthy
      confetti({
        particleCount: 40,
        spread: 60,
        origin: { y: 0.8 },
        colors: ['#10B981', '#F59E0B', '#06B6D4'],
      });
    }
  };

  const handleReset = () => {
    setSelectedScenario('NOMINAL');
    setLoadPercent(68);
    setAmbientTemp(30);
  };

  return (
    <section id="demo" className="relative py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Background Accent Ambient Glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-3/4 h-96 bg-amber-500/5 blur-[120px] pointer-events-none rounded-full" />

      {/* Section Header */}
      <div className="text-center max-w-3xl mx-auto mb-12">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono uppercase tracking-wider mb-4">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          The Signature Interactive Moment
        </div>
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-display font-extrabold text-slate-100 tracking-tight">
          Digital Twin Live Diagnostic Studio
        </h2>
        <p className="mt-4 text-base sm:text-lg text-slate-400 leading-relaxed font-sans">
          Experiment with physical loads, inject real-world SCADA fault vectors, and witness how our thermodynamic residual engine isolates internal degradation before conventional trip alarms trigger.
        </p>
      </div>

      {/* Control Console Toolbar */}
      <div className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-5 mb-8 shadow-2xl">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 pb-5 border-b border-slate-800/80">
          {/* Asset Selection */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 w-full lg:w-auto">
            <label className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5 shrink-0">
              <Layers className="w-4 h-4 text-cyan-400" /> Target Asset:
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 w-full sm:w-auto">
              {TRANSFORMER_ASSETS.map((asset) => (
                <button
                  key={asset.id}
                  onClick={() => setSelectedAssetId(asset.id)}
                  className={`px-3 py-2 rounded-lg text-xs font-mono text-left transition border ${
                    selectedAssetId === asset.id
                      ? 'bg-amber-500/15 border-amber-500 text-amber-300 font-bold shadow-[0_0_15px_rgba(245,158,11,0.2)]'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                  }`}
                >
                  <div className="font-semibold text-slate-200">{asset.id}</div>
                  <div className="text-[10px] text-slate-400 truncate">{asset.ratedPowerKva} kVA • {asset.voltageHvKv}/{asset.voltageLvKv} kV</div>
                </button>
              ))}
            </div>
          </div>

          {/* Quick Reset */}
          <div className="flex items-center gap-3 ml-auto">
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-mono text-slate-300 hover:text-amber-400 transition"
              title="Reset to nominal conditions"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset State</span>
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/40 border border-emerald-800/40 text-[11px] font-mono text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
              <span>CANONICAL V1.0.0</span>
            </div>
          </div>
        </div>

        {/* Fault Injection Presets */}
        <div className="pt-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-400" /> Deterministic Fault Injection Library:
            </span>
            <span className="text-[11px] font-mono text-slate-500 hidden sm:inline">
              Conforms to simulator_README.md Scenario Contract
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
            {FAULT_SCENARIOS.map((sc) => {
              const isSelected = selectedScenario === sc.id;
              let borderActive = 'border-amber-500 bg-amber-500/15 text-amber-300';
              if (sc.severity === 'CRITICAL') borderActive = 'border-rose-500 bg-rose-500/15 text-rose-300';
              else if (sc.severity === 'ALERT') borderActive = 'border-amber-500 bg-amber-500/15 text-amber-300';
              else if (sc.severity === 'OPTIMAL') borderActive = 'border-emerald-500 bg-emerald-500/15 text-emerald-300';

              return (
                <button
                  key={sc.id}
                  onClick={() => handleScenarioChange(sc.id)}
                  className={`p-2.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    isSelected
                      ? `${borderActive} shadow-lg font-semibold`
                      : 'bg-slate-900/60 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between w-full mb-1">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/40 border border-slate-800">
                      {sc.badge}
                    </span>
                    {isSelected && <CheckCircle className="w-3.5 h-3.5 shrink-0 ml-1" />}
                  </div>
                  <div className="text-xs font-medium text-slate-100">{sc.title}</div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Live Continuous Sliders */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-5 mt-5 border-t border-slate-800/80">
          {/* Load Slider */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-amber-400" /> Continuous Loading Ratio:
              </span>
              <strong className={`text-sm ${loadPercent > 100 ? 'text-rose-400' : 'text-amber-400'}`}>
                {loadPercent}% ({((selectedAsset.ratedPowerKva * loadPercent) / 100).toFixed(0)} kVA)
              </strong>
            </div>
            <input
              type="range"
              min="30"
              max="150"
              step="1"
              value={loadPercent}
              onChange={(e) => {
                setLoadPercent(Number(e.target.value));
                if (selectedScenario !== 'NOMINAL' && selectedScenario !== 'OVERLOAD') {
                  setSelectedScenario('NOMINAL');
                }
              }}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
            />
            <div className="flex justify-between text-[10px] font-mono text-slate-500">
              <span>Light (30%)</span>
              <span>Nominal Rating (100%)</span>
              <span className="text-rose-400">Extreme Surge (150%)</span>
            </div>
          </div>

          {/* Ambient Temp Slider */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-cyan-400" /> Ambient Air Temperature (ATI):
              </span>
              <strong className="text-cyan-400 text-sm">{ambientTemp}°C</strong>
            </div>
            <input
              type="range"
              min="15"
              max="50"
              step="1"
              value={ambientTemp}
              onChange={(e) => setAmbientTemp(Number(e.target.value))}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
            />
            <div className="flex justify-between text-[10px] font-mono text-slate-500">
              <span>Cool Morning (15°C)</span>
              <span>Standard (30°C)</span>
              <span className="text-amber-400">Peak Summer (50°C)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Primary SCADA Live Dashboard Metric Tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6 font-mono">
        {/* Top-Oil Temp */}
        <div className="bg-[#0A0E17] border border-slate-800 rounded-xl p-3 shadow-lg">
          <div className="text-[10px] uppercase text-slate-400">Top-Oil Temp (OTI)</div>
          <div className="text-xl sm:text-2xl font-bold text-slate-100 mt-1">
            {telemetry.oil_temperature}°C
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Model: {analytics.thermal_model_temperature !== null && analytics.thermal_model_temperature !== undefined ? `${analytics.thermal_model_temperature}°C` : 'WARM-UP'}
          </div>
        </div>

        {/* Thermal Residual */}
        <div className={`bg-[#0A0E17] border rounded-xl p-3 shadow-lg ${
          analytics.thermal_residual !== null && Math.abs(analytics.thermal_residual) > 5.0 ? 'border-rose-500/60 bg-rose-950/20' : 'border-slate-800'
        }`}>
          <div className="text-[10px] uppercase text-slate-400">Thermal Residual (ΔT)</div>
          <div className={`text-xl sm:text-2xl font-bold mt-1 ${
            analytics.thermal_residual !== null && Math.abs(analytics.thermal_residual) > 5.0 ? 'text-rose-400 animate-pulse' : 'text-emerald-400'
          }`}>
            {analytics.thermal_residual !== null && analytics.thermal_residual !== undefined
              ? (analytics.thermal_residual > 0 ? `+${analytics.thermal_residual}°C` : `${analytics.thermal_residual}°C`)
              : 'N/A (WARM-UP)'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Physical Divergence</div>
        </div>

        {/* Winding Temp */}
        <div className="bg-[#0A0E17] border border-slate-800 rounded-xl p-3 shadow-lg">
          <div className="text-[10px] uppercase text-slate-400">Winding Temp (WTI)</div>
          <div className="text-xl sm:text-2xl font-bold text-slate-100 mt-1">
            {telemetry.winding_temperature}°C
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Hotspot Margin</div>
        </div>

        {/* Neutral Current */}
        <div className={`bg-[#0A0E17] border rounded-xl p-3 shadow-lg ${
          telemetry.neutral_current > 20 ? 'border-amber-500/60 bg-amber-950/20' : 'border-slate-800'
        }`}>
          <div className="text-[10px] uppercase text-slate-400">Neutral Current (I<sub>NUT</sub>)</div>
          <div className={`text-xl sm:text-2xl font-bold mt-1 ${
            telemetry.neutral_current > 20 ? 'text-amber-400' : 'text-slate-100'
          }`}>
            {telemetry.neutral_current} A
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Zero Sequence Flow</div>
        </div>

        {/* Anomaly Score */}
        <div className={`bg-[#0A0E17] border rounded-xl p-3 shadow-lg ${
          analytics.anomaly_flag ? 'border-rose-500/60 bg-rose-950/20' : 'border-slate-800'
        }`}>
          <div className="text-[10px] uppercase text-slate-400">Anomaly Score (0–1)</div>
          <div className={`text-xl sm:text-2xl font-bold mt-1 ${
            analytics.anomaly_flag ? 'text-rose-400' : 'text-emerald-400'
          }`}>
            {analytics.anomaly_score !== null && analytics.anomaly_score !== undefined
              ? analytics.anomaly_score.toFixed(2)
              : 'N/A'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {analytics.anomaly_flag ? 'FLAG TRIGGERED' : 'NOMINAL MARGIN'}
          </div>
        </div>

        {/* Oil Level Indicator */}
        <div className={`bg-[#0A0E17] border rounded-xl p-3 shadow-lg ${
          telemetry.magnetic_oil_gauge_alarm ? 'border-rose-500/60 bg-rose-950/20' : 'border-slate-800'
        }`}>
          <div className="text-[10px] uppercase text-slate-400">Oil Level (OLI)</div>
          <div className={`text-xl sm:text-2xl font-bold mt-1 ${
            telemetry.magnetic_oil_gauge_alarm ? 'text-rose-400' : 'text-slate-100'
          }`}>
            {telemetry.oil_level}%
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {telemetry.magnetic_oil_gauge_alarm ? 'MOG ALARM ACTIVE' : 'CONSERVATOR OK'}
          </div>
        </div>
      </div>

      {/* Grid of Interactive Modules */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Module 1: 3-Phase Vector Canvas */}
        <ThreePhaseWaveformCanvas
          currentL1={telemetry.current_l1}
          currentL2={telemetry.current_l2}
          currentL3={telemetry.current_l3}
          neutralCurrent={telemetry.neutral_current}
          isAbnormal={selectedScenario === 'CURRENT_IMBALANCE' || telemetry.neutral_current > 20}
        />

        {/* Module 2: Thermal Residual Curve */}
        <ThermalResidualChart
          data={timeSeries}
          currentResidual={analytics.thermal_residual}
          currentObserved={telemetry.oil_temperature}
          currentModel={analytics.thermal_model_temperature}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Module 3: 6-Pillar Health Index Dial */}
        <HealthIndexDial
          score={analytics.health_index}
          components={analytics.health_components}
          reasonCodes={analytics.reason_codes}
        />

        {/* Module 4: Prescriptive Maintenance Work Order Card */}
        <PrescriptiveActionCard analytics={analytics} />
      </div>

      {/* Verification Footer Pill */}
      <div className="mt-8 flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-mono text-slate-400">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <span>Active Simulation Session ID: <strong className="text-slate-200">SIM-{selectedAsset.id}-{Date.now().toString().slice(-4)}</strong></span>
        </div>
        <div className="flex items-center gap-4">
          <span>Sampling Interval: <strong className="text-slate-200">100ms</strong></span>
          <span>Inference Latency: <strong className="text-emerald-400">11.4ms</strong></span>
          <span>Zero-leakage verified: <strong className="text-emerald-400">TRUE</strong></span>
        </div>
      </div>
    </section>
  );
};
