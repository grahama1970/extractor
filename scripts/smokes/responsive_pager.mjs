import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws });
  const page = await browser.newPage();
  await page.setViewport({ width: 1024, height: 800 });
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  // On narrow, bottom pager visible, top hidden
  const topExistsNarrow = await page.$('[data-testid="pager-slider-top"]').then(Boolean);
  const bottomExistsNarrow = await page.$('[data-testid="pager-slider"]').then(Boolean);
  // Now switch to wide
  await page.setViewport({ width: 1440, height: 900 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  const topExistsWide = await page.$('[data-testid="pager-slider-top"]').then(Boolean);
  const bottomExistsWide = await page.$('[data-testid="pager-slider"]').then(Boolean);
  await browser.disconnect();
  const ok = (!topExistsNarrow && bottomExistsNarrow) && (topExistsWide && !bottomExistsWide);
  if (!ok) { console.error('responsive_pager: FAIL', { topExistsNarrow, bottomExistsNarrow, topExistsWide, bottomExistsWide }); process.exit(1); }
  console.log('responsive_pager: OK');
  process.exit(0);
})().catch((e)=>{ console.error('responsive_pager crashed:', e?.message || e); process.exit(2); });

