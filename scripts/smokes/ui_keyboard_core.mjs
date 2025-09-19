#!/usr/bin/env node
import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_keyboard_core';
const SHOT = path.join(OUT_DIR, `${NAME}_${stamp}.png`);
const LOG = path.join(OUT_DIR, `${NAME}_${stamp}.log`);

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args:['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  try {
    await page.goto(URL, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 });
    await page.waitForSelector('[data-testid="page-label"]', { timeout: 15000 });

    const pageBefore = await page.$eval('[data-testid="page-label"]', el => el.textContent || '');
    await page.keyboard.press(']');
    await new Promise(r => setTimeout(r, 200));
    const pageAfter = await page.$eval('[data-testid="page-label"]', el => el.textContent || '');

    await page.keyboard.press('n');
    // Arm draw then drag a small box
    const overlay = await page.$('[data-testid="overlay"]');
    if (overlay) {
      const bb = await overlay.boundingBox();
      if (bb) {
        const sx = Math.floor(bb.x + bb.width*0.3);
        const sy = Math.floor(bb.y + bb.height*0.3);
        const ex = Math.floor(bb.x + bb.width*0.45);
        const ey = Math.floor(bb.y + bb.height*0.45);
        await page.mouse.move(sx,sy); await page.mouse.down(); await page.mouse.move(ex,ey,{steps:6}); await page.mouse.up();
      }
    }

    // Open help (shortcuts) with '?'
    await page.keyboard.type('?');
    await page.waitForSelector('text/Shortcuts & Modes', { timeout: 3000 });

    // Make a screenshot and log
    await page.screenshot({ path: SHOT, fullPage: true }).catch(()=>{});
    fs.writeFileSync(LOG, `pageBefore=${pageBefore}\npageAfter=${pageAfter}\nscreenshot=${SHOT}\n`, 'utf-8');

    console.log('OK ui_keyboard_core');
    await browser.close();
    process.exit(0);
  } catch (e) {
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `error=${e?.message||e}\nscreenshot=${SHOT}\n`, 'utf-8');
    console.error('FAIL ui_keyboard_core:', e?.message||e);
    await browser.close();
    process.exit(2);
  }
})();
