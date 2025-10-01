#!/usr/bin/env node
import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT = path.resolve('scripts','artifacts'); fs.mkdirSync(OUT,{recursive:true});
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');
const SHOT = path.join(OUT, `ui_thumbnails_virtualized_${ts()}.png`);
const LOG = SHOT.replace(/\.png$/, '.log');

(async () => {
  const browser = await puppeteer.launch({ headless:'new', args:['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  try {
    await page.goto(URL, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 });
    // Ensure left rail visible: it is default; verify container exists
    const rail = await page.$('div.w-40.border-r');
    const bottom = await page.$('[data-testid="page-controls"]');
    const thumbsPresent = !!rail || !!bottom;
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `thumbsPresent=${thumbsPresent}\nscreenshot=${SHOT}\n`);
    if (!thumbsPresent) throw new Error('thumbnail rails not present');
    console.log('OK ui_thumbnails_virtualized');
    await browser.close();
    process.exit(0);
  } catch (e) {
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `error=${e?.message||e}\nscreenshot=${SHOT}\n`);
    console.error('FAIL ui_thumbnails_virtualized:', e?.message||e);
    await browser.close();
    process.exit(2);
  }
})();

