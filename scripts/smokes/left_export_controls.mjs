import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  // Wait for list
  await page.waitForSelector('[data-testid="file-list"]', { timeout: 10000 });
  // Click first real row to open PDF
  const row = await page.$('[data-testid="file-row"]');
  if (!row) { console.error('No file rows'); process.exit(1); }
  await row.click();
  // Expect single export trigger to exist; open menu and check items
  await page.waitForSelector('[data-testid="btn-export-left"]', { timeout: 10000 });
  await page.click('[data-testid="btn-export-left"]');
  await page.waitForSelector('[data-testid="item-export-json-left"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="item-export-pdf-left"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="item-export-base-left"]', { timeout: 10000 });
  console.log('left_export_controls: OK');
  await browser.disconnect();
  process.exit(0);
})().catch((e)=>{ console.error('left_export_controls crashed:', e?.message || e); process.exit(2); });
