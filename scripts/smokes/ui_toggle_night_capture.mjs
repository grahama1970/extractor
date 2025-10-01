import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '') + '/main';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 15000 });
  const light = path.join(OUT_DIR, `ui_top_toolbar_light_${ts()}.png`);
  await page.screenshot({ path: light, fullPage: true }).catch(()=>{});
  await page.click('[data-testid="toggle-night"]').catch(()=>{});
  const dark = path.join(OUT_DIR, `ui_top_toolbar_dark_${ts()}.png`);
  await page.screenshot({ path: dark, fullPage: true }).catch(()=>{});
  await browser.disconnect();
  console.log(JSON.stringify({ ok:true, light, dark }, null, 2));
  process.exit(0);
})().catch((e)=>{ console.error('toggle_night failed:', e?.message||e); process.exit(2); });

