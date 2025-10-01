import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/main', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 15000 });
  const required = ['btn-first-top', 'btn-prev-top', 'btn-next-top', 'btn-last-top', 'page-label-top'];
  for (const id of required) {
    await page.waitForSelector(`[data-testid="${id}"]`, { timeout: 10000 });
  }
  // Basic interaction: click Next and ensure label updates to page 2
  await page.$eval('[data-testid="btn-next-top"]', (el) => (el instanceof HTMLElement ? el.click() : el.dispatchEvent(new MouseEvent('click', { bubbles: true }))));
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-testid="page-label-top"]');
    return el && /\b2\s*\/\s*\d+/.test(el.textContent || '');
  }, { timeout: 2000 });
  const label = await page.$eval('[data-testid="page-label-top"]', el => el.textContent || '');
  await browser.disconnect();
  if (!/2\s*\/\s*\d+/.test(label)) { console.error('page_controls_top_toolbar: FAIL', { label }); process.exit(1); }
  console.log('page_controls_top_toolbar: OK');
  process.exit(0);
})().catch((e) => { console.error('page_controls_top_toolbar crashed:', e?.message || e); process.exit(2); });
