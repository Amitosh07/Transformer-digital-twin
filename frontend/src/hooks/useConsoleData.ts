import { useCallback, useEffect, useRef } from 'react';
import { api, historyWindow, ApiError } from '../api/client';
import type { Asset, Latest } from '../api/contracts';
import { usePolling } from './usePolling';
import { POLL_MS } from '../monitoring';

export async function loadRegistry(signal: AbortSignal): Promise<Asset[]> {
  const assets: Asset[] = [];
  let offset = 0;
  do {
    const page = await api.registry(signal, offset);
    assets.push(...page.items); offset += page.items.length;
    if (offset >= page.total) break;
    if (!page.items.length) throw new ApiError('Incomplete registry page', 200, 'INCOMPLETE_REGISTRY');
  } while (!signal.aborted);
  return [...new Map(assets.map(a => [a.id, a])).values()];
}
export const registryLoader = (signal: AbortSignal) => loadRegistry(signal);
export interface AssetSnapshot { data: Latest | null; error: string | null; lastSuccess: number | null }
/** Three concurrent visible-card requests at most; no portfolio history fan-out. */
export async function loadPortfolio(ids: string[], signal: AbortSignal, previous: Record<string, AssetSnapshot>) {
  const result: Record<string, AssetSnapshot> = {}; let cursor = 0;
  await Promise.all(Array.from({ length: Math.min(3, ids.length) }, async () => {
    while (!signal.aborted && cursor < ids.length) {
      const id = ids[cursor++];
      try { result[id] = { data: await api.latest(id, signal), error: null, lastSuccess: Date.now() }; }
      catch (error) {
        if (signal.aborted) throw error;
        result[id] = { data: previous[id]?.data ?? null, lastSuccess: previous[id]?.lastSuccess ?? null, error: error instanceof Error ? error.message : 'Request failed' };
      }
    }
  }));
  return result;
}
export function usePortfolio(ids: string[], enabled: boolean) {
  const key = JSON.stringify(ids); const cache = useRef<Record<string, AssetSnapshot>>({});
  const load = useCallback(async (signal: AbortSignal) => {
    const result = await loadPortfolio(JSON.parse(key) as string[], signal, cache.current);
    if (!signal.aborted) cache.current = result;
    return result;
  }, [key]);
  return usePolling('portfolio:' + key, load, 15000, enabled && ids.length > 0);
}
export function useAssetData(id: string, area: string) {
  const latestLoad = useCallback((s: AbortSignal) => api.latest(id, s), [id]);
  const latest = usePolling(id, latestLoad, POLL_MS, !!id);
  const event = useRef<string | null>(null);
  useEffect(() => { event.current = latest.data?.telemetry?.timestamp ?? null; }, [id, latest.data?.telemetry?.timestamp]);
  const historyLoad = useCallback(async (s: AbortSignal) => {
    const q = historyWindow(event.current); q.set('limit', '300'); q.set('order', 'desc');
    const [telemetry, analytics] = await Promise.all([api.telemetry(id, q, s), api.analytics(id, q, s)]);
    if (telemetry.items.some(t => t.transformer_id !== id) || analytics.items.some(a => a.transformer_id && a.transformer_id !== id)) throw new ApiError('History asset identity mismatch', 200, 'IDENTITY_MISMATCH');
    return { telemetry: { ...telemetry, items: [...telemetry.items].reverse() }, analytics: { ...analytics, items: [...analytics.items].reverse() }, from: q.get('from'), to: q.get('to') };
  }, [id]);
  const lifecycleQuery = () => {
    const q = historyWindow(event.current); q.set('from', new Date(Date.parse(q.get('to')!) - 86400000).toISOString()); q.set('limit', '30'); q.delete('order'); return q;
  };
  const alertsLoad = useCallback(async (s: AbortSignal) => {
    const q = lifecycleQuery(); let page = await api.alerts(id, q, s);
    // Actual lifecycle API sorts ascending: request the final bounded page for recent events.
    if (page.total > 30) { q.set('offset', String(page.total - 30)); page = await api.alerts(id, q, s); }
    return { ...page, items: [...page.items].reverse() };
  }, [id]);
  const maintenanceLoad = useCallback(async (s: AbortSignal) => {
    const q = lifecycleQuery(); let page = await api.maintenance(id, q, s);
    if (page.total > 30) { q.set('offset', String(page.total - 30)); page = await api.maintenance(id, q, s); }
    return { ...page, items: [...page.items].reverse() };
  }, [id]);
  const rulLoad = useCallback((s: AbortSignal) => api.rul(id, s), [id]);
  const energyLoad = useCallback((s: AbortSignal) => api.energy(id, s), [id]);
  const projectionLoad = useCallback((s: AbortSignal) => api.projection(id, s), [id]);
  const ready = !!id && !!latest.data;
  return { latest,
    history: usePolling(id, historyLoad, 15000, ready && ['monitoring', 'thermal'].includes(area)),
    alerts: usePolling(id, alertsLoad, 15000, ready && ['monitoring', 'alarms'].includes(area)),
    maintenance: usePolling(id, maintenanceLoad, 15000, ready && area === 'maintenance'),
    rul: usePolling(id, rulLoad, 15000, ready && area === 'maintenance'),
    energy: usePolling(id, energyLoad, 30000, ready && area === 'maintenance'),
    projection: usePolling(id, projectionLoad, 30000, ready && area === 'maintenance') };
}
