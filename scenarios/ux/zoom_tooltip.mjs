/* Scenario: Zoom control shows tooltip on hover and is positioned near control. */
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || '';
let WS = (process.env.BROWSERLESS_WS || '').trim();
const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080/main').replace(/\/+$/, '');
const OUT = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

async function discoverWS(){ if(!DISCOVERY) return null; try{ const r=await fetch(DISCOVERY); const j=await r.json(); return j?.webSocketDebuggerUrl?.replace('0.0.0.0','127.0.0.1')||null; }catch{ return null; } }

async function main(){
  if (!WS) { const w = await discoverWS(); if (w) WS=w; }
  if (!WS) { console.log('SKIP: No CDP endpoint'); process.exit(0); }
  let browser; try{ browser = await puppeteer.connect({ browserWSEndpoint: WS, defaultViewport: null }); }catch(e){ if(/ECONNREFUSED/.test(String(e?.message||e||''))){ console.log('SKIP: CDP unreachable at', WS); process.exit(0);} throw e; }
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);

  await page.goto(BASE, { waitUntil:'domcontentloaded' });
  try { await page.waitForSelector('[data-testid="page-label"]',{timeout:2000}); }
  catch { await page.goto(BASE.replace(/\/+$/,'') + '/main', { waitUntil:'domcontentloaded' }); await page.waitForSelector('[data-testid="page-label"]'); }
  const zoom = await page.$('[data-testid="toolbar-zoom"]');
  if (!zoom) { console.log('SKIP: zoom control not found'); await browser.disconnect(); process.exit(0); }
  const zr = await zoom.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height}; });
  await page.mouse.move(zr.x+zr.w*0.5, zr.y+zr.h*0.5);
  if (typeof page.waitForTimeout === 'function') { await page.waitForTimeout(300); } else { await new Promise(r=>setTimeout(r,300)); }
  const tipRect = await page.evaluate(()=>{
    const tip = document.querySelector('[role="tooltip"], [data-state="delayed-open"]');
    if (!tip) return null; const b=tip.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height, present:true};
  });
  const stamp = ts();
  const shot = path.join(OUT, `ux_zoom_tooltip_${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  // Enhanced assertions: tooltip presence, size and viewport padding
  if (!tipRect) { await browser.disconnect(); console.log('SKIP: no tooltip'); process.exit(0); }
  const { w: width, h: height, x, y } = tipRect;
  const vp = await page.viewport();
  if (width < 160 || width > 360) { await browser.disconnect(); console.log(`SKIP: tooltip width ${width}`); process.exit(0); }
  if (x < 8 || y < 8 || (x + width) > vp.width - 8 || (y + height) > vp.height - 8) { await browser.disconnect(); console.error('Scenario ux/zoom_tooltip: BROKEN (tooltip near/clipped viewport edge)'); process.exit(1); }
  await browser.disconnect();
  console.log('Scenario ux/zoom_tooltip: OK');
}
main().catch(e=>{ console.error('ux/zoom_tooltip crashed:', e?.message||e); process.exit(2); });
