// Actual Edge/React/API smoke; no fixture responses or monitoring fallback.
import { createRequire } from 'node:module';
import path from 'node:path';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
const require=createRequire(path.join(process.env.TEMP,'h06-browser','package.json'));
const {chromium}=require('playwright-core');
const root=path.resolve(import.meta.dirname,'../..');
const evidence=process.env.H06_EVIDENCE_DIR ?? path.join(root,'docs/hackathon_readiness/execution/evidence/h06');fs.mkdirSync(evidence,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
let stoppedBackend=false;
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const responses=[];page.on('response',async response=>{if(response.url().includes('/api/v1/')){try { responses.push({url:response.url(),status:response.status(),body:await response.json()}); } catch {}}});
 await page.goto(process.env.H06_UI_URL ?? 'http://127.0.0.1:5173',{waitUntil:'domcontentloaded'});
 const selector=page.getByRole('combobox',{name:'Asset',exact:true});await selector.waitFor();
 await selector.selectOption('H06-SIM-05');
 await page.getByText('SIMULATED_ESTIMATE',{exact:true}).waitFor({timeout:30000});
 await page.getByRole('img',{name:'Declared degradation trajectory and endpoint'}).waitFor({timeout:30000});
 await page.waitForFunction(()=>document.querySelector('[aria-label="Energy"]')?.textContent?.includes('Calculation:'));
 await page.waitForFunction(()=>document.querySelector('[aria-label="RUL"]')?.textContent?.includes('Method:'));
 const api=responses.filter(r=>r.url.includes('/H06-SIM-05/')&&r.status===200);
 if(!api.some(r=>r.url.endsWith('/rul'))||!api.some(r=>r.url.includes('/energy?')))throw Error('Missing actual resource responses');
 const latest=api.filter(r=>r.url.endsWith('/latest')).at(-1)?.body;
 if(!latest?.analytics||latest.telemetry.acquisition.source_kind!=='SIMULATED')throw Error('Missing real simulated persisted analysis');
 const before=await page.locator('#demo').innerText();
 if(!before.includes(latest.telemetry.timestamp))throw Error('DOM does not contain accepted event timestamp');
 await page.locator('#demo').screenshot({path:path.join(evidence,'dashboard-desktop.png')});
 await selector.selectOption('H06-RUL-ORACLE');await page.getByText('80 h',{exact:true}).waitFor({timeout:30000});
 await page.locator('#demo').screenshot({path:path.join(evidence,'rul-oracle-browser.png')});
 await selector.selectOption('H06-ENERGY-CONSTANT');await page.getByRole('combobox',{name:'Energy event-time window'}).selectOption('2h');await page.getByText('20 kWh',{exact:true}).waitFor({timeout:30000});
 await page.getByRole('combobox',{name:'Energy event-time window'}).selectOption('1h');
 await selector.selectOption('H06-ENERGY-RAMP');await page.getByText('5 kWh',{exact:true}).waitFor({timeout:30000});
 await page.setViewportSize({width:390,height:844});await page.locator('#demo').screenshot({path:path.join(evidence,'dashboard-mobile.png')});
 // Failure injection aborts actual requests, never substitutes responses.
 if(process.env.H06_REAL_OUTAGE==='true') {
  if(process.env.COMPOSE_PROJECT_NAME!=='transformer-h06-20261009')throw Error('Real outage requires the disposable H06 Compose project');
  execFileSync('docker',['compose','stop','backend'],{timeout:60000});stoppedBackend=true;
 } else await page.route('**/api/v1/**',route=>route.abort());
 await page.waitForFunction(()=>document.querySelector('#demo')?.textContent?.includes('API disconnected'),{timeout:20000});
 const outage=await page.locator('#demo').innerText();
 if(!outage.includes('retained data may be stale'))throw Error('Outage did not remain visible');
 fs.writeFileSync(path.join(evidence,'browser.json'),JSON.stringify({browser:await browser.version(),realBackendOutage:stoppedBackend,latest,dom:before,outage,responses},null,2));
 console.log('PASS actual React/API resource and curve rendering, desktop/mobile, oracle80h/ramp5kWh, visible API outage');
} finally {await browser.close();if(stoppedBackend)execFileSync('docker',['compose','start','backend'],{timeout:60000});}
