import { useCallback, useEffect, useState } from 'react';

export interface PollState<T> { key: string; data: T | null; lastSuccess: number | null; error: string | null; loading: boolean; }
const emptyState = <T,>(key: string, enabled: boolean): PollState<T> => ({ key, data: null, lastSuccess: null, error: null, loading: enabled });
/** One request at a time; timer starts after completion. Key guards also
 * suppress obsolete data in the render before the effect cleanup executes. */
export function usePolling<T>(key: string, load: (signal: AbortSignal) => Promise<T>, intervalMs: number, enabled = true) {
  const [state, setState] = useState<PollState<T>>(() => emptyState(key,enabled));
  const [revision, setRevision] = useState(0);
  const retry = useCallback(() => setRevision(r => r + 1), []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    setState(previous => previous.key === key ? { ...previous, loading: enabled } : emptyState(key,enabled));
    const poll = async () => {
      try {
        const data = await load(controller.signal);
        if (active) setState({ key, data, lastSuccess: Date.now(), error: null, loading: false });
      } catch (error) {
        if (active && !controller.signal.aborted) setState(previous => ({ ...previous, loading: false, error: error instanceof Error ? error.message : 'Request failed' }));
      } finally {
        if (active && enabled && intervalMs > 0) timer = setTimeout(poll, intervalMs);
      }
    };
    if (enabled) void poll();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [key, load, intervalMs, enabled, revision]);
  return { ...(state.key === key ? state : emptyState<T>(key,enabled)), retry };
}
