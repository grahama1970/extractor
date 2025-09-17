import puppeteer from 'puppeteer-core';
import path from 'node:path';
import fs from 'node:fs';

const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() {
  try {
    const res = await fetch(DISCOVERY);
    const j = await res.json();
    if (j && j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0', '127.0.0.1');
  } catch {}
  return null;
}

const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const ws = await getWS();
  if (!ws) {
    console.error('Smoke(tabbed_crisp_toolbar): No CDP WebSocket found');
    process.exit(3);
  }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);

  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 8000 });
  await page.waitForSelector('canvas', { timeout: 15000 });

  // Check crispness: backstore / CSS width ratio ~ devicePixelRatio
  const crisp = await page.evaluate(() => {
    const c = document.querySelector('canvas');
    if (!c) return { ok: false, reason: 'no_canvas' };
    const rect = c.getBoundingClientRect();
    const ratioX = (c.width / Math.max(1, rect.width));
    const ratioY = (c.height / Math.max(1, rect.height));
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const pass = ratioX >= dpr * 0.95 && ratioY >= dpr * 0.95; // allow small slack
    return { ok: pass, ratioX, ratioY, dpr };
  });

  // Verify toolbar not overlaying: it exists and is positioned above the canvas in DOM order
  const orderOk = await page.evaluate(() => {
    const toolbar = document.querySelector('[data-testid="top-toolbar"]');
    const c = document.querySelector('canvas');
    if (!toolbar || !c) return false;
    // Check vertical positions
    const tb = toolbar.getBoundingClientRect();
    const cr = c.getBoundingClientRect();
    return tb.bottom <= cr.top + 4; // no overlap tolerance
  });

  const shotPath = path.join(OUT_DIR, `smoke_tabbed_crisp_toolbar_${ts()}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(() => {});
  await page.close();
  await browser.disconnect();

  if (!crisp.ok || !orderOk) {
    console.error('Smoke(tabbed_crisp_toolbar): FAIL', { crisp, orderOk, shotPath });
    process.exit(1);
  }
  console.log('Smoke(tabbed_crisp_toolbar): OK');
  process.exit(0);
})().catch((e) => { console.error('Smoke(tabbed_crisp_toolbar) crashed:', e); process.exit(2); });

