import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }
const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });
  // Hover specific inspector buttons by testid and scan for tooltip text
  await page.evaluate(() => { window.__ux?.drawBox?.(1, 0.20, 0.20, 0.40, 0.35, 'Table'); });
  const hoverAndCheck = async (sel, re) => {
    const el = await page.$(sel);
    if (!el) return false;
    const hasTitle = await page.$eval(sel, e => !!e.getAttribute('title')).catch(()=>false);
    await el.hover().catch(()=>{});
    const ok = await page.waitForFunction((regex) => {
      const tips = Array.from(document.querySelectorAll('[role="tooltip"], [data-radix-tooltip-content]'));
      return tips.some(t => new RegExp(regex, 'i').test(t.textContent || ''));
    }, { timeout: 1500 }, re).then(()=>true).catch(()=>false);
    return ok || hasTitle;
  };
  const okDup = await (async ()=>{
    const el = await page.$('[data-testid="btn-duplicate"]');
    if (!el) return false;
    const hasTitle = await page.$eval('[data-testid="btn-duplicate"]', e => !!e.getAttribute('title')).catch(()=>false);
    return hasTitle || await hoverAndCheck('[data-testid="btn-duplicate"]', 'Duplicate \\(D\\)');
  })();
  const okDel = await (async ()=>{
    const el = await page.$('[data-testid="btn-delete"]');
    if (!el) return false;
    const hasTitle = await page.$eval('[data-testid="btn-delete"]', e => !!e.getAttribute('title')).catch(()=>false);
    return hasTitle || await hoverAndCheck('[data-testid="btn-delete"]', 'Delete \\(Del\\)');
  })();

  const stamp = ts();
  const shot = path.join(OUT_DIR, `tooltips_hud_${stamp}.png`);
  const log = path.join(OUT_DIR, `tooltips_hud_${stamp}.log`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  fs.writeFileSync(log, [`BASE_URL=${BASE}`, `dup=${okDup}`, `del=${okDel}`, `screenshot=${shot}`].join('\n'));
  await page.close(); await browser.disconnect();
  if (!(okDup && okDel)) { console.error('HUD tooltips missing'); process.exit(1); }
  console.log('Smoke(tooltips_hud_actions): OK');
  process.exit(0);
})().catch(e => { console.error('Smoke(tooltips_hud_actions) crashed:', e.message || e); process.exit(2); });
