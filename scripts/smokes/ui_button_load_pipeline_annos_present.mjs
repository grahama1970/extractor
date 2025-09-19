#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_button_load_pipeline_annos_present';
const SHOT = path.join(OUT_DIR, `${NAME}_${stamp}.png`);
const LOG = path.join(OUT_DIR, `${NAME}_${stamp}.log`);

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
  page.setDefaultTimeout(20000);
  try {
    await page.goto(URL, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 });
    await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 15000 });
    const btn = await page.waitForSelector('[data-testid="btn-load-pipeline-annos"]', { timeout: 10000 });
    const visible = btn && await btn.isIntersectingViewport();
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `present=${!!btn}\nvisible=${!!visible}\nscreenshot=${SHOT}\n`, 'utf-8');
    if (!btn || !visible) throw new Error('Load pipeline annos button missing or not visible');
    console.log('OK ui_button_load_pipeline_annos_present');
    process.exit(0);
  } catch (e) {
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `error=${e?.message||e}\nscreenshot=${SHOT}\n`, 'utf-8');
    console.error('FAIL ui_button_load_pipeline_annos_present:', e?.message||e);
    process.exit(2);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
