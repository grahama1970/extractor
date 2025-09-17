import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/classic';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
  page.setDefaultTimeout(20000);

  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  // open the dialog
  await page.waitForSelector('[data-testid="btn-open-pdf"]');
  await page.click('[data-testid="btn-open-pdf"]');
  await page.waitForSelector('[data-testid="open-dialog"]');
  await page.waitForSelector('[data-testid="open-item"]');

  const items = await page.$$('[data-testid="open-item"]');
  let ok = true; let reason = '';
  if (items.length === 0) { ok = false; reason = 'no_items'; }
  if (ok) {
    // check height ~48px
    const h = await items[0].evaluate((el) => el.getBoundingClientRect().height);
    if (!(h >= 46 && h <= 50)) { ok = false; reason = `row_height=${h}`; }
  }
  if (ok) {
    // ensure we applied a hover bg utility in className (static check, less flaky)
    const cls = await items[0].evaluate((el) => el.className || '');
    if (!/hover:bg-/.test(cls)) { ok = false; reason = `no_hover_class:${cls}`; }
  }

  const stamp = ts();
  const shot = path.join(OUT_DIR, `issue_018_${stamp}.png`);
  const log = path.join(OUT_DIR, `issue_018_${stamp}.log`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  fs.writeFileSync(log, [
    `BASE_URL=${BASE}`,
    `items=${items.length}`,
    ok ? 'ok=true' : `ok=false reason=${reason}`,
    `screenshot=${shot}`,
  ].join('\n'), 'utf-8');

  await browser.close();
  if (!ok) { console.error('issue_018: FAIL', reason); process.exit(1); }
  console.log('issue_018: OK');
})().catch(e => { console.error('issue_018 crashed:', e.message || e); process.exit(2); });
