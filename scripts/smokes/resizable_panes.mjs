import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }

async function getLeftWidth(page) {
  return page.$eval('div.border-r.bg-card.p-6.flex.flex-col', el => el.getBoundingClientRect().width);
}

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="handle-left"]', { timeout: 10000 });

  const before = await getLeftWidth(page);
  const handle = await page.$('[data-testid="handle-left"]');
  const box = await handle.boundingBox();
  await page.mouse.move(box.x + box.width/2, box.y + box.height/2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width/2 + 60, box.y + box.height/2, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(150);
  const after = await getLeftWidth(page);
  const grew = after > before + 20;

  // Reload and ensure persistence roughly holds
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="handle-left"]', { timeout: 10000 });
  const persisted = (await getLeftWidth(page)) >= after - 5;

  await browser.disconnect();
  if (!(grew && persisted)) { console.error('resizable_panes: FAIL', { before, after, grew, persisted }); process.exit(1); }
  console.log('resizable_panes: OK');
  process.exit(0);
})().catch((e) => { console.error('resizable_panes crashed:', e?.message || e); process.exit(2); });

