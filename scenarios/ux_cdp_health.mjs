/*
 Live UX Health Scenario via Chrome DevTools (CDP)

 Preconditions:
 - BASE_URL points to a running UI route (e.g., http://127.0.0.1:8080/main)
 - CDP endpoint available via either:
     BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser
   or
     BROWSERLESS_DISCOVERY_URL=http://127.0.0.1:3000/json/version

 Emits:
 - scripts/artifacts/ux_scn_cdp_<ts>.png (screenshot)
 - scripts/artifacts/ux_scn_cdp_<ts>.log (text report)
*/
import fs from 'node:fs';
import path from 'node:path';
import { connectOrSkip, OUT_DIR, OUT_LOGS, ts, navigate, applyViewportFromEnv } from './lib/cdp.mjs';

const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || '';
let WS = (process.env.BROWSERLESS_WS || '').trim();
const BASE0 = (process.env.BASE_URL || 'http://127.0.0.1:8080/main').replace(/\/+$/, '');

fs.mkdirSync(OUT_DIR, { recursive: true });

async function discoverWS() {
  if (!DISCOVERY) return null;
  try {
    const res = await fetch(DISCOVERY);
    const j = await res.json();
    if (j && j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1');
  } catch {}
  return null;
}

function withClassicFallback(url) {
  try {
    const u = new URL(url);
    const p = (u.pathname||'/').replace(/\/+$/,'');
    if (p === '' || p === '/') { u.pathname = '/classic'; return u.toString(); }
  } catch {}
  return url;
}

async function main() {
  const BASE = withClassicFallback(BASE0);
  const browser = await connectOrSkip();
  const page = await browser.newPage();
  await applyViewportFromEnv(page);
  page.setDefaultTimeout(20000);

  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  const consoleLogs = [];
  page.on('console', (msg) => {
    const entry = `[console:${msg.type()}] ${msg.text()}`;
    consoleLogs.push(entry);
    if (msg.type() === 'error') consoleErrors.push(entry);
  });
  page.on('pageerror', (err) => pageErrors.push(`[pageerror] ${err.message}`));
  page.on('requestfailed', (req) => {
    const rt = req.resourceType?.() || 'other';
    const u = req.url?.() || req.url || '';
    if (['document','script','stylesheet'].includes(rt)) {
      failedRequests.push(`[requestfailed:${rt}] ${u}`);
    }
  });

  let navOk = true;
  try { await navigate(page, BASE); } catch { navOk = false; }
  const overlayPresent = await page.evaluate(() => !!document.querySelector('vite-error-overlay')).catch(() => false);
  const rootMounted = await page.evaluate(() => { const r = document.getElementById('root'); return !!r && r.childElementCount > 0; }).catch(() => false);

  let uiReady = false;
  try { await page.waitForSelector('[data-testid="page-label"]', { timeout: 3000 }); uiReady = true; } catch {}

  const broken = !navOk || overlayPresent || !rootMounted || !uiReady || consoleErrors.length > 0 || pageErrors.length > 0;
  const stamp = ts();
  const shotPath = path.join(OUT_DIR, `ux_scn_cdp_${stamp}.png`);
  const logPath = path.join(OUT_LOGS, `ux_scn_cdp_${stamp}.log`);
  try { await page.screenshot({ path: shotPath, fullPage: true }); } catch {}

  const report = [
    `BASE_URL=${BASE}`,
    `WS=${WS}`,
    `navOk=${navOk}`,
    `overlayPresent=${overlayPresent}`,
    `rootMounted=${rootMounted}`,
    `uiReady=${uiReady}`,
    `consoleErrors=${consoleErrors.length}`,
    `pageErrors=${pageErrors.length}`,
    `failedRequests=${failedRequests.length}`,
    '',
    '--- console (all) ---',
    ...consoleLogs,
    '',
    '--- pageErrors ---',
    ...pageErrors,
    '',
    '--- failedRequests ---',
    ...failedRequests,
    '',
    `screenshot: ${shotPath}`,
  ].join('\n');
  fs.writeFileSync(logPath, report, 'utf-8');

  await page.close();
  await browser.disconnect();

  if (broken) {
    console.error('Scenario ux_cdp_health: BROKEN');
    console.error(report);
    process.exit(1);
  } else {
    console.log('Scenario ux_cdp_health: OK');
    console.log(report);
  }
}

main().catch((e) => { console.error('ux_cdp_health crashed:', e?.message || e); process.exit(2); });
