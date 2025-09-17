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
  const sel = '[data-testid="btn-add-annotation-top"]';
  const exists = await page.$(sel).then(x=>!!x);
  const headerExists = await page.$('[data-testid="btn-add-annotation"]').then(x=>!!x);
  const stamp = ts();
  const shot = path.join(OUT_DIR, `add_top_menu_${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  const log = path.join(OUT_DIR, `add_top_menu_${stamp}.log`);
  // Tooltip assertion: hover and search for tooltip content or title fallback
  let tipOk = false;
  if (exists) {
    const hasTitle = await page.$eval(sel, el => !!el.getAttribute('title')).catch(()=>false);
    await page.hover(sel).catch(()=>{});
    tipOk = await page.waitForFunction(() => {
      const txt = document.body.innerText || '';
      if (/Add label type/i.test(txt)) return true;
      const tips = Array.from(document.querySelectorAll('[role="tooltip"], [data-radix-tooltip-content]'));
      return tips.some(t => /Add label type/i.test(t.textContent || ''));
    }, { timeout: 1500 }).then(()=>true).catch(()=>false);
    tipOk = tipOk || hasTitle;
  }

  fs.writeFileSync(log, [`BASE_URL=${BASE}`, `exists=${exists}`, `tooltip=${tipOk}`, `headerExists=${headerExists}`, `screenshot=${shot}`].join('\n'));
  await page.close(); await browser.disconnect();
  if (headerExists) { console.error('Legacy header Add Label button still present'); process.exit(1); }
  if (!(exists && tipOk)) { console.error('Add Label top button or tooltip missing'); process.exit(1); }
  console.log('Smoke(add_annotation_top_menu): OK');
  process.exit(0);
})().catch(e => { console.error('Smoke(add_annotation_top_menu) crashed:', e.message || e); process.exit(2); });
