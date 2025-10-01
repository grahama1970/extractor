/* Scenario: Toolbar hierarchy present and not overlapping canvas */
import path from 'node:path';
import fs from 'node:fs';
import { connectOrSkip, OUT_DIR, ts, getRoutes, navigate, applyViewportFromEnv } from '../lib/cdp.mjs';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080/main').replace(/\/+$/, '');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function main(){
  const browser = await connectOrSkip();
  const page = await browser.newPage();
  await applyViewportFromEnv(page);
  const routes = getRoutes();
  for (const route of routes){
  await navigate(page, BASE.replace(/\/+$/,'') + route);
  await page.waitForSelector('[data-testid="page-label"]');

  const toolbar = await page.$('[data-testid="top-toolbar"]');
  const overlay = await page.$('[data-testid="overlay"]');
  const present = !!toolbar;
  let overlaps=false; let heightOk=true;
  if (toolbar){
    const tb = await toolbar.evaluate(el=>{ const b=el.getBoundingClientRect(); return {y:b.top,h:b.height}; });
    heightOk = tb.h >= 36 && tb.h <= 64;
    if (overlay){
      const ov = await overlay.evaluate(el=>{ const b=el.getBoundingClientRect(); return {y:b.top}; });
      overlaps = !(tb.y + tb.h <= ov.y - 2);
    }
  }
  await page.screenshot({ path: path.join(OUT_DIR, `ux_toolbar_hierarchy_${ts()}_${route.replace(/\//g,'_')}.png`), fullPage: true }).catch(()=>{});
  const ok = present && !overlaps && heightOk;
  if (!ok) { await browser.disconnect(); console.error('Scenario ux/toolbar_hierarchy: BROKEN', {present, overlaps, heightOk}); process.exit(1); }
  }
  await browser.disconnect();
  console.log('Scenario ux/toolbar_hierarchy: OK');
}
main().catch(e=>{ console.error('ux/toolbar_hierarchy crashed:', e?.message||e); process.exit(2); });
