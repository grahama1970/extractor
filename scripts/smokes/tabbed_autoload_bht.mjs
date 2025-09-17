import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }
const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });
  // Without clicking Open PDF, the page should load a document and show a canvas
  const hasCanvas = await page.waitForSelector('canvas', { timeout: 8000 }).then(()=>true).catch(()=>false);
  // And at least one PNG thumbnail should appear shortly
  const okThumb = await page.waitForFunction(() => !!document.querySelector('img[alt^="Page"][src^="data:image/png"]'), { timeout: 4000 }).then(()=>true).catch(()=>false);
  const stamp = ts();
  const shot = path.join(OUT_DIR, `autoload_bht_${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  const log = path.join(OUT_DIR, `autoload_bht_${stamp}.log`);
  fs.writeFileSync(log, [`BASE_URL=${BASE}`, `hasCanvas=${hasCanvas}`, `hasThumb=${okThumb}`, `screenshot=${shot}`].join('\n'));
  await page.close(); await browser.disconnect();
  if (!(hasCanvas && okThumb)) { console.error('Autoload BHT failed'); process.exit(1); }
  console.log('Smoke(tabbed_autoload_bht): OK');
  process.exit(0);
})().catch(e => { console.error('Smoke(tabbed_autoload_bht) crashed:', e.message || e); process.exit(2); });
