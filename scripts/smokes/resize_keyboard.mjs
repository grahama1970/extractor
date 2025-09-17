import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="handle-left"]', { timeout: 10000 });
  const before = await page.$eval('div.border-r.bg-card.p-6.flex.flex-col', el => el.getBoundingClientRect().width);
  await page.focus('[data-testid="handle-left"]');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(50);
  const after = await page.$eval('div.border-r.bg-card.p-6.flex.flex-col', el => el.getBoundingClientRect().width);
  await browser.disconnect();
  if (!(after > before)) { console.error('resize_keyboard: FAIL', { before, after }); process.exit(1); }
  console.log('resize_keyboard: OK');
  process.exit(0);
})().catch((e)=>{ console.error('resize_keyboard crashed:', e?.message || e); process.exit(2); });

