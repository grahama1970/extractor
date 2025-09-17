import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }
const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });

  // Draw and select a box
  await page.evaluate(() => { window.__ux?.drawBox?.(1, 0.20, 0.20, 0.50, 0.45, 'Table'); });
  await page.waitForSelector('[data-testid="box"]', { timeout: 8000 });
  const before = await page.$$eval('[data-testid="box"]', els => els.length);
  // Click the last box to ensure selected
  const boxes = await page.$$('[data-testid="box"]');
  if (boxes.length) await boxes[boxes.length-1].click();
  await page.keyboard.press('Delete');
  await new Promise(r => setTimeout(r, 300));
  const after = await page.$$eval('[data-testid="box"]', els => els.length);

  const stamp = ts();
  const shot = path.join(OUT_DIR, `delete_key_${stamp}.png`);
  const log = path.join(OUT_DIR, `delete_key_${stamp}.log`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  fs.writeFileSync(log, [`BASE_URL=${BASE}`, `before=${before}`, `after=${after}`, `screenshot=${shot}`].join('\n'));
  await page.close(); await browser.disconnect();
  if (!(after < before)) { console.error('Delete did not reduce box count'); process.exit(1); }
  console.log('Smoke(delete_keypress): OK');
  process.exit(0);
})().catch(e => { console.error('Smoke(delete_keypress) crashed:', e.message || e); process.exit(2); });
