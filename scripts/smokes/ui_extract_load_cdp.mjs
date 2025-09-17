import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const URL = BASE.replace(/\/$/, '') + '/main';
const DISC = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const WS = process.env.BROWSERLESS_WS || null; // e.g. ws://127.0.0.1:9222/devtools/browser/...
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function discoverWS() {
  if (WS) return WS;
  try { const r = await fetch(DISC); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {}
  throw new Error('No CDP WS endpoint found; set BROWSERLESS_WS');
}

const ts = () => new Date().toISOString().replace(/[:.]/g,'-');
(async () => {
  const ws = await discoverWS();
  const stamp = ts();
  const shot = path.join(OUT_DIR, `ui_extract_load_cdp_${stamp}.png`);
  const logp = path.join(OUT_DIR, `ui_extract_load_cdp_${stamp}.log`);
  fs.writeFileSync(logp, `BASE_URL=${BASE}\nWS=${ws}\n`);
  let consoleErrors = 0;
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  try {
    const page = await browser.newPage();
    page.on('console', msg => { if (msg.type()==='error') { consoleErrors++; fs.appendFileSync(logp, `[console.error] ${msg.text()}\n`);} });
    page.on('pageerror', err => { consoleErrors++; fs.appendFileSync(logp, `[pageerror] ${err?.message||err}\n`); });
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="page-label"]', { timeout: 15000 });
    await page.waitForSelector('[data-testid="btn-extract-pipeline"]', { timeout: 10000 });
    await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
    fs.appendFileSync(logp, `screenshot=${shot}\n`);
    fs.appendFileSync(logp, `consoleErrors=${consoleErrors}\n`);
    if (consoleErrors > 0) { console.error('UI CDP smoke: FAIL'); process.exit(2); }
    console.log('UI CDP smoke: OK');
  } catch (e) {
    fs.appendFileSync(logp, `crash=${e?.message||e}\n`);
    console.error('UI CDP smoke crashed:', e?.message||e);
    process.exit(3);
  } finally {
    await browser.disconnect();
  }
})();

