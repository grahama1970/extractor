#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g,'-');
const NAME = 'ui_grouping_export_json';
const SHOT = path.join(OUT_DIR, `${NAME}_${stamp}.png`);
const LOG = path.join(OUT_DIR, `${NAME}_${stamp}.log`);
const log = (m) => fs.appendFileSync(LOG, String(m)+"\n");

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  let page;
  try {
    page = await browser.newPage();
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 }).catch(()=>{});
    await page.waitForSelector('[data-testid="page-label"]', { timeout: 15000 });
    // Jump to page 5 and ensure at least one box exists (draw one if needed)
    await page.evaluate(() => { try { /* @ts-ignore */ window.__ux?.setPage?.(5); } catch {} });
    await new Promise(r=>setTimeout(r,500));
    let firstBox = await page.$('[data-testid="box"]');
    if (!firstBox) {
      await page.evaluate(() => { try { /* @ts-ignore */ window.__ux?.drawBox?.(5, 0.2, 0.2, 0.6, 0.5); } catch {} });
      firstBox = await page.waitForSelector('[data-testid="box"]', { timeout: 3000 }).catch(()=>null);
    }
    if (!firstBox) throw new Error('no box found');
    await firstBox.click();
    // Set group id
    await page.focus('[data-testid="inspector-group-id"]');
    await page.keyboard.type('tbl-001', { delay: 10 });
    // Export JSON (prefer bottom button; fallback to top toolbar)
    const bottom = await page.$('[data-testid="btn-export-json"]');
    if (bottom) {
      await bottom.click();
    } else {
      const top = await page.$('[data-testid="btn-export-json-top"]');
      if (!top) throw new Error('No export button (top or bottom)');
      await top.click();
    }
    await page.waitForSelector('[data-testid="json-dialog"] textarea', { timeout: 10000 });
    const txt = await page.$eval('[data-testid="json-dialog"] textarea', el => el.value || '');
    log(`json_length=${txt.length}`);
    const parsed = JSON.parse(txt);
    const ok = parsed && Array.isArray(parsed.boxes) && parsed.boxes.length > 0 && typeof parsed.boxes[0].group_id === 'string';
    await page.screenshot({ path: SHOT, fullPage: true }).catch(()=>{});
    log(`screenshot=${SHOT}`);
    if (!ok) throw new Error('group_id missing in export');
    console.log('OK ui_grouping_export_json');
    process.exit(0);
  } catch (e) {
    if (page) await page.screenshot({ path: SHOT, fullPage: true }).catch(()=>{});
    log(`error=${e?.message||e}`);
    console.error('FAIL ui_grouping_export_json:', e?.message||e);
    process.exit(2);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
