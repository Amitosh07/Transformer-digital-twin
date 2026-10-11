// Real API/Edge judging rehearsal. Delay actual responses; never fabricate JSON.
import fs from 'node:fs';import path from 'node:path';import {createRequire} from 'node:module';import {execFileSync} from 'node:child_process';
const require=createRequire(path.join(process.env.TEMP,'h06-browser','package.json'));const {chromium}=require('playwright-core');
const manifest=JSON.parse(fs.readFileSync(process.argv[2])),mode=process.argv[3]??'switch',out=path.join(path.dirname(process.argv[2]),`judging-${mode}.json`);
if(process.env.COMPOSE_PROJECT_NAME!=='transformer-h06-20261009')throw Error('Requires disposable project');
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});let stopped=false;
const result={mode,started:new Date().toISOString(),passed:false};
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});await page.goto('http://127.0.0.1:5173',{waitUntil:'domcontentloaded'});
 const selector=page.getByRole('combobox',{name:'Asset',exact:true});await selector.waitFor();await page.waitForFunction(()=>document.querySelector('[aria-label="Asset"]')?.options.length>1,{timeout:20000});
 async function select(id){for(let i=0;i<5;i++){if(await selector.locator(`option[value="${id}"]`).count())break;const next=page.getByRole('button',{name:'Next assets',exact:true});if(await next.isDisabled())await page.getByRole('button',{name:'Previous assets',exact:true}).click();else await next.click();await page.waitForTimeout(700);}await selector.selectOption(id);}
 if(mode==='switch'){
  const [a,b]=manifest.assets;let resolve;const captured=new Promise(r=>resolve=r);let old=null;
  await page.route(`**/transformers/${a}/latest`,async route=>{try{const response=await route.fetch();old=await response.json();resolve();await page.waitForTimeout(2500);await route.fulfill({response});}catch{}});
  await select(a);await Promise.race([captured,new Promise((_,reject)=>setTimeout(()=>reject(Error('Delayed API response not captured')),20000))]);
  const response=page.waitForResponse(r=>r.url().endsWith(`/transformers/${b}/latest`)&&r.status()===200,{timeout:20000});await select(b);const current=await (await response).json();
  await page.waitForTimeout(4000);const text=await page.locator('[aria-label="Source and freshness"]').innerText();
  if(await selector.inputValue()!==b||!text.includes(b)||text.includes(old.telemetry.acquisition.snapshot_id))throw Error('Old asset overwrote selected identity');
  if(!text.includes(current.telemetry.acquisition.snapshot_id))throw Error('Current selected snapshot not visible');
  result.delayed_asset=old;result.selected_asset=current;result.dom=text;
 }else if(mode==='outage'){
  await select('H06-SIM-05');await page.waitForTimeout(4000);const before=await page.locator('[aria-label="Source and freshness"]').innerText();
  const poll=before.match(/Last successful API poll: ([^\n]+)/)?.[1];if(!poll||poll==='Never')throw Error('Missing successful baseline poll');
  execFileSync('docker',['compose','stop','backend'],{timeout:60000});stopped=true;
  await page.waitForFunction(()=>document.querySelector('#demo')?.textContent?.includes('API disconnected'),{timeout:20000});await page.waitForTimeout(4000);
  const after=await page.locator('[aria-label="Source and freshness"]').innerText(),dom=await page.locator('#demo').innerText();
  if(after.match(/Last successful API poll: ([^\n]+)/)?.[1]!==poll||!dom.includes('retained data may be stale'))throw Error('Failed poll refreshed success or hid failure');
  await page.locator('#demo').screenshot({path:path.join(path.dirname(out),'api-outage.png')});result.before=before;result.after=after;result.dom=dom;
 }else if(mode==='replay'){
  await select('H06-REPLAY-R1');await page.waitForTimeout(4000);const text=await page.locator('[aria-label="Source and freshness"]').innerText();
  result.dom=text;
  if(!text.includes('REPLAYED')||!text.includes('Historical replay')||!text.includes('2026-10-09T00:00:'))throw Error('Replay source/freshness missing');
  await page.locator('#demo').screenshot({path:path.join(path.dirname(out),'replay-fallback.png')});result.dom=text;
 }
 result.passed=true;console.log('PASS judging browser',mode);
}catch(e){result.error=String(e);throw e;}finally{result.finished=new Date().toISOString();fs.writeFileSync(out,JSON.stringify(result,null,2));await browser.close();if(stopped)execFileSync('docker',['compose','start','backend'],{timeout:60000});}
