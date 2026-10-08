import React, { useState } from 'react';
import { Thermometer, Info, AlertCircle } from 'lucide-react';

interface TimeSeriesPoint {
  time: string;
  observedTemp: number;
  modelTemp: number;
  residual: number;
  load: number;
  health: number;
}

interface ThermalResidualChartProps {
  data: TimeSeriesPoint[];
  currentResidual: number;
  currentObserved: number;
  currentModel: number;
}

export const ThermalResidualChart: React.FC<ThermalResidualChartProps> = ({
  data,
  currentResidual,
  currentObserved,
  currentModel,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (!data || data.length === 0) return null;

  // Compute SVG plotting bounds
  const minTemp = Math.min(...data.map((d) => Math.min(d.observedTemp, d.modelTemp))) - 5;
  const maxTemp = Math.max(...data.map((d) => Math.max(d.observedTemp, d.modelTemp))) + 8;
  const range = Math.max(20, maxTemp - minTemp);

  const width = 600;
  const height = 200;
  const paddingX = 40;
  const paddingY = 25;

  const chartW = width - paddingX * 2;
  const chartH = height - paddingY * 2;

  // Convert (index, temp) to (x, y)
  const getX = (i: number) => paddingX + (i / (data.length - 1)) * chartW;
  const getY = (t: number) => paddingY + chartH - ((t - minTemp) / range) * chartH;

  // Build SVG path strings
  const observedPath = data.reduce(
    (acc, d, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(d.observedTemp)}`,
    ''
  );

  const modelPath = data.reduce(
    (acc, d, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(d.modelTemp)}`,
    ''
  );

  // Build shaded polygon between model and observed
  const reverseModelPoints = [...data].reverse().map((d, idx) => {
    const originalIdx = data.length - 1 - idx;
    return `L ${getX(originalIdx)} ${getY(d.modelTemp)}`;
  }).join(' ');

  const residualAreaPath = `${observedPath} ${reverseModelPoints} Z`;

  const isDiverging = Math.abs(currentResidual) > 5.0;

  return (
    <div className="bg-[#0A0E17] border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col justify-between">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Thermometer className="w-4 h-4 text-rose-400" />
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300">
            Digital Twin Thermal Residual (Observed vs Thermodynamic Model)
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-700 text-xs font-mono">
            <span className="text-slate-400">Δ Residual:</span>
            <span
              className={`font-bold ${
                isDiverging ? 'text-rose-400 animate-pulse' : 'text-emerald-400'
              }`}
            >
              {currentResidual > 0 ? `+${currentResidual}°C` : `${currentResidual}°C`}
            </span>
          </div>

          {isDiverging && (
            <span className="flex items-center gap-1 text-[11px] font-mono text-rose-400 bg-rose-950/60 border border-rose-800/60 px-2 py-0.5 rounded-full">
              <AlertCircle className="w-3 h-3 text-rose-400" />
              THERMAL DRIFT
            </span>
          )}
        </div>
      </div>

      {/* Primary SVG Chart */}
      <div className="relative w-full my-3">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto overflow-visible select-none"
          onMouseLeave={() => setHoveredIndex(null)}
        >
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const y = paddingY + chartH * ratio;
            const tempVal = maxTemp - ratio * range;
            return (
              <g key={ratio}>
                <line
                  x1={paddingX}
                  y1={y}
                  x2={width - paddingX}
                  y2={y}
                  stroke="rgba(51, 65, 85, 0.25)"
                  strokeDasharray="4 4"
                />
                <text
                  x={paddingX - 8}
                  y={y + 3}
                  textAnchor="end"
                  fill="#64748B"
                  fontSize="9"
                  fontFamily="JetBrains Mono"
                >
                  {tempVal.toFixed(0)}°C
                </text>
              </g>
            );
          })}

          {/* Shaded Area for Thermal Residual */}
          <path
            d={residualAreaPath}
            fill={isDiverging ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.12)'}
            stroke="none"
          />

          {/* Expected Model Path (Cyan dashed line) */}
          <path
            d={modelPath}
            fill="none"
            stroke="#06B6D4"
            strokeWidth="2"
            strokeDasharray="4 3"
            style={{ filter: 'drop-shadow(0 0 4px rgba(6, 182, 212, 0.4))' }}
          />

          {/* Observed Telemetry Path (Amber/Crimson solid line) */}
          <path
            d={observedPath}
            fill="none"
            stroke={isDiverging ? '#EF4444' : '#F59E0B'}
            strokeWidth="2.5"
            style={{
              filter: `drop-shadow(0 0 6px ${
                isDiverging ? 'rgba(239, 68, 68, 0.6)' : 'rgba(245, 158, 11, 0.4)'
              })`,
            }}
          />

          {/* Interactive Hover Vertical Line and Points */}
          {data.map((d, i) => {
            const cx = getX(i);
            const cyObs = getY(d.observedTemp);
            const cyMod = getY(d.modelTemp);
            const isHovered = hoveredIndex === i;

            return (
              <g key={i} onMouseEnter={() => setHoveredIndex(i)} className="cursor-pointer">
                {/* Invisible hover trigger area */}
                <rect
                  x={cx - 10}
                  y={paddingY}
                  width="20"
                  height={chartH}
                  fill="transparent"
                />

                {isHovered && (
                  <>
                    <line
                      x1={cx}
                      y1={paddingY}
                      x2={cx}
                      y2={paddingY + chartH}
                      stroke="rgba(255, 255, 255, 0.4)"
                      strokeWidth="1"
                    />
                    <circle cx={cx} cy={cyObs} r="4" fill="#EF4444" stroke="#fff" strokeWidth="1.5" />
                    <circle cx={cx} cy={cyMod} r="4" fill="#06B6D4" stroke="#fff" strokeWidth="1.5" />
                  </>
                )}
              </g>
            );
          })}
        </svg>

        {/* Hover Floating Details Card */}
        {hoveredIndex !== null && data[hoveredIndex] && (
          <div className="absolute top-2 right-4 bg-slate-900/90 border border-slate-700 backdrop-blur-md rounded-md p-2.5 text-xs font-mono shadow-2xl pointer-events-none">
            <div className="text-slate-400 text-[10px] pb-1 border-b border-slate-800">
              Timestamp: {data[hoveredIndex].time}
            </div>
            <div className="flex items-center justify-between gap-4 pt-1">
              <span className="text-amber-400">Observed:</span>
              <strong className="text-slate-100">{data[hoveredIndex].observedTemp}°C</strong>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-cyan-400">Thermodynamic Model:</span>
              <strong className="text-slate-100">{data[hoveredIndex].modelTemp}°C</strong>
            </div>
            <div className="flex items-center justify-between gap-4 pt-1 border-t border-slate-800 text-[11px]">
              <span className="text-slate-300 font-semibold">Residual ΔT:</span>
              <span
                className={
                  data[hoveredIndex].residual > 5 ? 'text-rose-400 font-bold' : 'text-emerald-400'
                }
              >
                +{data[hoveredIndex].residual}°C
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Legend & Physical Insight Explainer */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800/80 text-xs font-mono">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-amber-500 rounded"></span>
            <span className="text-slate-400">
              Observed SCADA (T<sub>obs</sub>): <strong className="text-slate-200">{currentObserved}°C</strong>
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-cyan-400 border-dashed border-t rounded"></span>
            <span className="text-slate-400">
              Physics Model (T<sub>model</sub>): <strong className="text-slate-200">{currentModel}°C</strong>
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] text-slate-400 bg-slate-900/60 px-2.5 py-1 rounded border border-slate-800">
          <Info className="w-3.5 h-3.5 text-cyan-400" />
          <span>Residual ΔT = T<sub>obs</sub> − T<sub>model</sub> exposes radiator cooling degradation hours before trip alarms.</span>
        </div>
      </div>
    </div>
  );
};
