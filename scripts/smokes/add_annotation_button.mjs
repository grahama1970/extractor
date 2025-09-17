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
  // Prefer top toolbar button; fallback to header button
  const selectors = ['[data-testid="btn-add-annotation-top"]', '[data-testid="btn-add-annotation"]'];
  let clicked = false;
  for (const sel of selectors) {
    const el = await page.$(sel);
    if (el) { await el.click(); clicked = true; break; }
  }
  let opened = false;
  if (clicked) {
    opened = await page.waitForSelector('[data-testid="label-add-dialog"]', { timeout: 5000 }).then(()=>true).catch(()=>false);
    if (!opened) {
      opened = await page.waitForFunction(() => {
        const dlg = Array.from(document.querySelectorAll('div[role="dialog"] *')).find(el => /Add Label/i.test(el.textContent || ''));
        return !!dlg;
      }, { timeout: 5000 }).then(()=>true).catch(()=>false);
    }
  }
  const stamp = ts();
  const shot = path.join(OUT_DIR, `add_annotation_${stamp}.png`);
  const log = path.join(OUT_DIR, `add_annotation_${stamp}.log`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  fs.writeFileSync(log, [`BASE_URL=${BASE}`, `opened=${opened}`, `screenshot=${shot}`].join('\n'));
  await page.close(); await browser.disconnect();
  if (!opened) { console.error('Add label dialog not opened'); process.exit(1); }
  console.log('Smoke(add_annotation_button): OK');
  process.exit(0);
})().catch(e => { console.error('Smoke(add_annotation_button) crashed:', e.message || e); process.exit(2); });
