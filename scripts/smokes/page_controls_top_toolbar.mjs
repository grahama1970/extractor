import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 10000 });
  const required = ['btn-first-top', 'btn-prev-top', 'pager-slider-top', 'btn-next-top', 'btn-last-top'];
  for (const id of required) {
    await page.waitForSelector(`[data-testid="${id}"]`, { timeout: 10000 });
  }
  // Basic interaction: move slider to 2, ensure label updates
  await page.$eval('[data-testid="pager-slider-top"]', (el) => { el.value = '2'; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); });
  const label = await page.$eval('[data-testid="page-label-top"]', el => el.textContent || '');
  await browser.disconnect();
  if (!/2\s*\/\s*\d+/.test(label)) { console.error('page_controls_top_toolbar: FAIL', { label }); process.exit(1); }
  console.log('page_controls_top_toolbar: OK');
  process.exit(0);
})().catch((e) => { console.error('page_controls_top_toolbar crashed:', e?.message || e); process.exit(2); });

