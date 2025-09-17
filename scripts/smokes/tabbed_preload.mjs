import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getApiBase() {
  const candidates = [process.env.API_BASE, 'http://127.0.0.1:8001', 'http://127.0.0.1:8000'].filter(Boolean);
  for (const u of candidates) {
    try {
      const r = await fetch(u.replace(/\/$/, '') + '/api/list');
      if (r.ok) return u.replace(/\/$/, '');
    } catch {}
  }
  return null;
}

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
  const apiBase = await getApiBase();
  if (!apiBase) {
    console.error('Smoke(tabbed_preload): API not reachable on 8001/8000');
    process.exit(2);
  }

  // Check list for BHT file
  const list = await (await fetch(apiBase + '/api/list')).json();
  const names = (list.items || []).map((x) => x.name.toLowerCase());
  const hasBHT = names.includes('bht cv32a65x.pdf');

  const ws = await getWS();
  if (!ws) {
    console.error('Smoke(tabbed_preload): No CDP WebSocket found. Start browserless or expose a remote Chrome.');
    process.exit(3);
  }

  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);

  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 8000 });
  await page.waitForSelector('canvas', { timeout: 15000 });

  // Open modal and pick BHT if present
  await page.click('[data-testid="btn-open-pdf"]');
  await page.waitForSelector('[data-testid="open-dialog"]', { timeout: 5000 });
  if (hasBHT) {
    const sel = '[data-testid="open-item"][data-name="BHT CV32A65X.pdf"]';
    const exists = await page.$(sel);
    if (exists) {
      await page.click(sel);
      // Expect canvas remains and UI responsive
      await page.waitForSelector('canvas', { timeout: 10000 });
    } else {
      console.warn('Smoke(tabbed_preload): BHT not listed in modal; continuing');
    }
  }

  const shotPath = path.join(OUT_DIR, `smoke_tabbed_preload_${ts()}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(() => {});
  await page.close();
  await browser.disconnect();

  console.log('Smoke(tabbed_preload): OK');
  process.exit(0);
})().catch((e) => { console.error('Smoke(tabbed_preload) crashed:', e); process.exit(1); });

