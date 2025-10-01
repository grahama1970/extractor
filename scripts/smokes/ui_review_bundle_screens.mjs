import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '') + '/main';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

async function getWS() {
  try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {}
  return null;
}

async function ensureVisible(page, sel, timeout=8000) {
  await page.waitForSelector(sel, { timeout });
  const el = await page.$(sel); if (!el) return null;
  await el.evaluate(n => n.scrollIntoView({ block:'nearest', inline:'nearest' }));
  return el;
}

async function hoverExpect(page, selector, textLike, timeout=2000) {
  const el = await ensureVisible(page, selector).catch(()=>null);
  if (!el) return false;
  // Accept title/aria-label
  const attrOk = await page.$eval(selector, (n) => {
    const t = ((n.getAttribute('title')||'') + ' ' + (n.getAttribute('aria-label')||'')).toLowerCase();
    return t.includes('first page') || t.includes('previous page') || t.includes('next page') || t.includes('last page') || t.includes('zoom') || t.includes('fit') || t.includes('load pipeline annotations') || t.includes('save annotations') || t.includes('upsert to arango') || t.includes('run pipeline') || t.includes('extract (pipeline)');
  }).catch(()=>false);
  if (attrOk) return true;
  const box = await el.boundingBox().catch(()=>null); if (box) { await page.mouse.move(Math.floor(box.x+box.width/2), Math.floor(box.y+box.height/2)); }
  await page.hover(selector).catch(()=>{});
  await page.waitForFunction((t) => {
    const tips = Array.from(document.querySelectorAll('[role="tooltip"],div[data-state="delayed-open"],div[data-side]'));
    return tips.some(el => (el.textContent||'').toLowerCase().includes(String(t).toLowerCase()));
  }, { timeout }, textLike).catch(()=>{});
  return true;
}

(async () => {
  const ws = await getWS();
  const browser = ws ? await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null }) : await (await import('puppeteer')).default.launch({ headless: 'new', args:['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil:'domcontentloaded' });
  await ensureVisible(page, '[data-testid="top-toolbar"]', 15000);

  // Light mode capture (ensure night off)
  const lightShot = path.join(OUT_DIR, `ui_top_toolbar_light_${ts()}.png`);
  await hoverExpect(page, '[data-testid="btn-first-top"]', 'First page');
  await hoverExpect(page, '[data-testid="btn-prev-top"]', 'Previous page');
  await hoverExpect(page, '[data-testid="btn-next-top"]', 'Next page');
  await hoverExpect(page, '[data-testid="btn-last-top"]', 'Last page');
  await hoverExpect(page, '[data-testid="btn-zoom-out-top"]', 'Zoom out');
  await ensureVisible(page, '[data-testid="zoom-top"]');
  await hoverExpect(page, '[data-testid="btn-zoom-in-top"]', 'Zoom in');
  await hoverExpect(page, 'button[title="Fit to width"]', 'Fit');
  await page.screenshot({ path: lightShot, fullPage: true }).catch(()=>{});

  // Dark mode capture
  await ensureVisible(page, '[data-testid="toggle-night"]');
  await page.click('[data-testid="toggle-night"]').catch(()=>{});
  const darkShot = path.join(OUT_DIR, `ui_top_toolbar_dark_${ts()}.png`);
  await page.screenshot({ path: darkShot, fullPage: true }).catch(()=>{});

  // Pipeline buttons (top toolbar cluster)
  await hoverExpect(page, '[data-testid="btn-load-pipeline-annos"]', 'Load pipeline annotations');
  await hoverExpect(page, '[data-testid="btn-save-annotations"]', 'Save annotations');
  await hoverExpect(page, '[data-testid="btn-upsert-pipeline"]', 'Upsert to Arango');
  await hoverExpect(page, '[data-testid="btn-run-pipeline"]', 'Run pipeline');
  await hoverExpect(page, '[data-testid="btn-extract-pipeline"]', 'Extract');
  const pipeShot = path.join(OUT_DIR, `ui_pipeline_buttons_${ts()}.png`);
  await page.screenshot({ path: pipeShot, fullPage: true }).catch(()=>{});

  // Search dropdown with hits + Indexing footer
  await ensureVisible(page, '[data-testid="search-input"]');
  await page.click('[data-testid="search-input"]').catch(()=>{});
  await page.keyboard.type('the', { delay: 20 });
  await page.waitForSelector('[data-testid="search-hit"]', { timeout: 10000 }).catch(()=>{});
  // Indexing footer appears while building
  const searchShot = path.join(OUT_DIR, `ui_search_dropdown_${ts()}.png`);
  await page.screenshot({ path: searchShot, fullPage: true }).catch(()=>{});

  // Inspector pane segment (page slider + label)
  const insp = await ensureVisible(page, '[data-testid="inspector-pane"]');
  if (insp) {
    const box = await insp.boundingBox();
    if (box) {
      const segPath = path.join(OUT_DIR, `ui_inspector_segment_${ts()}.png`);
      await page.screenshot({ path: segPath, clip: { x: Math.max(0, box.x-8), y: Math.max(0, box.y-8), width: Math.min(box.width+16, page.viewport().width || 1280), height: Math.min(box.height+16, page.viewport().height || 800) } }).catch(()=>{});
    }
  }

  console.log(JSON.stringify({ ok: true, base: BASE, shots: fs.readdirSync(OUT_DIR).filter(f=>/ui_.*\.(png)$/i.test(f)).slice(-8) }, null, 2));
  if (ws) { await browser.disconnect(); } else { await browser.close().catch(()=>{}); }
  process.exit(0);
})().catch((e) => { console.error('ui_review_bundle_screens failed:', e?.message||e); process.exit(2); });

