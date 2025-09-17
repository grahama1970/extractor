import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/classic';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
  page.setDefaultTimeout(25000);

  let ok = true; let reason = '';

  try {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="overlay"]', { timeout: 8000 }).catch(()=>{});

    // Ensure one box exists (dev helper)
    try {
      await page.waitForFunction(() => !!(window).__ux && typeof (window).__ux.drawBox === 'function', { timeout: 1500 });
      await page.evaluate(() => { const ux = (window).__ux; ux?.drawBox(1, 0.2,0.2,0.5,0.4,'Table'); });
    } catch {}

    // Select the box
    const box = await page.$('[data-testid="box"]');
    if (!box) { ok = false; reason = 'no_box'; }
    if (ok) await box.click();

    // Ensure Exact JSON Match is OFF for flow test
    try {
      const isOn = await page.$eval('[data-testid="toggle-exact-json"]', (el) => (el && 'checked' in el) ? el.checked : false);
      if (isOn) await page.click('[data-testid="toggle-exact-json"]');
    } catch {}

    // Trigger Generate JSON
    await page.click('[data-testid="btn-generate-inspector"]');
    const dialog = await page.waitForSelector('[data-testid="json-dialog"]', { timeout: 12000 }).catch(()=>null);
    if (!dialog) {
      ok = false; reason = 'no_dialog_real_backend_unavailable_or_error';
    } else {
      // Inspect content
      const txt = await page.$eval('[data-testid="json-dialog"] textarea', (el) => el.value || el.textContent || '');
      if (!/"columns"\s*:\s*\[/.test(txt)) { ok = false; reason = 'no_columns_in_output'; }
    }
  } catch (e) {
    ok = false; reason = `exception:${e?.message || e}`;
  }

  const stamp = ts();
  const shot = path.join(OUT_DIR, `generate_json_flow_${stamp}.png`);
  const log = path.join(OUT_DIR, `generate_json_flow_${stamp}.log`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  fs.writeFileSync(log, [
    `BASE_URL=${BASE}`,
    ok ? 'ok=true' : `ok=false reason=${reason}`,
    `screenshot=${shot}`,
  ].join('\n'), 'utf-8');

  await browser.close();
  if (!ok) { console.error('generate_json_flow: FAIL', reason); process.exit(1); }
  console.log('generate_json_flow: OK');
})().catch(e => { console.error('generate_json_flow crashed:', e.message || e); process.exit(2); });
