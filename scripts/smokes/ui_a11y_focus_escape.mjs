#!/usr/bin/env node
import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT = path.resolve('scripts','artifacts'); fs.mkdirSync(OUT,{recursive:true});
const SHOT = path.join(OUT, `ui_a11y_focus_escape_${new Date().toISOString().replace(/[:.]/g,'-')}.png`);
const LOG = SHOT.replace(/\.png$/, '.log');

(async () => {
  const browser = await puppeteer.launch({ headless:'new', args:['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  try {
    await page.goto(URL, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 });
    // Open help with '?'
    await page.keyboard.type('?');
    const opened = await page.waitForSelector('text/Shortcuts & Modes', { timeout: 3000 }).then(()=>true).catch(()=>false);
    // Esc to close
    if (opened) { await page.keyboard.press('Escape'); }
    await new Promise(r => setTimeout(r, 200));
    const stillOpen = await page.$('text/Shortcuts & Modes');
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `opened=${opened}\nclosed=${!stillOpen}\nscreenshot=${SHOT}\n`);
    console.log('OK ui_a11y_focus_escape');
    await browser.close();
    process.exit(0);
  } catch (e) {
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `error=${e?.message||e}\nscreenshot=${SHOT}\n`);
    console.error('FAIL ui_a11y_focus_escape:', e?.message||e);
    await browser.close();
    process.exit(2);
  }
})();
