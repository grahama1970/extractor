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
  await page.goto(BASE.replace(/\/$/, '') + '/main', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });
  // Hover first/next and check tooltips
  const firstHasTitle = await page.$eval('[data-testid="btn-first"]', el => !!el.getAttribute('title')).catch(()=>false);
  const nextHasTitle = await page.$eval('[data-testid="btn-next"]', el => !!el.getAttribute('title')).catch(()=>false);
  // Also attempt ShadCN tooltip text if present
  await page.hover('[data-testid="btn-first"]');
  const okFirstTT = await page.waitForFunction(() => /First page/i.test(document.body.innerText), { timeout: 1500 }).then(()=>true).catch(()=>false);
  await page.hover('[data-testid="btn-next"]');
  const okNextTT = await page.waitForFunction(() => /Next page/i.test(document.body.innerText), { timeout: 1500 }).then(()=>true).catch(()=>false);
  const okFirst = firstHasTitle || okFirstTT;
  const okNext = nextHasTitle || okNextTT;
  const stamp = ts();
  const shot = path.join(OUT_DIR, `tooltips_controls_${stamp}.png`);
  const log = path.join(OUT_DIR, `tooltips_controls_${stamp}.log`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  fs.writeFileSync(log, [
    `BASE_URL=${BASE}`,
    `first=${okFirst}`,
    `next=${okNext}`,
    `firstHasTitle=${firstHasTitle}`,
    `nextHasTitle=${nextHasTitle}`,
    `screenshot=${shot}`
  ].join('\n'));
  await page.close(); await browser.disconnect();
  if (!(okFirst && okNext)) { console.error('Control tooltips missing'); process.exit(1); }
  console.log('Smoke(tooltips_controls): OK');
  process.exit(0);
})().catch(e => { console.error('Smoke(tooltips_controls) crashed:', e.message || e); process.exit(2); });
