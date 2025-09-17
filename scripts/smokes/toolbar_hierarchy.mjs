import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="btn-open-pdf"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="btn-generate-inspector"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="btn-export-all"]', { timeout: 10000 });

  const hasSolidBg = async (sel) => page.$eval(sel, (el) => {
    const cs = getComputedStyle(el);
    // Consider non-transparent bg as primary (simplified heuristic)
    return cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent';
  });

  const openPdfSolid = await hasSolidBg('[data-testid="btn-open-pdf"]');
  const genSolid = await hasSolidBg('[data-testid="btn-generate-inspector"]');
  const exportAllSolid = await hasSolidBg('[data-testid="btn-export-all"]');

  await browser.disconnect();

  const ok = openPdfSolid && genSolid && exportAllSolid;
  if (!ok) {
    console.error('toolbar_hierarchy: FAIL', { openPdfSolid, genSolid, exportAllSolid });
    process.exit(1);
  }
  console.log('toolbar_hierarchy: OK');
  process.exit(0);
})().catch((e) => { console.error('toolbar_hierarchy crashed:', e?.message || e); process.exit(2); });

