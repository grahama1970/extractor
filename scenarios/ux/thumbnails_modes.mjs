/* Scenario: Thumbnails Modes (left rail and bottom filmstrip)
 - Ensures thumbnails render in both modes and are visually present.
 - Captures screenshots and logs layout metrics for assessment.
*/
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
  if (!WS) { console.log('SKIP: No CDP endpoint (set BROWSERLESS_WS or discovery).'); process.exit(0); }
  let browser; try{ browser = await puppeteer.connect({ browserWSEndpoint: WS, defaultViewport: null }); }catch(e){ if(/ECONNREFUSED/.test(String(e?.message||e||''))){ console.log('SKIP: CDP unreachable at', WS); process.exit(0);} throw e; }
  const page = await browser.newPage();
  page.setDefaultTimeout(25000);
  const stamp = ts();
  const shot = (name) => path.join(OUT, `ux_thumbs_${stamp}_${name}.png`);

  const metrics = [];
  await page.goto(BASE, { waitUntil:'domcontentloaded' });

  // Mode: left
  await page.evaluate(()=>{ localStorage.setItem('anno_thumb_mode','left'); });
  await page.reload({ waitUntil:'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]');
  const left = await page.evaluate(()=>{
    const rail = document.querySelector('[data-testid="thumbs-left"]') || document.querySelector('[data-testid^="thumbs"]');
    const rect = rail?.getBoundingClientRect?.();
    const thumbs = Array.from(document.querySelectorAll('[data-testid^="thumb-"]')).length;
    return { present: !!rail, width: rect?.width||0, height: rect?.height||0, thumbs };
  });
  metrics.push({ mode:'left', ...left });
  await page.screenshot({ path: shot('left'), fullPage: true }).catch(()=>{});

  // Mode: bottom
  await page.evaluate(()=>{ localStorage.setItem('anno_thumb_mode','bottom'); });
  await page.reload({ waitUntil:'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]');
  const bottom = await page.evaluate(()=>{
    const strip = document.querySelector('[data-testid="thumbs-bottom"]') || document.querySelector('[data-testid^="thumbs"]');
    const rect = strip?.getBoundingClientRect?.();
    const thumbs = Array.from(document.querySelectorAll('[data-testid^="thumb-"]')).length;
    return { present: !!strip, width: rect?.width||0, height: rect?.height||0, thumbs };
  });
  metrics.push({ mode:'bottom', ...bottom });
  await page.screenshot({ path: shot('bottom'), fullPage: true }).catch(()=>{});

  // Simple visual assertions for assessment
  const okLeft = left.present && left.width > 40 && left.thumbs >= 1;
  const okBottom = bottom.present && bottom.height > 40 && bottom.thumbs >= 1;
  // Additional thumbnail size/aspect heuristics
  const firstThumbRect = await page.evaluate(()=>{
    const el = document.querySelector('[data-testid^="thumb-"]');
    if (!el) return null; const b=el.getBoundingClientRect(); return {w:b.width,h:b.height};
  });
  if (firstThumbRect){
    const w = firstThumbRect.w, h = firstThumbRect.h; const aspect = w/(h||1);
    if (w < 80 || w > 220 || aspect < 0.6 || aspect > 1.0) { console.error('Scenario ux/thumbnails_modes: BROKEN (thumb size/aspect)'); process.exit(1); }
  }
  const broken = !(okLeft && okBottom);
  console.log('Scenario ux/thumbnails_modes metrics:', JSON.stringify(metrics));
  await browser.disconnect();
  if (broken) { console.error('Scenario ux/thumbnails_modes: BROKEN'); process.exit(1); }
  console.log('Scenario ux/thumbnails_modes: OK');
}
main().catch(e=>{ console.error('ux/thumbnails_modes crashed:', e?.message||e); process.exit(2); });
