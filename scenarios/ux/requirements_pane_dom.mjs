/* Scenario: Requirements pane DOM renders key elements */
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
  // Open requirements pane via a known toggle if present
  const btn = await page.$('[data-testid="toggle-requirements"], [data-testid="open-requirements"]');
  if (btn) { await btn.click(); if (typeof page.waitForTimeout==='function'){ await page.waitForTimeout(200);} else { await new Promise(r=>setTimeout(r,200)); } }
  const present = await page.$('[data-testid="requirements-pane"], [data-testid^="req-"]');
  await page.screenshot({ path: path.join(OUT_DIR, `ux_requirements_${ts()}.png`), fullPage:true }).catch(()=>{});
  await browser.disconnect();
  if (!present) { console.error('Scenario ux/requirements_pane_dom: BROKEN (not found)'); process.exit(1); }
  console.log('Scenario ux/requirements_pane_dom: OK');
}
main().catch(e=>{ console.error('ux/requirements_pane_dom crashed:', e?.message||e); process.exit(2); });
