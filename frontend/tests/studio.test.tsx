import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import { InteractiveTwinStudio } from '../src/components/InteractiveTwinStudio';
import { Hero } from '../src/components/Hero';
import { ImpactMetrics } from '../src/components/ImpactMetrics';
import { makeLatest, page } from './fixtures';
afterEach(()=>vi.unstubAllGlobals());
function response(data:unknown,status=200) { return new Response(JSON.stringify(data),{status}); }
function installFetch(override?: (url:URL)=>Promise<Response>|undefined) {
 const fetcher=vi.fn((input:string)=>{
  const url=new URL(input);const supplied=override?.(url);if(supplied)return supplied;
  const id=url.pathname.split('/')[4];const latest=makeLatest(id);
  if(url.pathname==='/api/v1/transformers')return Promise.resolve(response(page([makeLatest('HX-A').transformer,makeLatest('HX-B').transformer],50)));
  if(url.pathname.endsWith('/latest'))return Promise.resolve(response(latest));
  if(url.pathname.endsWith('/telemetry'))return Promise.resolve(response(page([latest.telemetry])));
  if(url.pathname.endsWith('/analytics'))return Promise.resolve(response(page([latest.analytics])));
  if(url.pathname.endsWith('/alerts'))return Promise.resolve(response(page([{id:1,transformer_id:id,timestamp:latest.telemetry!.timestamp,severity:'WARNING',alert_type:'BACKEND_ALERT',trigger:'Supplied trigger',evidence:{provided:true},threshold_or_reason:'Supplied reason',recommended_action:'Review evidence',status:'OPEN',last_seen_at:latest.telemetry!.timestamp}])));
  if(url.pathname.endsWith('/maintenance'))return Promise.resolve(response(page([{id:1,transformer_id:id,timestamp:latest.telemetry!.timestamp,priority:'WATCH',recommendation:'Actual backend recommendation',reason_codes:[],status:'OPEN'}])));
  if(url.pathname.endsWith('/mqtt/status'))return Promise.resolve(response({enabled:false,connected:false,queue_depth:0,committed_count:0,conflicted_count:0,dropped_count:0,last_message_at:null,last_error:null}));
  return Promise.resolve(response({detail:'Not Found'},404));
 });
 vi.stubGlobal('fetch',fetcher);return fetcher;
}
it('populates registry assets and renders actual latest/history, recommendations and contact states',async()=>{
 const fetcher=installFetch();render(<InteractiveTwinStudio/>);
 const selector=screen.getByRole('combobox',{name:'Asset'});
 await waitFor(()=>expect(within(selector).getByRole('option',{name:'API asset HX-B (HX-B)'})).toBeInTheDocument());
 await waitFor(()=>expect(screen.getByText(/Actual backend recommendation/)).toBeVisible());
 expect(within(screen.getByRole('region',{name:'Health index'})).getByText('37')).toBeVisible();
 expect(screen.getByText(/Oil temperature alarm: Unknown contact/)).toHaveTextContent('Oil temperature trip: Cleared');
 expect(screen.getByText(/Source: SIMULATED/)).toBeVisible();
 await waitFor(()=>expect(screen.getByText(/RUL API not available: API HTTP 404/)).toBeVisible());
 expect(screen.getByText(/Energy API not available: API HTTP 404/)).toBeVisible();
 await waitFor(()=>expect(screen.getByText(/History:.*Showing 1 of 1/)).toBeVisible());
 expect(screen.getByText(/Observed 37/)).toBeInTheDocument();
 const paths=fetcher.mock.calls.map(([url])=>new URL(url).pathname);
 expect(paths.filter(p=>p.includes('/HX-B/'))).toHaveLength(0);
 expect(screen.getByText(/Not assessed — select asset/)).toBeVisible();
});
it('an asset switch cannot be overwritten by a delayed previous latest response',async()=>{
 let resolveOld!:(value:Response)=>void;
 installFetch(url=>url.pathname==='/api/v1/transformers/HX-A/latest'?new Promise(r=>{resolveOld=r;}):undefined);
 render(<InteractiveTwinStudio/>);await waitFor(()=>expect(resolveOld).toBeDefined());
 fireEvent.change(screen.getByRole('combobox',{name:'Asset'}),{target:{value:'HX-B'}});
 await waitFor(()=>expect(screen.getByRole('region',{name:'Source and freshness'})).toHaveTextContent('HX-B'));
 resolveOld(response({...makeLatest('HX-A'),analytics:{...makeLatest('HX-A').analytics!,health_index:99}}));
 await waitFor(()=>expect(screen.getByRole('region',{name:'Health index'})).toHaveTextContent('37'));
 expect(screen.getByRole('combobox',{name:'Asset'})).toHaveValue('HX-B');expect(screen.getByRole('region',{name:'Source and freshness'})).not.toHaveTextContent('HX-A ·');
});
it('partial history failure remains visible without fabricating observations or healthy status',async()=>{
 installFetch(url=>url.pathname.endsWith('/telemetry')?Promise.resolve(response({},500)):undefined);
 render(<InteractiveTwinStudio/>);await waitFor(()=>expect(screen.getByText(/API HTTP 500/)).toBeVisible());
 expect(within(screen.getByRole('region',{name:'Thermal history'})).getByText('No observations')).toBeVisible();expect(screen.queryByText('HEALTHY')).not.toBeInTheDocument();
});
it('API outage has no local monitoring fallback',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('offline')));
 render(<InteractiveTwinStudio/>);await waitFor(()=>expect(screen.getAllByRole('alert').length).toBeGreaterThan(0));
 expect(screen.getByRole('combobox',{name:'Asset'})).toHaveValue('');expect(screen.queryByRole('region',{name:'Health index'})).not.toBeInTheDocument();
});
it('empty registry and empty latest measurements are explicit',async()=>{
 vi.stubGlobal('fetch',vi.fn((url:string)=>Promise.resolve(new URL(url).pathname==='/api/v1/transformers'?response(page([],50)):response({},404))));
 render(<InteractiveTwinStudio/>);await waitFor(()=>expect(screen.getByText('No registered assets')).toBeVisible());
});
it('latest null telemetry and analytics remain unavailable without zero history',async()=>{
 installFetch(url=>url.pathname.endsWith('/latest')?Promise.resolve(response({...makeLatest(),telemetry:null,analytics:null,analytics_availability:{status:'UNAVAILABLE',reasons:['ML_UNAVAILABLE'],state_coverage_loss:true}})):url.pathname.endsWith('/telemetry')||url.pathname.endsWith('/analytics')?Promise.resolve(response(page([]))):undefined);
 render(<InteractiveTwinStudio/>);await waitFor(()=>expect(screen.getByText(/Analytics availability: UNAVAILABLE/)).toBeVisible());
 expect(screen.getByText(/ML_UNAVAILABLE/)).toBeVisible();expect(within(screen.getByRole('region',{name:'Health index'})).getAllByText(/Unavailable/).length).toBeGreaterThan(0);
 expect(within(screen.getByRole('region',{name:'Canonical measurements'})).getByText('No observations')).toBeVisible();
});
it.each([390,1440])('components render at configured %s px DOM viewport (not visual-layout proof)',width=>{
 Object.defineProperty(window,'innerWidth',{configurable:true,value:width});render(<><Hero/><ImpactMetrics/></>);
 expect(screen.getByRole('link',{name:/Open API monitoring/})).toBeVisible();expect(screen.getByText('Monitoring with visible evidence')).toBeVisible();
});
it('removes unsupported claims and excludes educational simulation from monitoring imports',()=>{
 const studio=fs.readFileSync('src/components/InteractiveTwinStudio.tsx','utf8');expect(studio).not.toMatch(/runTwinSimulation|generateTimeSeriesPoints|TRANSFORMER_ASSETS/);
 const files=['Hero','ImpactMetrics','Solution','FeaturesGrid','PipelineWalkthrough'];
 const source=files.map(name=>fs.readFileSync('src/components/'+name+'.tsx','utf8')).join('\n');
 expect(source).not.toMatch(/\+48h|-74%|<15ms|100%|48 hours of advance foresight|IEEE C57\.91 COMPLIANT/);
});

