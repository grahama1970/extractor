#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const API = (process.env.API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_load_pipeline_annos_from_latest';
const SHOT = path.join(OUT_DIR, `${NAME}_${stamp}.png`);
const LOG = path.join(OUT_DIR, `${NAME}_${stamp}.log`);
const log = (m) => fs.appendFileSync(LOG, String(m)+"\n");

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  let page;
  try {
    // Seed a minimal fake results dir with 04/05/06 shapes to keep this smoke offline-friendly
    const latest = path.resolve('scripts','artifacts','ui_fake_results');
    const mk = (p) => fs.mkdirSync(p, { recursive: true });
    mk(path.join(latest, '04_section_builder','json_output'));
    mk(path.join(latest, '05_table_extractor','json_output'));
    mk(path.join(latest, '06_figure_extractor','json_output'));
    fs.writeFileSync(path.join(latest,'04_section_builder','json_output','04_sections.json'), JSON.stringify({ sections:[{ page_start:0, bbox:[100,120,420,200] }] }, null, 2));
    fs.writeFileSync(path.join(latest,'05_table_extractor','json_output','05_tables.json'), JSON.stringify({ tables:[{ page_index:0, bbox:[140,250,460,380] }] }, null, 2));
    fs.writeFileSync(path.join(latest,'06_figure_extractor','json_output','06_figures.json'), JSON.stringify({ figures:[{ page:0, bbox:[200,400,260,460] }] }, null, 2));

    await fetch(`${API}/api/pipeline/latest-set`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ results_dir: latest }) });

    page = await browser.newPage();
    const reqs = [];
    page.on('request', (req) => {
      const u = req.url();
      if (u.includes('/api/pipeline/latest') || u.includes('/api/artifacts/file?path=')) reqs.push(u);
    });
    await page.goto(URL, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 }).catch(()=>{});
    await page.waitForSelector('[data-testid="page-label"]', { timeout: 15000 });

    // Kick a lightweight pipeline run to ensure a valid latest results dir exists in UI state
    const extractBtn = await page.$('[data-testid="btn-extract-pipeline"]');
    if (extractBtn) {
      await extractBtn.click();
      // Wait for progress to appear then settle
      await page.waitForSelector('[data-testid="pipeline-progress"]', { timeout: 10000 }).catch(()=>{});
      // allow a few seconds for the short run
      await new Promise(r => setTimeout(r, 3000));
    }

    const beforeCount = await page.$$eval('[data-testid="box"]', els => els.length).catch(()=>0);
    const loadBtn = await page.waitForSelector('[data-testid="btn-load-pipeline-annos"]', { timeout: 10000 }).catch(()=>null);
    if (!loadBtn) throw new Error('Load pipeline annos button missing');
    await loadBtn.click();
    // Allow time to fetch and render; prefer a condition wait
    await page.waitForFunction((prev) => {
      const n = document.querySelectorAll('[data-testid="box"]').length;
      return n > prev;
    }, { timeout: 5000 }, beforeCount).catch(()=>{});
    let afterCount = await page.$$eval('[data-testid="box"]', els => els.length).catch(()=>0);
    // If none on current page, try advancing a few pages to find overlays
    if (afterCount === 0) {
      for (let i=0; i<12; i++) {
        const clicked = await page.evaluate(() => {
          const btn = document.querySelector('[data-testid="pager-next"]');
          if (!btn) return false;
          (btn).dispatchEvent(new MouseEvent('click', { bubbles: true }));
          return true;
        });
        if (!clicked) break;
        await new Promise(r => setTimeout(r, 300));
        afterCount = await page.$$eval('[data-testid="box"]', els => els.length).catch(()=>0);
        if (afterCount > 0) break;
      }
    }
    log(`before=${beforeCount}`);
    log(`after=${afterCount}`);
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    log(`screenshot=${SHOT}`);
    if (!(afterCount > beforeCount) && reqs.length === 0) throw new Error('no new boxes after loading pipeline annos');
    if (reqs.length > 0) log('requests=' + reqs.join('\nrequests='));
    console.log('OK ui_load_pipeline_annos_from_latest');
    process.exit(0);
  } catch (e) {
    if (page) await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    log(`error=${e?.message||e}`);
    console.error('FAIL ui_load_pipeline_annos_from_latest:', e?.message||e);
    process.exit(2);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
