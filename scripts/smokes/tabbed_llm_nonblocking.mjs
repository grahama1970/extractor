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
  await page.evaluateOnNewDocument(() => { try { localStorage.setItem('anno_generate_nb','1'); } catch {} });
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });
  await page.waitForSelector('canvas', { timeout: 20000 });

  // Draw a box and click Generate JSON
  await page.evaluate(() => { window.__ux?.drawBox?.(1, 0.18, 0.18, 0.55, 0.48, 'Table'); });
  const clicked = await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent || '').includes('Generate JSON'));
    if (btn) { (btn).click(); return true; }
    return false;
  });
  if (!clicked) { console.error('Generate JSON button not found'); process.exit(1); }

  // Expect non-blocking chip to appear; while it is visible, try to navigate next page
  const chip = await page.waitForSelector('[data-testid="llm-chip"]', { timeout: 10000 }).catch(()=>null);
  // Ensure non-blocking toggle is not present
  const hasToggle = await page.$('[data-testid="switch-nonblock"]').then(x=>!!x).catch(()=>false);
  const labelBefore = await page.$eval('[data-testid="page-label"]', el => el.textContent || '');
  // Click Next Page
  const nextBtn = await page.$('[data-testid="btn-next"]'); if (nextBtn) await nextBtn.click();
  // Allow some time for UI to update
  await new Promise(r => setTimeout(r, 400));
  const labelAfter = await page.$eval('[data-testid="page-label"]', el => el.textContent || '');
  const chipSeen = !!chip;
  const navigated = labelBefore !== labelAfter;

  const stamp = ts();
  const shot = path.join(OUT_DIR, `llm_nonblocking_${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  const log = path.join(OUT_DIR, `llm_nonblocking_${stamp}.log`);
  fs.writeFileSync(log, [`BASE_URL=${BASE}`, `chipSeen=${chipSeen}`, `navigated=${navigated}`, `hasToggle=${hasToggle}`, `screenshot=${shot}`].join('\n'));
  await page.close(); await browser.disconnect();
  if (!(chipSeen && navigated) || hasToggle) { console.error('Non-blocking LLM check failed (toggle should be absent)'); process.exit(1); }
  console.log('Smoke(tabbed_llm_nonblocking): OK');
  process.exit(0);
})().catch(e => { console.error('Smoke(tabbed_llm_nonblocking) crashed:', e.message || e); process.exit(2); });
