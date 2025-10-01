#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g,'-');
const NAME = 'ui_export_json_fields';
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
  // Ensure at least one box exists (draw if needed)
  const hasBox = await page.$('[data-testid="box"]');
  if (!hasBox) {
    await page.evaluate(() => { try { /* @ts-ignore */ window.__ux?.setPage?.(5); } catch {} });
    await new Promise(r=>setTimeout(r,500));
    await page.evaluate(() => { try { /* @ts-ignore */ window.__ux?.drawBox?.(5, 0.2, 0.2, 0.6, 0.5); } catch {} });
    await page.waitForSelector('[data-testid="box"]', { timeout: 3000 }).catch(()=>{});
  }
    await page.evaluate(() => { try { /* @ts-ignore */ window.__ux?.setPage?.(5); } catch {} });
    await new Promise(r=>setTimeout(r,200));
    // Prefer bottom export button; fall back to top toolbar export if missing
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
    const first = parsed && parsed.boxes && parsed.boxes[0];
    const ok = first && typeof first.type === 'string' && typeof first.instance_id === 'string' && typeof first.group_id === 'string' && Array.isArray(first.bounding_box) && first.bounding_box.length === 4;
    await page.screenshot({ path: SHOT, fullPage: true }).catch(()=>{});
    log(`screenshot=${SHOT}`);
    if (!ok) throw new Error('required fields missing in export');
    console.log('OK ui_export_json_fields');
    process.exit(0);
  } catch (e) {
    if (page) await page.screenshot({ path: SHOT, fullPage: true }).catch(()=>{});
    log(`error=${e?.message||e}`);
    console.error('FAIL ui_export_json_fields:', e?.message||e);
    process.exit(2);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
