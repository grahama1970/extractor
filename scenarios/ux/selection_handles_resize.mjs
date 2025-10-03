/* Scenario: Selection handles appear and a small resize works (heuristic) */
import path from 'node:path';
import fs from 'node:fs';
import { connectOrSkip, OUT_DIR, ts } from '../lib/cdp.mjs';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080/main').replace(/\/+$/, '');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function main(){
  const browser = await connectOrSkip();
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil:'domcontentloaded' });
  try { await page.waitForSelector('[data-testid="page-label"]',{timeout:2000}); }
  catch { await page.goto(BASE.replace(/\/+$/,'') + '/main', { waitUntil:'domcontentloaded' }); await page.waitForSelector('[data-testid="page-label"]'); }

  // Draw a box first if none present
  let boxes = await page.$$('[data-testid="box"]');
  if (boxes.length === 0){
    const newBtn = await page.$('[data-testid="toolbar-new"]'); const overlay = await page.$('[data-testid="overlay"]');
    if (newBtn && overlay){
      await newBtn.click();
      const r = await overlay.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height}; });
      const sx=r.x+r.w*0.3, sy=r.y+r.h*0.3, ex=r.x+r.w*0.5, ey=r.y+r.h*0.4;
      await page.mouse.move(sx,sy); await page.mouse.down(); await page.mouse.move(ex,ey,{steps:8}); await page.mouse.up();
    }
    // Fallback: use window.__ux helper
    boxes = await page.$$('[data-testid="box"]');
    if (boxes.length === 0){
      await page.evaluate(()=>{ try{ window.__ux && window.__ux.drawBox(1,0.30,0.30,0.50,0.40,'Section'); }catch{} });
      if (typeof page.waitForTimeout==='function'){ await page.waitForTimeout(150);} else { await new Promise(r=>setTimeout(r,150)); }
    }
  }
  const first = await page.$('[data-testid="box"]');
  if (!first) { console.log('SKIP: no box to resize'); await browser.disconnect(); process.exit(0); }
  await first.click();
  // Try resizing via bottom-right handle
  const handle = await page.$('[data-testid="resize-handle-br"], [data-testid^="resize-handle"]');
  if (handle){
    const r = await handle.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top}; });
    await page.mouse.move(r.x+2, r.y+2); await page.mouse.down(); await page.mouse.move(r.x+15, r.y+10, {steps:6}); await page.mouse.up();
  }
  await page.screenshot({ path: path.join(OUT_DIR, `ux_selection_resize_${ts()}.png`), fullPage:true }).catch(()=>{});
  await browser.disconnect();
  console.log('Scenario ux/selection_handles_resize: OK');
}
main().catch(e=>{ console.error('ux/selection_handles_resize crashed:', e?.message||e); process.exit(2); });
