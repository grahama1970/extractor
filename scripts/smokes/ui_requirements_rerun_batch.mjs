import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const OUT_DIR = path.resolve('scripts','artifacts');
const RESULTS_DIR = process.env.RESULTS_DIR || 'data/results/with_requirements_prove';
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

(async () => {
  const stamp = ts();
  const shot = path.join(OUT_DIR, `ui_req_rerun_${stamp}.png`);
  const logp = path.join(OUT_DIR, `ui_req_rerun_${stamp}.log`);
  const log = (m)=>fs.appendFileSync(logp, m+"\n");
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    const RERUN = BASE.replace(/\/$/, '') + '/api/requirements/rerun';
    const payload = { results_dir: RESULTS_DIR };
    const resp = await page.evaluate(async (u, body) => {
      const r = await fetch(u, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
      return await r.json();
    }, RERUN, payload);
    log(`rerun=${JSON.stringify(resp)}`);
    // Fetch list again to ensure API responds after rerun
    const LIST = BASE.replace(/\/$/, '') + '/api/requirements/list?results_dir=' + encodeURIComponent(RESULTS_DIR);
    const data = await page.evaluate(async (u) => { const r=await fetch(u); return await r.json(); }, LIST);
    fs.writeFileSync(path.join(OUT_DIR, `ui_req_rerun_result_${stamp}.json`), JSON.stringify({ rerun: resp, list: data }, null, 2));
    await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
    if (!resp?.ok) { console.error('rerun not ok'); process.exit(2); }
    console.log(JSON.stringify({ ok: true }, null, 2));
  } catch (e) {
    log(`crash=${e?.message||e}`);
    console.error('UI req rerun smoke crashed:', e?.message||e);
    process.exit(3);
  } finally {
    await browser.close().catch(()=>{});
  }
})();

