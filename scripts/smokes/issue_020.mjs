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
    // Ensure at least two boxes exist (use dev helper)
    try {
      await page.waitForFunction(() => !!(window).__ux && typeof (window).__ux.drawBox === 'function', { timeout: 1500 });
      await page.evaluate(() => { const ux = (window).__ux; ux?.drawBox(1, 0.2,0.2,0.5,0.4,'Section'); ux?.drawBox(1, 0.55,0.55,0.85,0.85,'Table'); });
    } catch {}
    const boxes = await page.$$('[data-testid="box"]');
    if (boxes.length < 2) { ok = false; reason = 'need_two_boxes'; }
    if (ok) {
      // Select first box
      await boxes[0].click();
      const chipSel = '[data-testid="box-chip"]';
      const hasChip = await page.$(chipSel);
      if (!hasChip) { ok = false; reason = 'selector_missing'; }
    }
    if (ok) {
      // Heuristic: selected chip should have a visible ring/border compared to another chip
      const chipStyles = await page.$$eval('[data-testid="box-chip"]', (els) => els.map(el => getComputedStyle(el).boxShadow + '|' + getComputedStyle(el).borderColor + '|' + getComputedStyle(el).outlineColor));
      if (chipStyles.length < 2) { ok = false; reason = 'not_enough_chips'; }
      // Compare first (selected) and second (unselected) styles
      if (ok) {
        const [s0, s1] = chipStyles;
        if (s0 === s1) { ok = false; reason = 'no_visual_difference'; }
      }
    }
  } catch (e) {
    ok = false; reason = `exception:${e?.message || e}`;
  }

  const stamp = ts();
  const shot = path.join(OUT_DIR, `issue_020_${stamp}.png`);
  const log = path.join(OUT_DIR, `issue_020_${stamp}.log`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  fs.writeFileSync(log, [
    `BASE_URL=${BASE}`,
    ok ? 'ok=true' : `ok=false reason=${reason}`,
    `screenshot=${shot}`,
  ].join('\n'), 'utf-8');

  await browser.close();
  if (!ok) { console.error('issue_020: FAIL', reason); process.exit(1); }
  console.log('issue_020: OK');
})().catch(e => { console.error('issue_020 crashed:', e.message || e); process.exit(2); });
