import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() {
  try {
    const res = await fetch(DISCOVERY);
    const j = await res.json();
    if (j && j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1');
  } catch {}
  return null;
}

const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const origin = new URL(BASE).origin;
  // Fetch model from health
  const health = await (await fetch(origin + '/api/health/llm')).json().catch(()=>null);
  if (!health || health.ok !== true || !health.model) {
    console.error('LLM health not OK or model missing');
    process.exit(1);
  }
  const expectedModel = health.model;

  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  page.setDefaultTimeout(45000);

  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 8000 });
  // Ensure a PDF is loaded (autoload logic should handle this); wait for canvas
  await page.waitForSelector('canvas', { timeout: 20000 });

  // Draw a sample box via dev hook and click Generate JSON
  await page.evaluate(() => { window.__ux?.drawBox?.(1, 0.12, 0.12, 0.72, 0.42, 'Table'); });
  const clicked = await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => (b.textContent || '').includes('Generate JSON'));
    if (btn) { (btn).click(); return true; }
    return false;
  });
  if (!clicked) {
    console.error('Generate JSON button not found');
    process.exit(1);
  }

  // Wait for dialog textarea or any textarea to contain content
  await page.waitForFunction(() => {
    const inDlg = document.querySelector('div[role="dialog"] textarea');
    const anyTa = document.querySelector('textarea');
    const el = (inDlg || anyTa);
    const t = (el && (el.value || el.textContent)) || '';
    return typeof t === 'string' && t.trim().length > 10;
  }, { timeout: 80000 });
  const text = await page.evaluate(() => {
    const el = document.querySelector('div[role="dialog"] textarea') || document.querySelector('textarea');
    return (el && (el.value || el.textContent)) || '';
  });
  let obj = null;
  try { obj = JSON.parse(text); } catch {}
  const hasModel = obj && typeof obj === 'object' && typeof obj.model === 'string' && obj.model.length > 0;

  const stamp = ts();
  const shotPath = path.join(OUT_DIR, `tabbed_generate_json_model_${stamp}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(()=>{});
  const logPath = path.join(OUT_DIR, `tabbed_generate_json_model_${stamp}.log`);
  const report = [
    `BASE_URL=${BASE}`,
    `expectedModel=${expectedModel}`,
    `jsonHasModel=${hasModel}`,
    `returnedModel=${hasModel ? obj.model : ''}`,
    `screenshot=${shotPath}`,
  ].join('\n');
  fs.writeFileSync(logPath, report, 'utf-8');
  await page.close();
  await browser.disconnect();

  if (!hasModel || (obj.model !== expectedModel)) {
    console.error('Model missing or does not match expected');
    process.exit(1);
  }
  console.log('Smoke(tabbed_generate_json_model): OK');
  process.exit(0);
})().catch((e) => { console.error('Smoke(tabbed_generate_json_model) crashed:', e.message || e); process.exit(2); });
