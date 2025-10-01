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
  const shot = path.join(OUT_DIR, `ui_req_edit_${stamp}.png`);
  const logp = path.join(OUT_DIR, `ui_req_edit_${stamp}.log`);
  const log = (m)=>fs.appendFileSync(logp, m+"\n");
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    const LIST = BASE.replace(/\/$/, '') + '/api/requirements/list?results_dir=' + encodeURIComponent(RESULTS_DIR);
    let data = await page.evaluate(async (u) => { const r=await fetch(u); return await r.json(); }, LIST);
    if (!data?.ok || !Array.isArray(data.requirements) || data.requirements.length === 0) {
      console.error('no requirements to edit');
      process.exit(2);
    }
    const r0 = data.requirements[0];
    const edited = (r0.text_canonical || '').slice(0,120) + ' [edit]';
    const SAVE = BASE.replace(/\/$/, '') + '/api/requirements/save';
    const payload = { results_dir: RESULTS_DIR, edits: [{ id: r0.id, text_canonical: edited }] };
    const saved = await page.evaluate(async (u, body) => {
      const r = await fetch(u, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
      return await r.json();
    }, SAVE, payload);
    log(`save=${JSON.stringify(saved)}`);
    data = await page.evaluate(async (u) => { const r=await fetch(u); return await r.json(); }, LIST);
    fs.writeFileSync(path.join(OUT_DIR, `ui_req_edit_result_${stamp}.json`), JSON.stringify({ before: r0, after: data.requirements.find(x=>x.id===r0.id) }, null, 2));
    await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
    console.log(JSON.stringify({ ok: true, edited: r0.id }, null, 2));
  } catch (e) {
    log(`crash=${e?.message||e}`);
    console.error('UI req edit smoke crashed:', e?.message||e);
    process.exit(3);
  } finally {
    await browser.close().catch(()=>{});
  }
})();

