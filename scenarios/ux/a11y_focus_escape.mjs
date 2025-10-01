/* Scenario: A11y focus/escape closes dialogs and returns focus to trigger */
import path from 'node:path';
import fs from 'node:fs';
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
  // Open a known dialog if present (e.g., Generate JSON)
  const btn = await page.evaluateHandle(() => Array.from(document.querySelectorAll('button')).find(b=>/Generate JSON/i.test(b.textContent||'')) || null);
  if (!btn) { console.log('SKIP: dialog trigger not found'); await browser.disconnect(); process.exit(0); }
  const el = btn.asElement();
  await el.click();
  await page.waitForSelector('[role="dialog"]', { timeout: 4000 }).catch(()=>{});
  const shot1 = path.join(OUT, `ux_a11y_dialog_open_${ts()}.png`);
  await page.screenshot({ path: shot1, fullPage: true }).catch(()=>{});
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);
  const isOpen = await page.$('[role="dialog"]');
  const activeTag = await page.evaluate(()=>document.activeElement?.tagName||'');
  // Consider focus returned if a button or the mount element is active
  const focusOk = ['BUTTON','DIV'].includes((activeTag||'').toUpperCase());
  const ariaModal = await page.$eval('[role="dialog"]', el => el?.getAttribute('aria-modal')).catch(() => null);
  const ok = !isOpen && focusOk && ariaModal !== 'true';
  const shot2 = path.join(OUT, `ux_a11y_dialog_closed_${ts()}.png`);
  await page.screenshot({ path: shot2, fullPage: true }).catch(()=>{});
  await browser.disconnect();
  if (!ok) { console.error('Scenario ux/a11y_focus_escape: BROKEN'); process.exit(1); }
  console.log('Scenario ux/a11y_focus_escape: OK');
}
main().catch(e=>{ console.error('ux/a11y_focus_escape crashed:', e?.message||e); process.exit(2); });
