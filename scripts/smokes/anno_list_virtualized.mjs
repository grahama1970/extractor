import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  // Jump to seeded page 5
  await page.waitForSelector('[data-testid="pager-slider"]', { timeout: 10000 });
  await page.$eval('[data-testid="pager-slider"]', (el) => { el.value = '5'; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForSelector('[data-testid="anno-list"]', { timeout: 10000 });
  // At least one row should render for the seeded boxes
  const rows = await page.$$('[data-testid="anno-row"]');
  await browser.disconnect();
  if (!rows || rows.length < 1) { console.error('anno_list_virtualized: FAIL', { rows: rows?.length || 0 }); process.exit(1); }
  console.log('anno_list_virtualized: OK');
  process.exit(0);
})().catch((e)=>{ console.error('anno_list_virtualized crashed:', e?.message || e); process.exit(2); });

