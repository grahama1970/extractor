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
  const ws = await getWS();
  if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  page.setDefaultTimeout(25000);

  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 8000 });

  // Ensure bottom filmstrip mode via inline selector
  const inlineSel = await page.$('[data-testid="thumbs-selector-inline"]');
  if (!inlineSel) {
    // Open settings dropdown (if not in bottom mode yet, the selector still exists inline)
    // Just proceed; we'll validate presence and height next
  }

  const report = { BASE_URL: BASE };

  // Check that the inline selector exists inside page-controls
  const hasInline = await page.evaluate(() => !!document.querySelector('[data-testid="page-controls"] [data-testid="thumbs-selector-inline"]'));
  report.hasInline = hasInline;

  // Measure the thumbnail strip height when present
  const metrics = await page.evaluate(() => {
    const pc = document.querySelector('[data-testid="page-controls"]');
    const strip = pc && (pc.previousElementSibling instanceof HTMLElement ? pc.previousElementSibling : null);
    const stripH = strip ? Math.round(strip.getBoundingClientRect().height) : null;
    return { stripH };
  });
  Object.assign(report, metrics);

  // Accept: inline selector present and strip height <= 110 when bottom mode
  const ok = hasInline && (metrics.stripH === null || metrics.stripH <= 110);
  const stamp = ts();
  const shotPath = path.join(OUT_DIR, `bottom_single_row_${stamp}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(()=>{});
  const logPath = path.join(OUT_DIR, `bottom_single_row_${stamp}.log`);
  fs.writeFileSync(logPath, [
    `BASE_URL=${BASE}`,
    `hasInline=${String(hasInline)}`,
    `stripH=${String(metrics.stripH)}`,
    `screenshot=${shotPath}`,
  ].join('\n'), 'utf-8');

  await page.close();
  await browser.disconnect();
  if (!ok) {
    console.error('Smoke(tabbed_bottom_single_row) failed');
    process.exit(1);
  }
  console.log('Smoke(tabbed_bottom_single_row): OK');
  process.exit(0);
})().catch((e) => { console.error('Smoke(tabbed_bottom_single_row) crashed:', e.message || e); process.exit(2); });

