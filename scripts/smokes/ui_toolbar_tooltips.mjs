import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '') + '/main';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

async function hoverExpect(page, selector, textLike) {
  const el = await page.$(selector);
  if (!el) return false;
  // Accept title/aria-label as a valid tooltip source
  const attrOk = await page.$eval(selector, (n) => {
    const t = (n.getAttribute('title')||'') + ' ' + (n.getAttribute('aria-label')||'');
    return t.toLowerCase().includes('load pipeline annotations') || t.toLowerCase().includes('save annotations') || t.toLowerCase().includes('upsert to arango');
  }).catch(()=>false);
  if (attrOk) return true;
  // Scroll into view and hover
  await el.evaluate((n)=> n.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
  const box = await el.boundingBox();
  if (box) {
    await page.mouse.move(Math.floor(box.x+box.width/2), Math.floor(box.y+box.height/2));
  }
  await page.hover(selector);
  await page.waitForTimeout(500);
  const ok = await page.waitForFunction((t) => {
    const tips = Array.from(document.querySelectorAll('[role="tooltip"],div[class*="Tooltip"],div[data-state="delayed-open"],div[data-side]'));
    return tips.some(el => (el.textContent||'').toLowerCase().includes(String(t).toLowerCase()));
  }, { timeout: 2500 }, textLike).then(()=>true).catch(()=>false);
  return ok;
}

(async () => {
  const stamp = ts();
  const shot = path.join(OUT_DIR, `ui_tooltips_${stamp}.png`);
  const logp = path.join(OUT_DIR, `ui_tooltips_${stamp}.log`);
  const log = (m)=>fs.appendFileSync(logp, m+"\n");
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 15000 });
    const checks = [
      ['[data-testid="btn-load-pipeline-annos"]','Load pipeline annotations'],
      ['[data-testid="btn-save-annotations"]','Save annotations'],
      ['[data-testid="btn-upsert-pipeline"]','Upsert to Arango'],
    ];
    const results = [];
    for (const [sel,txt] of checks) {
      const ok = await hoverExpect(page, sel, txt);
      results.push({ sel, txt, ok });
    }
    await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
    log(`BASE_URL=${BASE}`);
    log(`results=${JSON.stringify(results)}`);
    log(`screenshot=${shot}`);
    if (!results.every(r=>r.ok)) {
      console.error('tooltips check failed');
      process.exit(1);
    }
    console.log(JSON.stringify({ ok: true, results }, null, 2));
  } catch (e) {
    log('crash=' + (e?.message||e));
    console.error('tooltips smoke failed:', e?.message||e);
    process.exit(2);
  } finally { await browser.close().catch(()=>{}); }
})();
