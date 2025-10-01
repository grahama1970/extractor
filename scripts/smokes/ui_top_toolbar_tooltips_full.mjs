import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '') + '/main';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR,{recursive:true});
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

const shot = (name) => path.join(OUT_DIR, `${name}_${ts()}.png`);

async function wait(ms){ return new Promise(r=>setTimeout(r, ms)); }

async function hoverAndWaitTooltip(page, selector, textLike){
  const el = await page.$(selector);
  if (!el) return false;
  await el.evaluate(n => n.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
  const box = await el.boundingBox();
  if (box){
    await page.mouse.move(Math.floor(box.x+box.width/2), Math.floor(box.y+box.height/2));
  }
  await page.hover(selector);
  // Try Radix tooltip content
  const ok = await page.waitForFunction((t) => {
    const tips = Array.from(document.querySelectorAll('[role="tooltip"],div[data-state="delayed-open"],div[data-side]'));
    return tips.some(el => (el.textContent||'').toLowerCase().includes(String(t).toLowerCase()));
  }, { timeout: 2000 }, textLike).then(()=>true).catch(async ()=>{
    // Fallback: title or aria-label attribute
    const attr = await page.$eval(selector, n => ((n.getAttribute('title')||'') + ' ' + (n.getAttribute('aria-label')||'')).toLowerCase()).catch(()=> '');
    return attr.includes(String(textLike).toLowerCase());
  });
  return ok;
}

(async ()=>{
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  page.setDefaultTimeout(25000);
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 15000 });
  // ensure left rail for parity
  await page.evaluate(()=>{ try { localStorage.setItem('anno_thumb_mode','left'); } catch {} });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 15000 });

  const logp = path.join(OUT_DIR, `ui_top_toolbar_tooltips_${ts()}.log`);
  const log = (m)=>fs.appendFileSync(logp, m+"\n");
  log(`BASE_URL=${BASE}`);

  // Group 1: pager buttons (light)
  const pager = [
    ['[data-testid="btn-first-top"]', 'First page', 'ui_top_tt_light_first'],
    ['[data-testid="btn-prev-top"]',  'Previous page', 'ui_top_tt_light_prev'],
    ['[data-testid="btn-next-top"]',  'Next page', 'ui_top_tt_light_next'],
    ['[data-testid="btn-last-top"]',  'Last page', 'ui_top_tt_light_last'],
  ];
  for (const [sel, tip, name] of pager){
    const ok = await hoverAndWaitTooltip(page, sel, tip);
    log(`${name}.ok=${ok}`);
    const p = shot(name); await page.screenshot({ path: p, fullPage: true }).catch(()=>{});
    log(`${name}.screenshot=${p}`);
  }

  // Group 2: zoom controls (light)
  const zoomOutOk = await hoverAndWaitTooltip(page, '[data-testid="btn-zoom-out-top"]', 'Zoom out');
  log(`zoom.light.out.ok=${zoomOutOk}`);
  const s1 = shot('ui_top_tt_light_zoom_out'); await page.screenshot({ path: s1, fullPage: true }).catch(()=>{});
  log(`zoom.light.out.screenshot=${s1}`);
  // Range (no tooltip, just ensure present)
  const hasRange = !!(await page.$('[data-testid="zoom-top"]'));
  log(`zoom.light.range.present=${hasRange}`);
  const s2 = shot('ui_top_tt_light_zoom_range'); await page.screenshot({ path: s2, fullPage: true }).catch(()=>{});
  log(`zoom.light.range.screenshot=${s2}`);
  const zoomInOk = await hoverAndWaitTooltip(page, '[data-testid="btn-zoom-in-top"]', 'Zoom in');
  log(`zoom.light.in.ok=${zoomInOk}`);
  const s3 = shot('ui_top_tt_light_zoom_in'); await page.screenshot({ path: s3, fullPage: true }).catch(()=>{});
  log(`zoom.light.in.screenshot=${s3}`);

  // Group 3: Fit W / Fit P using explicit title attributes (Puppeteer doesn't support :has-text)
  const fitWOk = await hoverAndWaitTooltip(page, 'button[title="Fit to width"]', 'Fit to width').catch(()=>false);
  log(`fit.light.w.ok=${fitWOk}`);
  const s4 = shot('ui_top_tt_light_fit_w'); await page.screenshot({ path: s4, fullPage: true }).catch(()=>{});
  log(`fit.light.w.screenshot=${s4}`);
  const fitPOk = await hoverAndWaitTooltip(page, 'button[title="Fit to page"]', 'Fit to page').catch(()=>false);
  log(`fit.light.p.ok=${fitPOk}`);
  const s5 = shot('ui_top_tt_light_fit_p'); await page.screenshot({ path: s5, fullPage: true }).catch(()=>{});
  log(`fit.light.p.screenshot=${s5}`);

  // Group 4: pipeline buttons cluster tooltips (light)
  const pipeline = [
    ['[data-testid="btn-load-pipeline-annos"]', 'Load pipeline annotations', 'ui_top_tt_light_pipe_load'],
    ['[data-testid="btn-save-annotations"]',    'Save annotations', 'ui_top_tt_light_pipe_save'],
    ['[data-testid="btn-upsert-pipeline"]',     'Upsert to Arango', 'ui_top_tt_light_pipe_upsert'],
    ['[data-testid="btn-extract-pipeline"]',    'Extract (Pipeline)', 'ui_top_tt_light_pipe_extract'],
    ['[data-testid="btn-run-pipeline"]',        'Run Pipeline', 'ui_top_tt_light_pipe_run'],
  ];
  for (const [sel, tip, name] of pipeline){
    const ok = await hoverAndWaitTooltip(page, sel, tip);
    log(`${name}.ok=${ok}`);
    const p = shot(name); await page.screenshot({ path: p, fullPage: true }).catch(()=>{});
    log(`${name}.screenshot=${p}`);
  }

  // Switch to dark mode
  await page.click('[data-testid="toggle-night"]').catch(()=>{});
  await wait(200);

  // Repeat one composite capture with a tooltip in dark
  const darkOk = await hoverAndWaitTooltip(page, '[data-testid="btn-next-top"]', 'Next page');
  log(`dark.next.ok=${darkOk}`);
  const darkShot = shot('ui_top_tt_dark_next');
  await page.screenshot({ path: darkShot, fullPage: true }).catch(()=>{});
  log(`dark.screenshot=${darkShot}`);

  await browser.close();
  console.log('ui_top_toolbar_tooltips_full: OK');
})().catch(e=>{ console.error('ui_top_toolbar_tooltips_full failed:', e?.message||e); process.exit(2); });