/* Scenario: Console/Request Hard Errors (CDP)
 - Requires CDP endpoint via BROWSERLESS_WS or BROWSERLESS_DISCOVERY_URL
 - BASE_URL points to UI route (e.g., http://127.0.0.1:8080/main)
 - Emits screenshot/log under scripts/artifacts/
*/
import fs from 'node:fs';
import path from 'node:path';
import { connectOrSkip, OUT_DIR, ts } from '../lib/cdp.mjs';

const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || '';
let WS = (process.env.BROWSERLESS_WS || '').trim();
const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080/main').replace(/\/+$/, '');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function discoverWS(){ if(!DISCOVERY) return null; try{ const r=await fetch(DISCOVERY); const j=await r.json(); return j?.webSocketDebuggerUrl?.replace('0.0.0.0','127.0.0.1')||null; }catch{ return null; } }
function isFavicon(u=''){ return /favicon\.ico(\?|$)/.test(u) || u.includes('favicon'); }

async function main(){
  const browser = await connectOrSkip();
  const page = await browser.newPage();

  const consoleErrors=[], pageErrors=[], failed=[]; const allLogs=[];
  page.on('console', m=>{ const s=`[console:${m.type()}] ${m.text()}`; allLogs.push(s); if(m.type()==='error') consoleErrors.push(s); });
  page.on('pageerror', e=>pageErrors.push(`[pageerror] ${e.message}`));
  page.on('requestfailed', req=>{ const rt=req.resourceType?.()||'other'; const u=req.url?.()||req.url||''; if(['document','script','stylesheet'].includes(rt)) failed.push(`[requestfailed:${rt}] ${u}`); });

  let navOk=true; try { await page.goto(BASE,{waitUntil:'domcontentloaded'}); } catch{ navOk=false; }
  const overlay = await page.evaluate(()=>!!document.querySelector('vite-error-overlay')).catch(()=>false);
  const rootMounted = await page.evaluate(()=>{const r=document.getElementById('root'); return !!r && r.childElementCount>0;}).catch(()=>false);
  let ready=false; try{ await page.waitForSelector('[data-testid="page-label"]',{timeout:3000}); ready=true; }catch{}

  const broken = !navOk || overlay || !rootMounted || !ready || consoleErrors.length>0 || pageErrors.length>0;
  const stamp=ts(); const shot=path.join(OUT_DIR,`ux_console_errors_${stamp}.png`); const logp=path.join(OUT_DIR,`ux_console_errors_${stamp}.log`);
  try{ await page.screenshot({path:shot, fullPage:true}); }catch{}
  const report=[`BASE_URL=${BASE}`,`WS=${WS}`,`navOk=${navOk}`,`overlayPresent=${overlay}`,`rootMounted=${rootMounted}`,`uiReady=${ready}`,`consoleErrors=${consoleErrors.length}`,`pageErrors=${pageErrors.length}`,`failedRequests=${failed.length}`,'','--- console (all) ---',...allLogs,'','--- pageErrors ---',...pageErrors,'','--- failedRequests ---',...failed.filter(u=>!isFavicon(u)),'',`screenshot: ${shot}`].join('\n');
  fs.writeFileSync(logp, report, 'utf-8');
  await page.close(); await browser.disconnect();
  if(broken){ console.error('Scenario ux/console_errors: BROKEN'); console.error(report); process.exit(1);} else { console.log('Scenario ux/console_errors: OK'); console.log(report); }
}
main().catch(e=>{ console.error('ux/console_errors crashed:', e?.message||e); process.exit(2); });
