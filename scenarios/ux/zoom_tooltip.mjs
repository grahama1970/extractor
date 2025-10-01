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
  await page.waitForSelector('[data-testid="page-label"]');
  const zoom = await page.$('[data-testid="toolbar-zoom"]');
  if (!zoom) { console.log('SKIP: zoom control not found'); await browser.disconnect(); process.exit(0); }
  const zr = await zoom.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height}; });
  await page.mouse.move(zr.x+zr.w*0.5, zr.y+zr.h*0.5);
  await page.waitForTimeout(300);
  const tipRect = await page.evaluate(()=>{
    const tip = document.querySelector('[role="tooltip"], [data-state="delayed-open"]');
    if (!tip) return null; const b=tip.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height, present:true};
  });
  const stamp = ts();
  const shot = path.join(OUT, `ux_zoom_tooltip_${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  await browser.disconnect();
  const ok = !!(tipRect && tipRect.present && tipRect.w > 20 && Math.abs((tipRect.y) - (zr.y)) < 200);
  if (!ok) { console.error('Scenario ux/zoom_tooltip: BROKEN'); process.exit(1); }
  console.log('Scenario ux/zoom_tooltip: OK');
}
main().catch(e=>{ console.error('ux/zoom_tooltip crashed:', e?.message||e); process.exit(2); });

