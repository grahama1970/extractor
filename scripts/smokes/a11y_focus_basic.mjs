import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

async function hasFocusRing(page, selector) {
  return page.$eval(selector, (el) => {
    el.focus();
    const cs = getComputedStyle(el);
    // Look for a visible outline or non-empty box-shadow applied by focus-visible
    const outlineVisible = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth || '0') > 0;
    const shadow = cs.boxShadow || '';
    return outlineVisible || (shadow && shadow !== 'none');
  }).catch(()=>false);
}

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="btn-open-pdf"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="toggle-exact-json"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="pager-slider"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="handle-left"]', { timeout: 10000 });

  const b1 = await hasFocusRing(page, '[data-testid="btn-open-pdf"]');
  const sw = await hasFocusRing(page, '[data-testid="toggle-exact-json"]');
  const ps = await hasFocusRing(page, '[data-testid="pager-slider"]');
  const hl = await hasFocusRing(page, '[data-testid="handle-left"]');

  await browser.disconnect();
  const ok = b1 && sw && ps && hl;
  if (!ok) { console.error('a11y_focus_basic: FAIL', { b1, sw, ps, hl }); process.exit(1); }
  console.log('a11y_focus_basic: OK');
  process.exit(0);
})().catch((e)=>{ console.error('a11y_focus_basic crashed:', e?.message || e); process.exit(2); });

