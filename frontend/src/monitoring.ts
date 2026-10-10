import type { Telemetry, Analytics, AnalyticsPoint } from './api/contracts';

export const POLL_MS = Math.min(5000, Math.max(2000, Number(import.meta.env.VITE_POLL_INTERVAL_MS) || 3000));
export const STALE_MS = Math.max(1000, Number(import.meta.env.VITE_STALE_AFTER_MS) || 10000);
export const displayNumber = (value: number | null | undefined, unit?: string | null) => value == null ? 'Unavailable' : `${value}${unit && unit !== 'UNKNOWN' ? ` ${unit}` : ' (unit unknown)'}`;
export const contactLabel = (value: number | null | undefined) => value == null ? 'Unknown contact' : value === 1 ? 'Active' : 'Cleared';
export const thermalReady = (data?: Analytics | AnalyticsPoint | null) => data?.metadata?.components?.thermal ? data.metadata.components.thermal.status === 'READY' : data?.metadata?.thermal_readiness === 'READY';
export const forecastReleased = (data?: Analytics | null) => data?.metadata?.forecast?.release_status === 'RELEASED' && data.metadata.forecast.operational_eligible;
export function freshness(record: Telemetry | null | undefined, lastSuccess: number | null, now: number, error: string | null): string {
  if (error) return lastSuccess === null ? 'Disconnected / API error' : 'API error — retained data may be stale';
  if (!record) return 'No observations';
  if (record.acquisition?.source_kind === 'REPLAYED') return 'Historical replay — event time is not a live reading';
  if (!record.acquisition) return 'Unknown provenance';
  const age = now - Date.parse(record.timestamp);
  if (age < -STALE_MS) return 'Clock mismatch — future event time';
  return age > STALE_MS ? 'Stale measurement' : 'Within configured demo freshness window';
}
