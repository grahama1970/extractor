import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:9222/json/version';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() {
  try {
    const res = await fetch(DISCOVERY);
    const j = await res.json();
    if (j && j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0', '127.0.0.1');
  } catch {}
  return null;
}

const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  // Preflight: ensure mock endpoint responds
  try {
    const mockPing = await fetch(BASE.replace(/\/[^/]*$/, '') + '/api/ux/mock/generate', { method: 'POST' });
    if (!mockPing.ok) {
      console.warn('Mock generate not available; skipping smoke.');
      process.exit(0);
    }
  } catch {
    console.warn('Mock generate not reachable; skipping smoke.');
    process.exit(0);
  }

  const ws = await getWS();
  if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);

  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 8000 });
  await page.waitForSelector('canvas', { timeout: 15000 });

  // Draw a sample box via dev hook
  await page.evaluate(() => { window.__ux?.drawBox?.(1, 0.1, 0.1, 0.6, 0.4, 'Table'); });

  // Click Generate JSON
  const clicked = await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent || '').includes('Generate JSON'));
    if (btn) { (btn).click(); return true; }
    return false;
  });
  if (!clicked) throw new Error('Generate JSON button not found');

  // Wait for the JSON dialog to appear
  await page.waitForSelector('textarea', { timeout: 20000 });
  const text = await page.$eval('textarea', el => el.value || el.textContent || '');
  if (!/\bcolumns\b/.test(text) || !/\bdata\b/.test(text)) {
    throw new Error('Generated JSON did not include expected keys');
  }

  const shot = path.join(OUT_DIR, `smoke_generate_json_${ts()}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  await page.close();
  await browser.disconnect();
  console.log('Smoke(tabbed_generate_json_mock): OK');
  process.exit(0);
})().catch((e) => { console.error('Smoke(tabbed_generate_json_mock) failed:', e.message || e); process.exit(1); });
