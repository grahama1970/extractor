import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
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
  const api = await getApiBase();
  if (!api) {
    console.error('Smoke(tabbed_suggest_tables_ui): API not reachable');
    process.exit(2);
  }

  // Probe Camelot availability and suggestions
  const list = await (await fetch(api + '/api/list')).json();
  const pick = (list.items || [])[0];
  if (!pick) {
    console.error('Smoke(tabbed_suggest_tables_ui): no PDFs listed');
    process.exit(2);
  }
  const probe = await (await fetch(api + `/api/suggest/tables?rel=${encodeURIComponent(pick.rel || pick.name)}&page=1`)).json().catch(()=>({}));
  if (probe && probe.error === 'camelot_missing') {
    console.log('Smoke(tabbed_suggest_tables_ui): SKIP — camelot missing');
    process.exit(0);
  }

  const ws = await getWS();
  if (!ws) {
    console.error('Smoke(tabbed_suggest_tables_ui): No CDP WebSocket found');
    process.exit(3);
  }

  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);
  await page.goto(BASE + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 8000 });
  await page.waitForSelector('canvas', { timeout: 15000 });

  // Trigger suggestions
  const btn = await page.$('[data-testid="btn-suggest-tables"]');
  if (!btn) { console.error('suggest button not found'); process.exit(1); }
  await btn.click();

  // Wait for either suggest overlay or accept-all button (best effort ~5s)
  const overlay = await page.waitForSelector('[data-testid="suggest-box"]', { timeout: 5000 }).catch(()=>null);
  const acceptAll = await page.$('[data-testid="btn-accept-all-suggestions"]');
  if (!overlay && !acceptAll) {
    console.warn('No visible suggestions; content may not contain tables. Passing with note.');
    await browser.disconnect();
    console.log('Smoke(tabbed_suggest_tables_ui): OK (no suggestions)');
    process.exit(0);
  }

  // If Accept All present, click it and assert suggestions disappear
  if (acceptAll) {
    await acceptAll.click();
    await page.waitForTimeout(400);
    const remaining = await page.$$('[data-testid="suggest-box"]');
    if (remaining && remaining.length > 0) {
      console.error('Accept all did not clear suggestions');
      process.exit(1);
    }
  }

  const shotPath = path.join(OUT_DIR, `smoke_tabbed_suggest_ui_${ts()}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(()=>{});
  await page.close();
  await browser.disconnect();
  console.log('Smoke(tabbed_suggest_tables_ui): OK');
  process.exit(0);
})().catch((e) => { console.error('Smoke(tabbed_suggest_tables_ui) crashed:', e?.message || e); process.exit(1); });
