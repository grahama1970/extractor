#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const UI = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '') + '/main';
const API = (process.env.API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const OUT = path.resolve('scripts','artifacts'); fs.mkdirSync(OUT,{recursive:true});
const stamp = new Date().toISOString().replace(/[:.]/g,'-');
const SHOT = path.join(OUT, `ui_conflicts_load_and_resolve_${stamp}.png`);
const LOG = path.join(OUT, `ui_conflicts_load_and_resolve_${stamp}.log`);
const log = (m) => fs.appendFileSync(LOG, String(m)+'\n');

async function post(url, body){ const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); return r.json(); }
async function get(url){ const r = await fetch(url); return r.json(); }

(async () => {
  const browser = await puppeteer.launch({ headless:'new', args:['--no-sandbox','--disable-setuid-sandbox'] });
  let page;
  try {
    // Determine current docId used by UI by calling doc-id for default PDF
    const didResp = await get(`${API}/api/pipeline/doc-id?pdf_rel=${encodeURIComponent('BHT CV32A65X.pdf')}`);
    const docId = didResp && didResp.doc_id; if(!docId) throw new Error('no docId');
    // Seed a conflict artifact
    await post(`${API}/api/conflicts/save`, { doc_id: docId, items:[{ id:'c1', type:'duplicate', groupId:'tbl-001', resolved:false }] });

    page = await browser.newPage();
    await page.goto(UI, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 }).catch(()=>{});
    await page.waitForSelector('[data-testid="page-label"]', { timeout: 15000 });

    // Load conflicts (allow time for UI to compute docId)
    await new Promise(r=>setTimeout(r,900));
    await page.click('[data-testid="btn-load-conflicts"]');
    let item = await page.waitForSelector('[data-testid="conflict-item"]', { timeout: 4000 }).catch(()=>null);
    if (!item) {
      await new Promise(r=>setTimeout(r,1500));
      item = await page.$('[data-testid="conflict-item"]');
    }
    if (!item) throw new Error('no conflict item');
    await page.click('[data-testid="btn-adjudicate"]');

    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    log(`screenshot=${SHOT}`);
    console.log('OK ui_conflicts_load_and_resolve');
    process.exit(0);
  } catch (e) {
    if (page) await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    log(`error=${e?.message||e}`);
    console.error('FAIL ui_conflicts_load_and_resolve:', e?.message||e);
    process.exit(2);
  } finally { await browser.close().catch(()=>{}); }
})();
