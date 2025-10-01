import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '') + '/main';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

(async () => {
  const stamp = ts();
  const shot = path.join(OUT_DIR, `ui_inspector_${stamp}.png`);
  const logp = path.join(OUT_DIR, `ui_inspector_${stamp}.log`);
  const log = (m)=>fs.appendFileSync(logp, m+"\n");
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="inspector-pane"]', { timeout: 15000 });
    await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
    log(`BASE_URL=${BASE}`);
    log(`screenshot=${shot}`);
    console.log(JSON.stringify({ ok: true, selector: 'inspector-pane' }, null, 2));
  } catch (e) {
    log('crash=' + (e?.message||e));
    console.error('inspector pane smoke failed:', e?.message||e);
    process.exit(2);
  } finally { await browser.close().catch(()=>{}); }
})();
