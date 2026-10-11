import React, { useEffect, useRef, useState } from 'react';
import { Activity, Play, Pause, Zap } from 'lucide-react';

interface ThreePhaseWaveformProps {
  currentL1: number;
  currentL2: number;
  currentL3: number;
  neutralCurrent: number;
  isAbnormal?: boolean;
}

export const ThreePhaseWaveformCanvas: React.FC<ThreePhaseWaveformProps> = ({
  currentL1,
  currentL2,
  currentL3,
  neutralCurrent,
  isAbnormal = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const animFrameRef = useRef<number | null>(null);
  const phaseOffsetRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let dpr = window.devicePixelRatio || 1;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
    };

    resize();
    window.addEventListener('resize', resize);

    const render = () => {
      if (isPlaying) {
        phaseOffsetRef.current += 0.05 * speed;
      }

      const rect = canvas.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      const centerY = height / 2;

      ctx.clearRect(0, 0, width, height);

      // Draw Grid Lines
      ctx.strokeStyle = document.documentElement.classList.contains('light')
        ? '#E5EAF0'
        : 'rgba(51, 65, 85, 0.25)';
      ctx.lineWidth = 1;

      // Horizontal Center Line
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      ctx.moveTo(0, centerY);
      ctx.lineTo(width, centerY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Vertical Phase Division Grid
      const stepX = width / 8;
      for (let x = 0; x < width; x += stepX) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }

      // Max scale factor to fit current into canvas height
      const maxCurrent = Math.max(currentL1, currentL2, currentL3, 100);
      const ampScale = (height * 0.38) / maxCurrent;

      const offset = phaseOffsetRef.current;

      // Phase 1 (L1) - Electric Amber (#F59E0B)
      ctx.beginPath();
      ctx.strokeStyle = '#F59E0B';
      ctx.lineWidth = 2.5;
      ctx.shadowColor = 'rgba(245, 158, 11, 0.4)';
      ctx.shadowBlur = 8;
      for (let x = 0; x < width; x++) {
        const t = (x / width) * 4 * Math.PI + offset;
        const y = centerY - Math.sin(t) * (currentL1 * ampScale);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Phase 2 (L2) - Ion Cyan (#06B6D4) - 120 deg (2*PI/3)
      ctx.beginPath();
      ctx.strokeStyle = '#06B6D4';
      ctx.lineWidth = 2.5;
      ctx.shadowColor = 'rgba(6, 182, 212, 0.4)';
      ctx.shadowBlur = 8;
      for (let x = 0; x < width; x++) {
        const t = (x / width) * 4 * Math.PI + offset - (2 * Math.PI) / 3;
        const y = centerY - Math.sin(t) * (currentL2 * ampScale);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Phase 3 (L3) - Laser Emerald (#10B981) - 240 deg (4*PI/3)
      ctx.beginPath();
      ctx.strokeStyle = '#10B981';
      ctx.lineWidth = 2.5;
      ctx.shadowColor = 'rgba(16, 185, 129, 0.4)';
      ctx.shadowBlur = 8;
      for (let x = 0; x < width; x++) {
        const t = (x / width) * 4 * Math.PI + offset - (4 * Math.PI) / 3;
        const y = centerY - Math.sin(t) * (currentL3 * ampScale);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Neutral Current (INUT) - Pulsing Crimson (#EF4444)
      if (neutralCurrent > 10) {
        ctx.beginPath();
        ctx.strokeStyle = '#EF4444';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 3]);
        ctx.shadowColor = 'rgba(239, 68, 68, 0.6)';
        ctx.shadowBlur = 10;
        for (let x = 0; x < width; x++) {
          const t = (x / width) * 4 * Math.PI + offset;
          // Resultant unbalance wave
          const y =
            centerY -
            (Math.sin(t) * currentL1 +
              Math.sin(t - (2 * Math.PI) / 3) * currentL2 +
              Math.sin(t - (4 * Math.PI) / 3) * currentL3) *
              (ampScale * 0.85);
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.setLineDash([]);
      }

      ctx.shadowBlur = 0;
      animFrameRef.current = requestAnimationFrame(render);
    };

    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', resize);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [currentL1, currentL2, currentL3, neutralCurrent, isPlaying, speed]);

  return (
    <div className="flex flex-col bg-[#0A0E17] border border-slate-800 rounded-xl p-4 shadow-xl relative overflow-hidden">
      {/* Header controls */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-amber-400 animate-pulse" />
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300">
            Real-Time 3-Phase Vector Canvas (50 Hz / 60 FPS)
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs font-mono">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className="p-1 hover:bg-slate-800 rounded text-slate-300 hover:text-amber-400 transition"
              title={isPlaying ? 'Pause Waveform' : 'Resume Waveform'}
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={() => setSpeed(speed === 1 ? 0.5 : speed === 0.5 ? 2 : 1)}
              className="px-1.5 py-0.5 hover:bg-slate-800 rounded text-[10px] text-slate-400 hover:text-slate-200"
            >
              {speed}x
            </button>
          </div>

          {isAbnormal && (
            <span className="inline-flex items-center gap-1 text-[11px] font-mono font-semibold text-rose-400 bg-rose-950/60 border border-rose-800/60 px-2 py-0.5 rounded-full animate-pulse">
              <Zap className="w-3 h-3 text-rose-400" />
              VECTOR ASYMMETRY
            </span>
          )}
        </div>
      </div>

      {/* Canvas view */}
      <div className="relative w-full h-44 bg-[#06080E] rounded-lg border border-slate-900 overflow-hidden">
        <canvas ref={canvasRef} className="w-full h-full block" />

        {/* Phase legend badges */}
        <div className="absolute bottom-2 left-3 flex items-center gap-3 bg-black/60 backdrop-blur-md px-2.5 py-1 rounded-md border border-slate-800 text-[11px] font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shadow-[0_0_8px_#f59e0b]"></span>
            <span className="text-slate-300">Phase L1: <strong className="text-amber-400">{currentL1.toFixed(0)}A</strong></span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 shadow-[0_0_8px_#06b6d4]"></span>
            <span className="text-slate-300">Phase L2: <strong className="text-cyan-400">{currentL2.toFixed(0)}A</strong></span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_#10b981]"></span>
            <span className="text-slate-300">Phase L3: <strong className="text-emerald-400">{currentL3.toFixed(0)}A</strong></span>
          </div>
          {neutralCurrent > 10 && (
            <div className="flex items-center gap-1.5 border-l border-slate-700 pl-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping"></span>
              <span className="text-rose-300">Neutral I<sub>NUT</sub>: <strong className="text-rose-400">{neutralCurrent.toFixed(1)}A</strong></span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
