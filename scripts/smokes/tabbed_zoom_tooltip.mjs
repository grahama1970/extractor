import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() {
  try {
    const res = await fetch(DISCOVERY);
    const j = await res.json();
    if (j && j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0', '127.0.0.1');
  } catch {}
  return null;
}

(async () => {
  const ws = await getWS();
  if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);

  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 8000 });

  // Zoom should be top only
  const zTop = await page.$('[data-testid="zoom-top"]');
  if (!zTop) { console.error('zoom-top missing'); process.exit(1); }
  const zBot = await page.$('[data-testid="zoom-bottom"]');
  if (zBot) { console.error('zoom-bottom present (should be removed)'); process.exit(1); }

  // Tooltips: ensure top toolbar buttons have title attributes or aria-labels
  const hasTitles = await page.evaluate(() => {
    const tb = document.querySelector('[data-testid="top-toolbar"]');
    if (!tb) return false;
    const btns = Array.from(tb.querySelectorAll('button'));
    return btns.some(b => b.getAttribute('title'));
  });
  if (!hasTitles) { console.error('No button titles in top toolbar'); process.exit(1); }

  console.log('Smoke(tabbed_zoom_tooltip): OK');
  await page.close();
  await browser.disconnect();
  process.exit(0);
})().catch((e) => { console.error('Smoke(tabbed_zoom_tooltip) crashed:', e); process.exit(2); });
