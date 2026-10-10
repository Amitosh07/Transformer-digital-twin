import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { usePolling } from '../src/hooks/usePolling';
function deferred<T>() { let resolve!: (value:T)=>void; let reject!: (error:Error)=>void; const promise = new Promise<T>((a,b)=>{resolve=a;reject=b;}); return {promise,resolve,reject}; }
beforeEach(()=> {vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-09T00:00:00Z'));});
afterEach(()=>vi.useRealTimers());
it('ignores an old asset response and aborts obsolete requests',async()=>{
 const old=deferred<string>(), next=deferred<string>(); const signals:AbortSignal[]=[];
 const load=vi.fn((signal:AbortSignal)=>{signals.push(signal);return signals.length===1?old.promise:next.promise;});
 const {result,rerender,unmount}=renderHook(({id})=>usePolling(id,load,3000),{initialProps:{id:'A'}});
 rerender({id:'B'}); expect(signals[0].aborted).toBe(true);expect(result.current.data).toBeNull();
 await act(async()=>next.resolve('B response')); expect(result.current.data).toBe('B response');
 await act(async()=>old.resolve('A response')); expect(result.current.data).toBe('B response');
 unmount();expect(signals[1].aborted).toBe(true);expect(vi.getTimerCount()).toBe(0);
});
it('retains successful data and timestamp through a failed poll and allows retry',async()=>{
 const load=vi.fn< (signal:AbortSignal)=>Promise<string> >().mockResolvedValueOnce('accepted').mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce('recovered');
 const {result,unmount}=renderHook(()=>usePolling('A',load,3000));
 await act(async()=>{});const acceptedAt=result.current.lastSuccess;
 await act(async()=>vi.advanceTimersByTimeAsync(3000));
 expect(result.current.data).toBe('accepted');expect(result.current.lastSuccess).toBe(acceptedAt);expect(result.current.error).toBe('offline');
 await act(async()=>result.current.retry());expect(result.current.data).toBe('recovered');expect(result.current.lastSuccess).toBeGreaterThan(acceptedAt!);
 unmount();expect(vi.getTimerCount()).toBe(0);
});
it('does not overlap requests or poll after unmount',async()=>{
 const pending=deferred<string>();const load=vi.fn(()=>pending.promise);
 const {unmount}=renderHook(()=>usePolling('A',load,3000));
 await act(async()=>vi.advanceTimersByTimeAsync(12000));expect(load).toHaveBeenCalledTimes(1);
 unmount();await act(async()=>pending.resolve('late'));await act(async()=>vi.advanceTimersByTimeAsync(9000));expect(load).toHaveBeenCalledTimes(1);
});
it('disabled and one-shot resource requests have no recurring timers',async()=>{
 const load=vi.fn().mockResolvedValue('data');const {rerender,unmount}=renderHook(({enabled})=>usePolling('A',load,0,enabled),{initialProps:{enabled:false}});
 expect(load).not.toHaveBeenCalled();rerender({enabled:true});await act(async()=>{});expect(load).toHaveBeenCalledTimes(1);expect(vi.getTimerCount()).toBe(0);unmount();
});

