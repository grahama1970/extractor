import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });

  // Draw a small box to ensure canvas present
  await page.waitForSelector('canvas', { timeout: 20000 });
  // Check labels absence and gap
  const result = await page.evaluate(() => {
    const h2s = Array.from(document.querySelectorAll('h2')); 
    const textList = h2s.map(h => (h.textContent || '').trim().toLowerCase());
    const hasExplorer = textList.some(t => t === 'explorer');
    const hasAnnotation = textList.some(t => t === 'annotation');
    const hasInspector = textList.some(t => t === 'inspector');
    const overlay = document.querySelector('[data-testid="overlay"]');
    const canvas = document.querySelector('canvas');
    let gapOk = false, gap = null;
    if (overlay && canvas) {
      const wrap = overlay.parentElement?.parentElement || overlay.parentElement;
      const wy = wrap?.getBoundingClientRect().top || 0;
      const cy = canvas.getBoundingClientRect().top;
      gap = Math.max(0, Math.round(cy - wy));
      gapOk = gap < 24;
    }
    return { hasExplorer, hasAnnotation, hasInspector, gap, gapOk };
  });

  const stamp = ts();
  const shot = path.join(OUT_DIR, `issue_013_${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  const log = path.join(OUT_DIR, `issue_013_${stamp}.log`);
  fs.writeFileSync(log, [
    `BASE_URL=${BASE}`,
    `hasExplorer=${result.hasExplorer}`,
    `hasAnnotation=${result.hasAnnotation}`,
    `hasInspector=${result.hasInspector}`,
    `gap=${result.gap}`,
    `gapOk=${result.gapOk}`,
    `screenshot=${shot}`
  ].join('\n'));
  await page.close(); await browser.disconnect();

  const ok = (!result.hasExplorer && !result.hasAnnotation && !result.hasInspector && result.gapOk);
  if (!ok) { console.error('issue_013: FAIL'); process.exit(1); }
  console.log('issue_013: OK');
  process.exit(0);
})().catch(e => { console.error('issue_013 crashed:', e.message || e); process.exit(2); });
