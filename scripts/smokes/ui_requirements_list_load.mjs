import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const API = BASE.replace(/\/$/, '') + '/api/requirements/list';
const RESULTS_DIR = process.env.RESULTS_DIR || 'data/results/with_requirements_prove';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

(async () => {
  const stamp = ts();
  const shot = path.join(OUT_DIR, `ui_requirements_list_${stamp}.png`);
  const logp = path.join(OUT_DIR, `ui_requirements_list_${stamp}.log`);
  const log = (m)=>fs.appendFileSync(logp, m+"\n");

  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  try {
    const page = await browser.newPage();
    // Hit API via page.evaluate to reuse dev server/proxy cookies when applicable
    const url = API + `?results_dir=${encodeURIComponent(RESULTS_DIR)}`;
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    const data = await page.evaluate(async (u) => {
      const r = await fetch(u);
      return { status: r.status, json: await r.json() };
    }, url);
    log(`BASE_URL=${BASE}`);
    log(`URL=${url}`);
    log(`status=${data.status}`);
    log(`body=${JSON.stringify(data.json).slice(0,800)}`);
    await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
    fs.writeFileSync(path.join(OUT_DIR, `ui_requirements_list_${stamp}.json`), JSON.stringify(data.json, null, 2));
    if (!data.json?.ok) {
      console.error('requirements/list not ok');
      process.exit(2);
    }
    const n = (data.json?.requirements||[]).length;
    console.log(JSON.stringify({ ok: true, count: n }, null, 2));
  } catch (e) {
    log(`crash=${e?.message||e}`);
    console.error('UI req list smoke crashed:', e?.message||e);
    process.exit(3);
  } finally {
    await browser.close().catch(()=>{});
  }
})();

