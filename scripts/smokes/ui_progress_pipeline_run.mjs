#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g,'-');
const NAME = 'ui_progress_pipeline_run';
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
    // Start job via top toolbar run button
  const btn = await page.$('[data-testid="btn-run-pipeline"]');
  if (!btn) throw new Error('btn-run-pipeline missing');
  await page.$eval('[data-testid="btn-run-pipeline"]', (el) => el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })));
  const progress = await page.waitForSelector('[data-testid="pipeline-progress"]', { timeout: 6000 }).catch(()=>null);
    await page.screenshot({ path: SHOT, fullPage: true }).catch(()=>{});
    log(`screenshot=${SHOT}`);
    if (!progress) throw new Error('pipeline-progress not visible');
    console.log('OK ui_progress_pipeline_run');
    process.exit(0);
  } catch (e) {
    if (page) await page.screenshot({ path: SHOT, fullPage: true }).catch(()=>{});
    log(`error=${e?.message||e}`);
    console.error('FAIL ui_progress_pipeline_run:', e?.message||e);
    process.exit(2);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
