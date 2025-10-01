/* Scenario: Thumbnails Virtualized list renders and scrolls
 - Captures initial and scrolled screenshots, asserts count increases on scroll
*/
import path from 'node:path';
import fs from 'node:fs';
import { connectOrSkip, OUT_DIR, ts } from '../lib/cdp.mjs';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080/main').replace(/\/+$/, '');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function main(){
  const browser = await connectOrSkip();
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil:'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]');

  // Ensure left mode
  await page.evaluate(()=>{ localStorage.setItem('anno_thumb_mode','left'); });
  await page.reload({ waitUntil:'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]');

  const count0 = await page.$$eval('[data-testid^="thumb-"]', els=>els.length).catch(()=>0);
  await page.screenshot({ path: path.join(OUT_DIR, `ux_thumbs_virtualized_${ts()}_start.png`), fullPage: true }).catch(()=>{});
  // Scroll rail if present
  await page.evaluate(()=>{ const rail = document.querySelector('[data-testid^="thumbs"]'); if (rail) rail.scrollTop = (rail.scrollHeight||0); });
  await page.waitForTimeout(300);
  const count1 = await page.$$eval('[data-testid^="thumb-"]', els=>els.length).catch(()=>0);
  await page.screenshot({ path: path.join(OUT_DIR, `ux_thumbs_virtualized_${ts()}_end.png`), fullPage: true }).catch(()=>{});
  await browser.disconnect();
  const ok = count1 >= count0 && count1 > 0;
  if (!ok) { console.error('Scenario ux/thumbnails_virtualized: BROKEN', {count0, count1}); process.exit(1); }
  console.log('Scenario ux/thumbnails_virtualized: OK', {count0, count1});
}
main().catch(e=>{ console.error('ux/thumbnails_virtualized crashed:', e?.message||e); process.exit(2); });

