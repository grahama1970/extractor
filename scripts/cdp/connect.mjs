// Connect to a CDP endpoint and open a page. Run with:
//   CDP_ORIGIN=http://127.0.0.1:9222 TEST_URL=http://127.0.0.1:8080/classic node scripts/cdp/connect.mjs
import puppeteer from 'puppeteer-core';

async function discoverWS(origin, token) {
  const url = token ? `${origin.replace(/\/$/, '')}/json/version?token=${token}`
                    : `${origin.replace(/\/$/, '')}/json/version`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Discovery failed: ${res.status}`);
  const j = await res.json();
  if (!j || !j.webSocketDebuggerUrl) throw new Error('webSocketDebuggerUrl missing');
  return j.webSocketDebuggerUrl.replace('0.0.0.0', '127.0.0.1');
}

(async () => {
  const origin = process.env.CDP_ORIGIN || 'http://127.0.0.1:9222';
  const token = process.env.CDP_TOKEN || '';
  const testUrl = process.env.TEST_URL || 'http://127.0.0.1:8080/classic';
  const ws = await discoverWS(origin, token);
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(testUrl, { waitUntil: 'domcontentloaded' });
  console.log('Connected & loaded:', testUrl);
  await browser.disconnect();
})().catch((e) => { console.error('connect.mjs failed:', e?.message || e); process.exit(1); });

