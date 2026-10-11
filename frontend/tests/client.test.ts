import { afterEach, expect, it, vi } from 'vitest';
import { api, historyWindow } from '../src/api/client';
import { makeLatest, page } from './fixtures';
afterEach(()=>vi.unstubAllGlobals());
const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
it('uses the actual registry/latest paths and bounded UTC history parameters',async()=>{
 const fetcher=vi.fn().mockResolvedValueOnce(response(page([makeLatest().transformer],50))).mockResolvedValueOnce(response(makeLatest()));
 vi.stubGlobal('fetch',fetcher);expect((await api.registry()).items[0].id).toBe('HX-A');await api.latest('HX-A');
 expect(fetcher.mock.calls[0][0]).toContain('/api/v1/transformers?limit=50&offset=0');expect(fetcher.mock.calls[1][0]).toContain('/transformers/HX-A/latest');
 const query=historyWindow('2026-10-09T00:00:00Z');expect(query.get('from')).toBe('2026-10-08T23:00:00.000Z');expect(query.get('to')).toBe('2026-10-09T00:00:00.000Z');expect(query.get('limit')).toBe('100');expect(query.get('anchor')).toBe('latest');
});
it('rejects malformed response and mismatched asset identity',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(response({})).mockResolvedValueOnce(response(makeLatest('OTHER'))));
 await expect(api.latest('HX-A')).rejects.toMatchObject({code:'INVALID_RESPONSE'});await expect(api.latest('HX-A')).rejects.toMatchObject({code:'IDENTITY_MISMATCH'});
});
it('reports unavailable resources and API outages without fallback objects',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(response({detail:'Not Found'},404)).mockRejectedValueOnce(new TypeError('Failed to fetch')));
 await expect(api.rul('HX-A')).rejects.toMatchObject({status:404});await expect(api.energy('HX-A')).rejects.toMatchObject({code:'DISCONNECTED'});
});
it('forwards cancellation and clears the request timeout',async()=>{
 let received:AbortSignal|undefined;
 vi.stubGlobal('fetch',vi.fn((_url:string,init:RequestInit)=>{received=init.signal!;return new Promise((_resolve,reject)=>received?.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))));}));
 const controller=new AbortController();const pending=api.latest('HX-A',controller.signal);controller.abort();await expect(pending).rejects.toMatchObject({name:'AbortError'});expect(received?.aborted).toBe(true);
});
it('reports a bounded request timeout as an error',async()=>{
 vi.useFakeTimers();
 vi.stubGlobal('fetch',vi.fn((_url:string,init:RequestInit)=>new Promise((_resolve,reject)=>init.signal?.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))))));
 const pending=expect(api.latest('HX-A')).rejects.toMatchObject({code:'TIMEOUT'});
 await vi.advanceTimersByTimeAsync(10000);await pending;expect(vi.getTimerCount()).toBe(0);vi.useRealTimers();
});

