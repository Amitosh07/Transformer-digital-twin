// Controlled UI fixtures only; never imported by application code.
import fs from 'node:fs';
import { assetSchema, analyticsSchema, telemetrySchema, rulResourceSchema, energySchema, type Latest } from '../src/api/contracts';
const examples: {name:string;payload:unknown}[] = JSON.parse(fs.readFileSync('../tests/fixtures/hackathon/examples.json','utf8'));
export function example(name:string) { const result = examples.find(x=>x.name===name); if (!result) throw new Error(name); return result.payload; }
export const event = '2026-10-09T00:00:00Z';
export function makeLatest(id='HX-A'): Latest {
 const asset = assetSchema.parse({...example('asset-valid') as object,id,name:'API asset '+id,created_at:event,updated_at:event});
 const telemetry = telemetrySchema.parse({...example('telemetry-valid') as object,transformer_id:id,current_l1:0,oil_temp_alarm:null,oil_temp_trip:0,oil_temperature:37});
 const analytics = analyticsSchema.parse({...example('analytics-valid') as object,transformer_id:id,health_index:37,maintenance_priority:'WATCH',maintenance_recommendation:'Inspect supplied backend evidence'});
 return {transformer:asset,telemetry,analytics,open_alerts_count:0,schema_version:'1.1.0',analytics_availability:{status:'AVAILABLE',reasons:[],state_coverage_loss:false}};
}
export const page = <T,>(items:T[],limit=100) => ({items,total:items.length,limit,offset:0});
const oracles: {rul:{name:string;expected:unknown}[];energy:{name:string;expected:unknown}[]} = JSON.parse(fs.readFileSync('../tests/fixtures/hackathon/oracles.json','utf8'));
export const rulOracle = (name:string) => rulResourceSchema.parse(oracles.rul.find(x=>x.name===name)?.expected);
export const energyOracle = (name:string) => energySchema.parse(oracles.energy.find(x=>x.name===name)?.expected);

