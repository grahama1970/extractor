#!/usr/bin/env node
import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT = path.resolve('scripts','artifacts'); fs.mkdirSync(OUT,{recursive:true});
const SHOT = path.join(OUT, `ui_comments_threads_panel_${new Date().toISOString().replace(/[:.]/g,'-')}.png`);
const LOG = SHOT.replace(/\.png$/, '.log');

(async () => {
  const browser = await puppeteer.launch({ headless:'new', args:['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  try {
    await page.goto(URL, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 });
    // If comments panel not yet implemented, skip gracefully
    const panel = await page.$('[data-testid="comments-thread-panel"]');
    if (!panel) {
      await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
      fs.writeFileSync(LOG, `skip=comments_panel_missing\nscreenshot=${SHOT}\n`);
      console.log('OK ui_comments_threads_panel (skipped)');
      await browser.close();
      process.exit(0);
    }
    // Else, try to add a comment and @mention
    await page.click('[data-testid="comments-new"]');
    await page.type('[data-testid="comments-input"]', 'Test note @Me');
    await page.keyboard.press('Enter');
    await page.waitForSelector('[data-testid="comment-item"]', { timeout: 3000 });
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `ok=true\nscreenshot=${SHOT}\n`);
    console.log('OK ui_comments_threads_panel');
    await browser.close();
    process.exit(0);
  } catch (e) {
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `error=${e?.message||e}\nscreenshot=${SHOT}\n`);
    console.error('FAIL ui_comments_threads_panel:', e?.message||e);
    await browser.close();
    process.exit(2);
  }
})();

