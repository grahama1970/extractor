#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g,'-');
const NAME = 'ui_mentions_basic';
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
    await page.focus('[data-testid="notes-input"]');
    await page.keyboard.type('Discuss with @', { delay: 20 });
    const suggest = await page.waitForSelector('[data-testid="mention-suggest"]', { timeout: 5000 }).catch(()=>null);
    if (!suggest) throw new Error('mention-suggest not visible');
    // Click first option
    const first = await page.$('[data-testid^="mention-option-"]');
    if (first) await first.click();
    const val = await page.$eval('[data-testid="notes-input"]', el => el.value || el.textContent || '');
    log(`notes=${JSON.stringify(val)}`);
    await page.screenshot({ path: SHOT, fullPage: true }).catch(()=>{});
    if (!/@\w+/.test(val)) throw new Error('mention not inserted');
    console.log('OK ui_mentions_basic');
    process.exit(0);
  } catch (e) {
    if (page) await page.screenshot({ path: SHOT, fullPage: true }).catch(()=>{});
    log(`error=${e?.message||e}`);
    console.error('FAIL ui_mentions_basic:', e?.message||e);
    process.exit(2);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
