#!/usr/bin/env node
import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT = path.resolve('scripts','artifacts'); fs.mkdirSync(OUT,{recursive:true});
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');
const SHOT = path.join(OUT, `ui_selection_handles_resize_${ts()}.png`);
const LOG = SHOT.replace(/\.png$/, '.log');

(async () => {
  const browser = await puppeteer.launch({ headless:'new', args:['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  try {
    await page.goto(URL, { waitUntil:'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 });
    // Ensure at least one box exists; if not, draw it quickly
    const hasBox = await page.$('[data-testid="box"]');
    if (!hasBox) {
      await page.keyboard.press('n');
      const overlay = await page.$('[data-testid="overlay"]');
      const bb = overlay && await overlay.boundingBox();
      if (bb) {
        const sx = Math.floor(bb.x + bb.width*0.3);
        const sy = Math.floor(bb.y + bb.height*0.3);
        const ex = Math.floor(bb.x + bb.width*0.45);
        const ey = Math.floor(bb.y + bb.height*0.45);
        await page.mouse.move(sx,sy); await page.mouse.down(); await page.mouse.move(ex,ey,{steps:6}); await page.mouse.up();
      }
    }
    // Capture initial width/height
    const before = await page.$eval('[data-testid="box"]', el => ({
      w: (el).getBoundingClientRect().width,
      h: (el).getBoundingClientRect().height
    }));
    // Drag the bottom-right handle (approx by offset near bottom-right)
    const box = await page.$('[data-testid="box"]');
    const bb2 = box && await box.boundingBox();
    if (bb2) {
      const hx = Math.floor(bb2.x + bb2.width);
      const hy = Math.floor(bb2.y + bb2.height);
      await page.mouse.move(hx-2, hy-2);
      await page.mouse.down();
      await page.mouse.move(hx+30, hy+20, { steps: 8 });
      await page.mouse.up();
    }
    const after = await page.$eval('[data-testid="box"]', el => ({
      w: (el).getBoundingClientRect().width,
      h: (el).getBoundingClientRect().height
    }));
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `before=${JSON.stringify(before)}\nafter=${JSON.stringify(after)}\nscreenshot=${SHOT}\n`);
    console.log('OK ui_selection_handles_resize');
    await browser.close();
    process.exit(0);
  } catch (e) {
    await page.screenshot({ path: SHOT, fullPage:true }).catch(()=>{});
    fs.writeFileSync(LOG, `error=${e?.message||e}\nscreenshot=${SHOT}\n`);
    console.error('FAIL ui_selection_handles_resize:', e?.message||e);
    await browser.close();
    process.exit(2);
  }
})();

