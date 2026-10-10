import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.join(process.env.TEMP,'h06-browser','package.json'));
const {chromium}=require('playwright-core');
const manifest=process.argv[2],out=path.dirname(manifest);
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const log=fs.createWriteStream(path.join(out,'browser-observations.jsonl'),{flags:'a'});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const latest=new Map();
 page.on('response',async r=>{if(r.url().endsWith('/latest')&&r.status()===200){try {const body=await r.json();latest.set(body.transformer.id,{body,received:Date.now()});}catch{}}});
 await page.goto('http://127.0.0.1:5173',{waitUntil:'domcontentloaded'});
 const selector=page.getByRole('combobox',{name:'Asset',exact:true});await selector.waitFor();await page.waitForFunction(()=>document.querySelector('[aria-label="Asset"]')?.options.length>1,{timeout:20000});
 let index=0;
 while(JSON.parse(fs.readFileSync(manifest)).status==='running') {
  const assets=JSON.parse(fs.readFileSync(manifest)).assets,asset=assets[index++%assets.length];
  try {
   for(let n=0;n<5;n++){
    if(await selector.locator(`option[value="${asset}"]`).count())break;
    const next=page.getByRole('button',{name:'Next assets',exact:true});
    if(await next.isDisabled())await page.getByRole('button',{name:'Previous assets',exact:true}).click();else await next.click();
    await page.waitForTimeout(700);
   }
   await selector.selectOption(asset);
   await page.waitForTimeout(3500);
   const observation=latest.get(asset),dom=await page.getByRole('region',{name:'Source and freshness'}).count().catch(()=>0);
   const text=await page.locator('[aria-label="Source and freshness"]').innerText();
   if(observation?.body.telemetry&&text.includes(observation.body.telemetry.acquisition.snapshot_id)){
    const t=observation.body.telemetry,a=observation.body.analytics,now=Date.now();
    log.write(JSON.stringify({asset,observed_at:new Date(now).toISOString(),timestamp:t.timestamp,snapshot:t.acquisition.snapshot_id,received_at:t.received_at,analytics_timestamp:a?.timestamp,source:t.acquisition.source_kind,event_to_visible_ms:now-Date.parse(t.timestamp),backend_received_to_visible_ms:now-Date.parse(t.received_at),dom:text})+'\n');
   }else log.write(JSON.stringify({asset,error:'No matching latest response/snapshot visible',dom:text,observed_at:new Date().toISOString()})+'\n');
   if(index===3)await page.locator('#demo').screenshot({path:path.join(out,'portfolio.png')});
  }catch(e){log.write(JSON.stringify({asset,error:String(e),observed_at:new Date().toISOString()})+'\n');}
 }
}finally {log.end();await browser.close();}
