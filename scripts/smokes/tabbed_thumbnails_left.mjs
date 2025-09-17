import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() {
  try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {}
  return null;
}
const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.evaluateOnNewDocument(() => { try { localStorage.setItem('anno_thumb_mode','left'); } catch {} });
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });
  // Give thumbnails time to render
  await new Promise(r => setTimeout(r, 800));
  // Only count PNG thumbnails
  let pngSel = 'img[alt^="Page"][src^="data:image/png"]';
  const count = await page.$$eval(pngSel, els => els.length);
  const stamp = ts();
  const shot = path.join(OUT_DIR, `thumbs_left_${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  const logPath = path.join(OUT_DIR, `thumbs_left_${stamp}.log`);
  // Pixel check for non-trivial content
  const metrics = await page.evaluate((selector) => {
    const imgs = Array.from(document.querySelectorAll(selector)).slice(0, 4);
    const results = [];
    for (const img of imgs) {
      try {
        const el = img;
        const c = document.createElement('canvas');
        const w = Math.max(1, Math.min(120, el.naturalWidth || 120));
        const h = Math.max(1, Math.min(160, el.naturalHeight || 160));
        c.width = w; c.height = h;
        const ctx = c.getContext('2d');
        ctx.drawImage(el, 0, 0, w, h);
        const data = ctx.getImageData(0, 0, w, h).data;
        let nonWhite = 0; const total = w * h;
        for (let i = 0; i < data.length; i += 4) {
          const r = data[i], g = data[i+1], b = data[i+2], a = data[i+3];
          if (a > 0 && !(r > 248 && g > 248 && b > 248)) nonWhite++;
        }
        const ratio = nonWhite / total;
        results.push({ ratio });
      } catch (e) {
        results.push({ ratio: 0 });
      }
    }
    return results;
  }, pngSel);
  const good = (metrics || []).filter(m => (m.ratio || 0) > 0.02).length;

  fs.writeFileSync(logPath, [
    `BASE_URL=${BASE}`,
    `pngCount=${count}`,
    `goodThumbnails=${good}`,
    `metrics=${JSON.stringify(metrics)}`,
    `screenshot=${shot}`
  ].join('\n'));
  await page.close(); await browser.disconnect();
  if (count < 2 || good < 2) { console.error('left thumbnails insufficient or blank'); process.exit(1); }
  console.log('Smoke(tabbed_thumbnails_left): OK');
  process.exit(0);
})().catch(e => { console.error('Smoke(tabbed_thumbnails_left) crashed:', e.message || e); process.exit(2); });
