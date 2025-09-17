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
  // Fallback-tag targets by text if testids missing
  await page.evaluate(() => {
    const tag = (txt, attr) => {
      const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent || '').trim() === txt);
      if (btn && !btn.hasAttribute(attr)) btn.setAttribute(attr, '1');
    };
    tag('Sec','data-tt-sec');
    tag('Tbl','data-tt-tbl');
  });
  const secSel = '[data-testid="btn-type-sec"], [data-tt-sec="1"]';
  const tblSel = '[data-testid="btn-type-tbl"], [data-tt-tbl="1"]';
  await page.hover(secSel);
  const okSec = await page.waitForFunction(() => /Section label/i.test(document.body.innerText), { timeout: 3000 }).then(()=>true).catch(()=>false);
  await page.hover(tblSel);
  const okTbl = await page.waitForFunction(() => /Table label/i.test(document.body.innerText), { timeout: 3000 }).then(()=>true).catch(()=>false);
  const stamp = ts();
  const shot = path.join(OUT_DIR, `tooltips_types_${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  const log = path.join(OUT_DIR, `tooltips_types_${stamp}.log`);
  fs.writeFileSync(log, [`BASE_URL=${BASE}`, `sec=${okSec}`, `tbl=${okTbl}`, `screenshot=${shot}`].join('\n'));
  await page.close(); await browser.disconnect();
  if (!(okSec && okTbl)) { console.error('Type tooltips missing'); process.exit(1); }
  console.log('Smoke(tooltips_types): OK');
  process.exit(0);
})().catch(e => { console.error('Smoke(tooltips_types) crashed:', e.message || e); process.exit(2); });
