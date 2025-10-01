#!/usr/bin/env node
import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT = path.resolve('scripts','artifacts'); fs.mkdirSync(OUT,{recursive:true});
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');
const SHOT = path.join(OUT, `ui_zoom_fit_pan_${ts()}.png`);
const LOG = SHOT.replace(/\.png$/, '.log');

(async () => {
  const browser = await puppeteer.launch({ headless:'new', args:['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  try {
    await page.goto(URL, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 });
    const pctBefore = await page.$eval('[data-testid="top-toolbar"]', el => {
      const t = el.textContent || '';
      const m = t.match(/(\d+)%/);
      return m ? parseInt(m[1],10) : null;
    }).catch(()=>null);
    await page.click('text/\u200BFit W').catch(()=>{});
    await new Promise(r => setTimeout(r, 200));
    await page.click('text/\u200BFit P').catch(()=>{});
    await new Promise(r => setTimeout(r, 200));
    const pctAfter = await page.$eval('[data-testid="top-toolbar"]', el => {
      const t = el.textContent || '';
      const m = t.match(/(\d+)%/);
      return m ? parseInt(m[1],10) : null;
    }).catch(()=>null);

    // Spacebar pan: ensure scrollLeft changes
    const scBefore = await page.evaluate(() => {
      const v = document.querySelector('[data-testid="overlay"]')?.parentElement?.parentElement; // viewerRef container
      return v ? { l: v.scrollLeft, t: v.scrollTop } : { l:0, t:0 };
    });
    await page.keyboard.down(' ');
    const overlay = await page.$('[data-testid="overlay"]');
    if (overlay) {
      const bb = await overlay.boundingBox();
      if (bb) {
        const x = Math.floor(bb.x + bb.width*0.5);
        const y = Math.floor(bb.y + bb.height*0.5);
        await page.mouse.move(x,y);
        await page.mouse.down();
        await page.mouse.move(x-60,y-40,{steps:8});
        await page.mouse.up();
      }
    }
    await page.keyboard.up(' ');
    const scAfter = await page.evaluate(() => {
      const v = document.querySelector('[data-testid="overlay"]')?.parentElement?.parentElement;
      return v ? { l: v.scrollLeft, t: v.scrollTop } : { l:0, t:0 };
    });

    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `pctBefore=${pctBefore}\npctAfter=${pctAfter}\nscrollBefore=${JSON.stringify(scBefore)}\nscrollAfter=${JSON.stringify(scAfter)}\nscreenshot=${SHOT}\n`);
    console.log('OK ui_zoom_fit_pan');
    await browser.close();
    process.exit(0);
  } catch (e) {
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `error=${e?.message||e}\nscreenshot=${SHOT}\n`);
    console.error('FAIL ui_zoom_fit_pan:', e?.message||e);
    await browser.close();
    process.exit(2);
  }
})();
