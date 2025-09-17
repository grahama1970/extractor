import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

async function setRangeValue(page, selector, value) {
  await page.evaluate((sel, val) => {
    const el = document.querySelector(sel);
    if (!el) return;
    el.value = String(val);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }, selector, value);
}

async function waitForText(page, text, timeout=3000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const found = await page.evaluate((t) => {
      return !!Array.from(document.querySelectorAll('body *')).find(n => (n.textContent||'').includes(t));
    }, text);
    if (found) return true;
    await page.waitForTimeout(100);
  }
  return false;
}

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });
  await page.waitForSelector('canvas', { timeout: 20000 });

  // Go to a seeded page that has boxes
  await page.waitForSelector('[data-testid="pager-slider"]', { timeout: 10000 });
  await setRangeValue(page, '[data-testid="pager-slider"]', 5);
  // Ensure at least one box is rendered
  await page.waitForSelector('[data-testid="box"]', { timeout: 10000 });

  // Ensure toggle exists
  await page.waitForSelector('[data-testid="toggle-exact-json"]', { timeout: 10000 });

  // 1) Capture a generated JSON
  // Make sure JSON dialog is closed
  let dialogOpen = await page.$('[data-testid="json-dialog"]');
  if (dialogOpen) {
    await page.click('button:has-text("Close")').catch(()=>{});
    await page.waitForFunction(() => !document.querySelector('[data-testid="json-dialog"]'));
  }
  // Trigger generation
  await page.click('[data-testid="btn-generate-inspector"]');
  await page.waitForSelector('[data-testid="json-dialog"]', { timeout: 20000 });
  const genText = await page.$eval('[data-testid="json-dialog"] textarea', el => el.value || '');
  // Close dialog
  await page.click('[data-testid="json-dialog"] button:has-text("Close")');
  await page.waitForFunction(() => !document.querySelector('[data-testid="json-dialog"]'));

  // 2) Mismatch test: set gold JSON to known value and expect failure
  await page.click('[data-testid="btn-export-json"]');
  await page.waitForSelector('[data-testid="json-dialog"]', { timeout: 10000 });
  await page.$eval('[data-testid="json-dialog"] textarea', (el) => { el.value = '{"title":"X","columns":[],"data":[]}'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  await page.click('[data-testid="json-dialog"] button:has-text("Close")');
  await page.waitForFunction(() => !document.querySelector('[data-testid="json-dialog"]'));
  // Enable strict toggle
  const isChecked = await page.$eval('[data-testid="toggle-exact-json"]', el => el.getAttribute('data-state') === 'checked');
  if (!isChecked) await page.click('[data-testid="toggle-exact-json"]');
  await page.click('[data-testid="btn-generate-inspector"]');
  // Wait for failure toast, and ensure dialog did not open
  const failSeen = await waitForText(page, 'Exact JSON Match failed');
  dialogOpen = await page.$('[data-testid="json-dialog"]');
  const mismatchOk = failSeen && !dialogOpen;

  // 3) Match test: set gold JSON to previously generated value and expect pass
  await page.click('[data-testid="btn-export-json"]');
  await page.waitForSelector('[data-testid="json-dialog"]', { timeout: 10000 });
  await page.$eval('[data-testid="json-dialog"] textarea', (el, val) => { el.value = val; el.dispatchEvent(new Event('input', { bubbles: true })); }, genText);
  await page.click('[data-testid="json-dialog"] button:has-text("Close")');
  await page.waitForFunction(() => !document.querySelector('[data-testid="json-dialog"]'));
  // Ensure toggle ON
  const chk2 = await page.$eval('[data-testid="toggle-exact-json"]', el => el.getAttribute('data-state') === 'checked');
  if (!chk2) await page.click('[data-testid="toggle-exact-json"]');
  await page.click('[data-testid="btn-generate-inspector"]');
  const passSeen = await waitForText(page, 'Exact JSON Match passed');
  dialogOpen = await page.$('[data-testid="json-dialog"]');
  const matchOk = passSeen && !dialogOpen;

  const stamp = ts();
  const shot = path.join(OUT_DIR, `issue_014_${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  const log = path.join(OUT_DIR, `issue_014_${stamp}.log`);
  fs.writeFileSync(log, [
    `BASE_URL=${BASE}`,
    `mismatchOk=${mismatchOk}`,
    `matchOk=${matchOk}`,
    `screenshot=${shot}`
  ].join('\n'));
  await page.close(); await browser.disconnect();

  const ok = mismatchOk && matchOk;
  if (!ok) { console.error('issue_014: FAIL'); process.exit(1); }
  console.log('issue_014: OK');
  process.exit(0);
})().catch(e => { console.error('issue_014 crashed:', e.message || e); process.exit(2); });
