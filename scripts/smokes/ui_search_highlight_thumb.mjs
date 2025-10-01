#!/usr/bin/env node
import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_search_highlight_thumb';
const SHOT = path.join(OUT_DIR, `${NAME}_${stamp}.png`);
const LOG = path.join(OUT_DIR, `${NAME}_${stamp}.log`);

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args:['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  try {
    await page.goto(URL, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 });
    await page.waitForSelector('[data-testid="search-input"]', { timeout: 15000 });
    await page.click('[data-testid="search-input"]');
    await page.type('[data-testid="search-input"]', 'the', { delay: 10 });
    // Accept either a visible hit highlight or at least one hit badge on a thumbnail
    let ok = false;
    try {
      await page.waitForSelector('[data-testid="hit-box"]', { timeout: 4000 });
      ok = true;
    } catch {}
    if (!ok) {
      try { await page.waitForSelector('[data-testid="thumb-hit"]', { timeout: 4000 }); ok = true; } catch {}
    }
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `ok=${ok}\nscreenshot=${SHOT}\n`, 'utf-8');
    if (!ok) throw new Error('no hit highlight or thumb marker visible');
    console.log('OK ui_search_highlight_thumb');
    await browser.close();
    process.exit(0);
  } catch (e) {
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `error=${e?.message||e}\nscreenshot=${SHOT}\n`, 'utf-8');
    console.error('FAIL ui_search_highlight_thumb:', e?.message||e);
    await browser.close();
    process.exit(2);
  }
})();

