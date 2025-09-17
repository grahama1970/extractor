import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() {
  try {
    const r = await fetch(DISCOVERY);
    const j = await r.json();
    if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1');
  } catch {}
  return null;
}

(async () => {
  const ws = await getWS();
  if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (msg) => {
    const type = msg.type();
    if (type === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => pageErrors.push(err?.message || String(err)));

  const url = BASE.replace(/\/$/, '') + '/classic';
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
  } catch (e) {
    consoleErrors.push('Navigation failed: ' + (e?.message || e));
  }
  // Give the app a moment to mount/hydrate
  await new Promise((r) => setTimeout(r, 1200));

  const errs = consoleErrors.concat(pageErrors);
  if (errs.length) {
    console.error('console_errors: FAIL');
    for (const e of errs) console.error(' -', e);
    await browser.disconnect();
    process.exit(1);
  }
  console.log('console_errors: OK');
  await browser.disconnect();
  process.exit(0);
})().catch((e) => { console.error('console_errors crashed:', e?.message || e); process.exit(2); });
