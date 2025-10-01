/* Scenario: No /api/* Calls Post-Ready in Preview (CDP)
 - Requires PREVIEW=1 (otherwise skip)
 - Requires CDP endpoint via BROWSERLESS_WS or discovery
*/
import puppeteer from 'puppeteer';

const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || '';
let WS = (process.env.BROWSERLESS_WS || '').trim();
const TARGET_URL = (process.env.TARGET_URL || process.env.BASE_URL || 'http://127.0.0.1:8080/main').replace(/\/+$/,'');
const PREVIEW = process.env.VITE_PREVIEW === '1' || process.env.PREVIEW === '1';
const WINDOW_MS = Number(process.env.NO_PREVIEW_API_WINDOW_MS ?? 5000);

if (!PREVIEW) { console.log('[scenario no_preview_api_requests] SKIP (not in preview)'); process.exit(0); }

async function discoverWS(){ if(!DISCOVERY) return null; try{ const r=await fetch(DISCOVERY); const j=await r.json(); return j?.webSocketDebuggerUrl?.replace('0.0.0.0','127.0.0.1')||null; }catch{ return null; } }
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
function isApi(u){ try{ return new URL(u).pathname.startsWith('/api/'); }catch{ return String(u).includes('/api/'); } }

async function main(){
  if (!WS) { const w = await discoverWS(); if (w) WS=w; }
  if (!WS) { console.log('SKIP: No CDP endpoint (set BROWSERLESS_WS or discovery).'); process.exit(0); }
  let browser; try{ browser = await puppeteer.connect({ browserWSEndpoint: WS, defaultViewport: null }); }catch(e){ if(/ECONNREFUSED/.test(String(e?.message||e||''))){ console.log('SKIP: CDP unreachable at', WS); process.exit(0);} throw e; }
  const page = await browser.newPage();
  let offender=null;
  page.on('request', req=>{ const u=req.url?.()||req.url||''; if(isApi(u)) offender=offender||{kind:'request', url:u, method: req.method?.()??'GET'}; });
  page.on('response', res=>{ const u=res.url?.()||res.url||''; if(isApi(u)) offender=offender||{kind:'response', url:u, status: res.status?.()??res.status()}; });
  await page.goto(TARGET_URL, { waitUntil:'networkidle0', timeout: 30000 });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 30000 });
  await page.waitForFunction(() => !!(document.getElementById('root')?.childElementCount), { timeout: 30000 });
  await sleep(WINDOW_MS);
  try {
    const outDir = require('node:path').resolve('scripts','artifacts');
    require('node:fs').mkdirSync(outDir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g,'-');
    await page.screenshot({ path: require('node:path').join(outDir, `ux_no_preview_api_${stamp}.png`), fullPage: true });
  } catch {}
  await browser.disconnect();
  if (offender) { console.error('[scenario no_preview_api_requests] FAIL — saw /api after ready:', offender); process.exit(1); }
  console.log(`[scenario no_preview_api_requests] OK (no /api within ${WINDOW_MS}ms post-ready)`);
}
main().catch(e=>{ console.error('no_preview_api_requests crashed:', e?.message||e); process.exit(2); });
