import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8100';
const URL = BASE.replace(/\/$/, '') + '/main';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

(async () => {
  const stamp = ts();
  const shot = path.join(OUT_DIR, `ui_requirements_pane_dom_${stamp}.png`);
  const logp = path.join(OUT_DIR, `ui_requirements_pane_dom_${stamp}.log`);
  const log = (m)=>fs.appendFileSync(logp, m+"\n");
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="req-pane"]', { timeout: 20000 });
    // click refresh to populate
    const hasRefresh = await page.$('[data-testid="req-refresh"]');
    if (hasRefresh) await page.click('[data-testid="req-refresh"]');
    await new Promise((r)=>setTimeout(r,800));
    const count = await page.$$eval('[data-testid="req-item"]', els => els.length).catch(()=>0);
    log(`count=${count}`);
    await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
    console.log(JSON.stringify({ ok: true, count }, null, 2));
  } catch (e) {
    log(`crash=${e?.message||e}`);
    console.error('UI req pane DOM smoke crashed:', e?.message||e);
    process.exit(3);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
