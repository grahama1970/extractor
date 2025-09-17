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
  page.setDefaultTimeout(20000);

  let reason = '';
  let ok = true;

  try {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="overlay"]');
    // Ensure at least one box exists (use dev helper)
    try {
      await page.waitForFunction(() => !!(window).__ux && typeof (window).__ux.drawBox === 'function', { timeout: 1500 });
      await page.evaluate(() => { const ux = (window).__ux; ux?.drawBox(1, 0.2,0.2,0.5,0.4,'Table'); });
    } catch {}
    const boxes = await page.$$('[data-testid="box"]');
    if (boxes.length === 0) { ok = false; reason = 'no_boxes'; }
    if (ok) {
      await boxes[0].click();
      // Ensure expected testids exist (per issue acceptance)
      const hasType = await page.$('[data-testid="inspector-label-type"]');
      const hasId = await page.$('[data-testid="inspector-instance-id"]');
      const hasChip = await page.$('[data-testid="box-chip"]');
      if (!hasType || !hasId || !hasChip) { ok = false; reason = 'selector_missing'; }
    }
    if (ok) {
      // Set initial id to table-ro3
      await page.focus('[data-testid="inspector-instance-id"]');
      await page.click('[data-testid="inspector-instance-id"]', { clickCount: 3 });
      await page.type('[data-testid="inspector-instance-id"]', 'table-ro3');
      // Change type to Section
      await page.click('[data-testid="inspector-label-type"]');
      // Select menu item with text 'Section'
      await page.evaluate(() => {
        const el = Array.from(document.querySelectorAll('[data-radix-collection-item]')).find((n) => (n.textContent || '').trim() === 'Section')
          || Array.from(document.querySelectorAll('*')).find((n) => (n.textContent || '').trim() === 'Section');
        if (el && el instanceof HTMLElement) el.click();
      });
      // Read back id
      const val = await page.$eval('[data-testid="inspector-instance-id"]', (el) => (el && 'value' in el) ? el.value : '');
      if (val !== 'section-ro3') { ok = false; reason = `id_not_updated:${val}`; }
      // Chip contains Section · section-ro3
      const chipText = await page.$eval('[data-testid="box-chip"]', (el) => el.textContent || '');
      if (!/Section\s*·\s*section-ro3/.test(chipText)) { ok = false; reason = `chip_not_updated:${chipText}`; }
    }
  } catch (e) {
    ok = false; reason = `exception:${e?.message || e}`;
  }

  const stamp = ts();
  const shot = path.join(OUT_DIR, `issue_019_${stamp}.png`);
  const log = path.join(OUT_DIR, `issue_019_${stamp}.log`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  fs.writeFileSync(log, [
    `BASE_URL=${BASE}`,
    ok ? 'ok=true' : `ok=false reason=${reason}`,
    `screenshot=${shot}`,
  ].join('\n'), 'utf-8');

  await browser.close();
  if (!ok) { console.error('issue_019: FAIL', reason); process.exit(1); }
  console.log('issue_019: OK');
})().catch(e => { console.error('issue_019 crashed:', e.message || e); process.exit(2); });
