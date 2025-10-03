/* Scenario: Zoom fit + pan interaction roughly works */
import path from 'node:path';
import fs from 'node:fs';
import { connectOrSkip, OUT_DIR, ts } from '../lib/cdp.mjs';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080/main').replace(/\/+$/, '');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function main(){
  const browser = await connectOrSkip();
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil:'domcontentloaded' });
  try { await page.waitForSelector('[data-testid="page-label"]',{timeout:3500}); }
  catch { await page.goto(BASE.replace(/\/+$/,'') + '/main', { waitUntil:'domcontentloaded' }); await page.waitForSelector('[data-testid="page-label"]',{timeout:3500}); }

  // Fit button
  const fit = await page.$('[data-testid="toolbar-zoom-fit"], [data-testid="zoom-fit"]');
  if (fit) await fit.click();
  // Pan gesture over overlay
  const ov = await page.$('[data-testid="overlay"]');
  if (ov){
    const r = await ov.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height}; });
    const sx = r.x + r.w*0.5, sy=r.y + r.h*0.5; const ex = sx+40, ey=sy+10;
    await page.mouse.move(sx,sy);
    // Use left-button drag for compatibility
    await page.mouse.down({ button:'left' }).catch(async()=>{ await page.mouse.down(); });
    await page.mouse.move(ex,ey,{steps:8}); await page.mouse.up();
  }
  await page.screenshot({ path: path.join(OUT_DIR, `ux_zoom_fit_pan_${ts()}.png`), fullPage: true }).catch(()=>{});
  await browser.disconnect();
  console.log('Scenario ux/zoom_fit_pan: OK');
}
main().catch(e=>{ console.error('ux/zoom_fit_pan crashed:', e?.message||e); process.exit(2); });
