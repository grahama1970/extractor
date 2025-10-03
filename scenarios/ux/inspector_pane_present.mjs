/* Scenario: Inspector pane is present/rendered (when available) */
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
  const present = await page.$('[data-testid="inspector-pane"], [data-testid="inspector"]');
  await page.screenshot({ path: path.join(OUT_DIR, `ux_inspector_${ts()}.png`), fullPage:true }).catch(()=>{});
  await browser.disconnect();
  if (!present) { console.error('Scenario ux/inspector_pane_present: BROKEN (not found)'); process.exit(1); }
  console.log('Scenario ux/inspector_pane_present: OK');
}
main().catch(e=>{ console.error('ux/inspector_pane_present crashed:', e?.message||e); process.exit(2); });
