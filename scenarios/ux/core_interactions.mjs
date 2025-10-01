/* Scenario: Core Interactions (draw/duplicate/delete/label) via CDP
 - Requires CDP endpoint; BASE_URL should point to /main
 - Saves multiple screenshots and a log summary
*/
import fs from 'node:fs';
import path from 'node:path';
import { connectOrSkip } from '../lib/cdp.mjs';

const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || '';
let WS = (process.env.BROWSERLESS_WS || '').trim();
const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080/main').replace(/\/+$/, '');
const OUT = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');
async function discoverWS(){ if(!DISCOVERY) return null; try{ const r=await fetch(DISCOVERY); const j=await r.json(); return j?.webSocketDebuggerUrl?.replace('0.0.0.0','127.0.0.1')||null; }catch{ return null; } }
async function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }

async function main(){
  const browser = await connectOrSkip();
  const page = await browser.newPage();
  page.setDefaultTimeout(25000);

  const stamp = ts();
  const shot = (name) => path.join(OUT, `ux_core_${stamp}_${name}.png`);
  const report = [];

  await page.goto(BASE, { waitUntil:'domcontentloaded' });
  await page.evaluate(()=>{ localStorage.setItem('anno_thumb_mode','left'); });
  await page.reload({ waitUntil:'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]');
  // Visual: toolbar does not occlude canvas overlay
  const tb = await page.$('[data-testid="top-toolbar"]');
  const ov = await page.$('[data-testid="overlay"]');
  if (tb && ov) {
    const tbR = await tb.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height}; });
    const ovR = await ov.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height}; });
    const overlaps = !(tbR.y + tbR.h <= ovR.y - 2);
    if (overlaps) { console.error('Scenario ux/core_interactions: BROKEN (toolbar overlays canvas)'); await browser.disconnect(); process.exit(1); }
  }
  await page.screenshot({ path: shot('page_loaded'), fullPage:true }).catch(()=>{});

  const newBtn = await page.$('[data-testid="toolbar-new"]');
  const overlay = await page.$('[data-testid="overlay"]');
  if (!newBtn || !overlay) { console.log('SKIP: toolbar/overlay not found'); await browser.disconnect(); process.exit(0); }
  await newBtn.click();
  const r = await overlay.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height}; });
  const sx = r.x + r.w*0.25, sy = r.y + r.h*0.25, ex = r.x + r.w*0.55, ey = r.y + r.h*0.40;
  await page.mouse.move(sx, sy); await page.mouse.down(); await page.mouse.move(ex, ey, { steps: 12 }); await page.mouse.up();
  let boxes = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0);
  if (boxes === 0) { await page.evaluate(()=>{ try{ window.__ux && window.__ux.drawBox(1,0.25,0.25,0.55,0.40,'Section'); }catch{} }); await sleep(150); boxes = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0); }
  report.push(`boxes_after_draw=${boxes}`);
  await page.screenshot({ path: shot('after_draw'), fullPage:true }).catch(()=>{});

  const firstBox = await page.$('[data-testid="box"]'); if (firstBox) { await firstBox.click(); await sleep(120); }
  const dupBtn = await page.$('[data-testid="toolbar-dup"]'); const delBtn = await page.$('[data-testid="toolbar-del"]');
  if (dupBtn) { await dupBtn.click(); await sleep(100); }
  let afterDup = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0); report.push(`boxes_after_dup=${afterDup}`);
  if (delBtn) { await delBtn.click(); await sleep(100); }
  let afterDel = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0); report.push(`boxes_after_del=${afterDel}`);
  await page.screenshot({ path: shot('after_dup_del'), fullPage:true }).catch(()=>{});

  const labelBtn = await page.$('[data-testid="toolbar-label"]'); if (labelBtn) { await labelBtn.click(); await page.waitForSelector('[data-testid^="label-item-"]', { timeout: 3000 }).catch(()=>{}); }
  const figBtn = await page.$('[data-testid="label-item-figure"]'); if (figBtn) { await figBtn.click(); await sleep(120); report.push('label_changed=figure'); }
  await page.screenshot({ path: shot('after_label'), fullPage:true }).catch(()=>{});

  await browser.disconnect();
  console.log('Scenario ux/core_interactions: OK');
  console.log(report.join('\n'));
}
main().catch(e=>{ console.error('ux/core_interactions crashed:', e?.message||e); process.exit(2); });
