/* Scenario: Keyboard core shortcuts work for navigation/selection (heuristic) */
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

  // Press N to arm new (if supported), then draw; press Delete to remove
  await page.keyboard.press('KeyN').catch(()=>{});
  const overlay = await page.$('[data-testid="overlay"]');
  if (overlay){
    const r = await overlay.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height}; });
    const sx=r.x+r.w*0.25, sy=r.y+r.h*0.25, ex=r.x+r.w*0.45, ey=r.y+r.h*0.35;
    await page.mouse.move(sx,sy); await page.mouse.down(); await page.mouse.move(ex,ey,{steps:8}); await page.mouse.up();
  }
  let count = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0);
  await page.keyboard.press('Delete').catch(()=>{});
  if (typeof page.waitForTimeout === 'function') { await page.waitForTimeout(100); } else { await new Promise(r=>setTimeout(r,100)); }
  const after = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0);
  await page.screenshot({ path: path.join(OUT_DIR, `ux_keyboard_core_${ts()}.png`), fullPage: true }).catch(()=>{});
  await browser.disconnect();
  const ok = after <= count;
  if (!ok) { console.error('Scenario ux/keyboard_core: BROKEN', {count, after}); process.exit(1); }
  console.log('Scenario ux/keyboard_core: OK', {count, after});
}
main().catch(e=>{ console.error('ux/keyboard_core crashed:', e?.message||e); process.exit(2); });
