import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const URL = BASE.replace(/\/$/, '') + '/main';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

function logLine(file, line){
  fs.appendFileSync(file, String(line) + '\n');
}

(async () => {
  const stamp = ts();
  const shot = path.join(OUT_DIR, `ui_extract_load_${stamp}.png`);
  const logp = path.join(OUT_DIR, `ui_extract_load_${stamp}.log`);
  logLine(logp, `BASE_URL=${BASE}`);
  let consoleErrors = 0;
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  try {
    const page = await browser.newPage();
    page.on('console', msg => {
      const type = msg.type();
      if (type === 'error') { consoleErrors++; logLine(logp, `[console.error] ${msg.text()}`); }
    });
    page.on('pageerror', err => { consoleErrors++; logLine(logp, `[pageerror] ${err?.message||err}`); });

    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="page-label"]', { timeout: 15000 });
    // Verify top toolbar mounted (buttons can be conditionally rendered)
    await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 15000 });
    // Assert core buttons present
    await page.waitForSelector('[data-testid="btn-extract-pipeline"]', { timeout: 15000 });
    await page.waitForSelector('[data-testid="btn-load-pipeline-annos"]', { timeout: 15000 });

    // Try to arm draw and drag a small box (best-effort; ignore errors)
    try {
      await page.keyboard.press('KeyN');
      const r = await page.evaluate(() => document.body.getBoundingClientRect());
      await page.mouse.move(r.left + 400, r.top + 300);
      await page.mouse.down();
      await page.mouse.move(r.left + 520, r.top + 380, { steps: 8 });
      await page.mouse.up();
      logLine(logp, 'drawAttempt=1');
    } catch {}

    await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
    logLine(logp, `screenshot=${shot}`);
    logLine(logp, `consoleErrors=${consoleErrors}`);
    if (consoleErrors > 0) {
      console.error('UI smoke: FAIL due to console errors');
      process.exit(2);
    }
    console.log('UI smoke: OK');
  } catch (e) {
    logLine(logp, `crash=${e?.message||e}`);
    console.error('UI smoke crashed:', e?.message||e);
    process.exit(3);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
