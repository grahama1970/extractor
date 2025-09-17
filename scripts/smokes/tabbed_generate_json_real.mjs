import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:9222/json/version';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() {
  try {
    const res = await fetch(DISCOVERY);
    const j = await res.json();
    if (j && j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0', '127.0.0.1');
  } catch {}
  return null;
}

(async () => {
  // Preflight: ensure LLM health passes (backend wired + keys/model configured)
  const origin = new URL(BASE).origin;
  try {
    const model = process.env.MODEL || process.env.LITELLM_DEFAULT_MODEL || process.env.DEFAULT_LITELLM_MODEL || '';
    const url = origin + '/api/health/llm' + (model ? ('?model=' + encodeURIComponent(model)) : '');
    const r = await fetch(url, { headers: { 'accept': 'application/json' } });
    if (!r.ok) {
      console.error('LLM health check failed: HTTP ' + r.status);
      process.exit(1);
    }
    const body = await r.json().catch(() => null);
    if (!body || body.ok !== true) {
      console.error('LLM health not OK. Check DEFAULT_LITELLM_MODEL / LITELLM_DEFAULT_MODEL and API keys.');
      process.exit(1);
    }
  } catch (e) {
    console.error('LLM health preflight error:', e?.message || e);
    process.exit(1);
  }

  const ws = await getWS();
  if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  page.setDefaultTimeout(45000);

  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 8000 });
  // Open a PDF explicitly to guarantee a loaded document
  try {
    await page.click('[data-testid="btn-open-pdf"]', { timeout: 4000 });
    await page.waitForSelector('[data-testid="open-dialog"] [data-testid="open-item"]', { timeout: 8000 });
    // Click the first item in the dialog
    const items = await page.$$('[data-testid="open-dialog"] [data-testid="open-item"]');
    if (items.length > 0) {
      await items[0].click();
    }
  } catch {}
  await page.waitForSelector('canvas', { timeout: 20000 });

  // Draw a sample box and click Generate
  await page.evaluate(() => { window.__ux?.drawBox?.(1, 0.12, 0.12, 0.72, 0.42, 'Table'); });
  // Ensure the new box is selected (click the last overlay box)
  try {
    await page.waitForSelector('[data-testid="box"]', { timeout: 8000 });
    const boxes = await page.$$('[data-testid="box"]');
    if (boxes.length > 0) await boxes[boxes.length - 1].click();
  } catch {}

  const clicked = await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent || '').includes('Generate JSON'));
    if (btn) { (btn).click(); return true; }
    return false;
  });
  if (!clicked) throw new Error('Generate JSON button not found');

  // Wait for result; dialog may open after latency; wait up to ~80s for non-empty value
  await page.waitForSelector('div[role="dialog"] textarea', { timeout: 40000 });
  await page.waitForFunction(() => {
    const el = document.querySelector('div[role="dialog"] textarea');
    const t = (el && (el.value || el.textContent)) || '';
    return typeof t === 'string' && t.trim().length > 10;
  }, { timeout: 80000 });
  const text = await page.$eval('div[role="dialog"] textarea', el => el.value || el.textContent || '');

  // Capture artifacts before assertion so failures still leave evidence
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const shotPath = path.join(OUT_DIR, `tabbed_generate_json_real_${stamp}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(() => {});
  const overlayPresent = await page.evaluate(() => !!document.querySelector('vite-error-overlay')).catch(() => false);
  const logPath = path.join(OUT_DIR, `tabbed_generate_json_real_${stamp}.log`);
  const preview = (text || '').slice(0, 600);
  const report = [
    `BASE_URL=${BASE}`,
    `DISCOVERY=${DISCOVERY}`,
    `overlayPresent=${overlayPresent}`,
    `textLength=${(text || '').length}`,
    '--- preview ---',
    preview,
    `screenshot=${shotPath}`,
  ].join('\n');
  fs.writeFileSync(logPath, report, 'utf-8');

  let okKeys = /\bcolumns\b/.test(text) && /\bdata\b/.test(text);
  if (!okKeys) {
    try {
      const obj = JSON.parse(text);
      const hasKeys = (v) => {
        if (v && typeof v === 'object') {
          if (Array.isArray(v)) return v.some(hasKeys);
          const has = Object.prototype.hasOwnProperty.call(v, 'columns') && Object.prototype.hasOwnProperty.call(v, 'data');
          return has || Object.values(v).some(hasKeys);
        }
        return false;
      };
      okKeys = hasKeys(obj);
    } catch {}
  }
  if (!okKeys) {
    throw new Error('REAL LLM output missing expected keys (columns, data). Check DEFAULT_LITELLM_MODEL / LITELLM_DEFAULT_MODEL and API keys.');
  }

  await page.close();
  await browser.disconnect();
  console.log('Smoke(tabbed_generate_json_real): OK');
  process.exit(0);
})().catch((e) => {
  console.error('Smoke(tabbed_generate_json_real) failed:', e.message || e);
  process.exit(1);
});
