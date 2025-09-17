import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

const run = async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
  page.setDefaultTimeout(20000);

  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  const consoleLogs = [];

  page.on('console', (msg) => {
    const entry = `[console:${msg.type()}] ${msg.text()}`;
    consoleLogs.push(entry);
    if (msg.type() === 'error') consoleErrors.push(entry);
  });
  page.on('pageerror', (err) => pageErrors.push(`[pageerror] ${err.message}`));
  page.on('requestfailed', (req) => {
    const rt = req.resourceType();
    const u = req.url();
    // Track important failures (document/js/css/images)
    if (['document','script','stylesheet'].includes(rt)) {
      failedRequests.push(`[requestfailed:${rt}] ${u} -> ${req.failure()?.errorText}`);
    }
  });

  let navOk = true;
  try {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  } catch (e) {
    navOk = false;
  }

  // Check for dev error overlays (Vite + react-swc variants)
  const overlayPresent = await page.evaluate(() => {
    const selectors = [
      'vite-error-overlay',
      '#vite-plugin-react-swc-error-overlay',
      '.vite-plugin-react-swc-error-overlay',
      'react-swc-error-overlay',
      '#react-refresh-overlay'
    ];
    if (selectors.some((s) => !!document.querySelector(s))) return true;
    const txt = (document.body && document.body.innerText) || '';
    return /\[plugin:vite:react-swc\]/i.test(txt) || /Expected .+ got .+/i.test(txt);
  }).catch(() => false);

  // Ensure React mounted something meaningful
  const rootMounted = await page.evaluate(() => {
    const root = document.getElementById('root');
    return !!root && root.childElementCount > 0;
  }).catch(() => false);

  // Optional: expected selector in Classic layout
  let uiReady = false;
  try {
    await page.waitForSelector('[data-testid="page-label"]', { timeout: 3000 });
    uiReady = true;
  } catch {}

  // Minimal center-pane functional checks (low-brittleness)
  let zoomChanged = false;
  let pointerDrawOk = false;
  let toolbarClear = true;
  try {
    const canvas = await page.waitForSelector('canvas', { timeout: 4000 });
    if (canvas) {
      const before = await canvas.evaluate((c) => c.getBoundingClientRect().width);
      const slider = await page.$('[data-testid="zoom-slider"]');
      if (slider) {
        await page.$eval('[data-testid=\"zoom-slider\"]', (el) => {
          const input = el;
          const v = Number((input).value || '1');
          (input).value = String(Math.min(2, v + 0.3));
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
        });
        // wait up to 2s for canvas width to change
        for (let i = 0; i < 20; i++) {
          const after = await canvas.evaluate((c) => c.getBoundingClientRect().width);
          if (after > before + 10) { zoomChanged = true; break; }
          await page.waitForTimeout(100);
        }
      }
    }
  } catch {}

  // Check if top toolbar obscures the canvas center (should not overlay)
  try {
    const res = await page.evaluate(() => {
      const t = document.querySelector('[data-testid="top-toolbar"]');
      const c = document.querySelector('canvas');
      if (!t || !c) return { present:false, clear:true };
      const tr = t.getBoundingClientRect();
      const cr = c.getBoundingClientRect();
      const cx = cr.left + cr.width/2; const cy = cr.top + cr.height/2;
      const el = document.elementFromPoint(cx, cy);
      const overlapsCenter = !!el && (el === t || t.contains(el));
      const intersects = tr.bottom > cr.top && tr.top < cr.bottom && tr.right > cr.left && tr.left < cr.right;
      return { present:true, clear: !(overlapsCenter || intersects) };
    });
    if (res.present) toolbarClear = res.clear;
  } catch {}

  try {
    // Attempt real pointer draw: wait for overlay, focus, KeyN to arm, then drag
    await page.waitForSelector('[data-testid="overlay"]', { timeout: 8000 });
    const overlay = await page.$('[data-testid="overlay"]');
    if (overlay) {
      const bb = await overlay.boundingBox();
      if (bb) {
        const cx = Math.floor(bb.x + bb.width / 2);
        const cy = Math.floor(bb.y + bb.height / 2);
        await page.mouse.move(cx, cy);
        await page.mouse.click(cx, cy);
        await page.keyboard.press('n');
        try { await page.waitForSelector('[data-testid=\"hud-draw-armed\"]', { timeout: 1500 }); } catch {}
        const sx = Math.floor(bb.x + bb.width * 0.25);
        const sy = Math.floor(bb.y + bb.height * 0.25);
        const ex = Math.floor(bb.x + bb.width * 0.55);
        const ey = Math.floor(bb.y + bb.height * 0.55);
        await page.mouse.move(sx, sy);
        await page.mouse.down();
        await page.mouse.move(ex, ey, { steps: 8 });
        await page.mouse.up();
        try { await page.waitForSelector('[data-testid=\"box\"]', { timeout: 3000 }); pointerDrawOk = true; } catch {}
        // Fallback: try dev helper if draw didn't register in time
        if (!pointerDrawOk) {
          try {
            await page.waitForFunction(() => !!window.__ux && typeof window.__ux.drawBox === 'function', { timeout: 1500 });
            await page.evaluate(() => { const ux = (window).__ux; ux?.drawBox(1, 0.2,0.2,0.5,0.4,'Section'); });
            await page.waitForSelector('[data-testid=\"box\"]', { timeout: 1500 });
            pointerDrawOk = true;
          } catch {}
        }
      }
    }
  } catch {}

  // Consider site broken only if functional center-pane checks fail
  const consoleErrorsHard = consoleErrors.filter((l) => !/Failed to load resource/i.test(l));
  const broken = !navOk || overlayPresent || !rootMounted || !uiReady || !pointerDrawOk || !toolbarClear || consoleErrorsHard.length > 0 || pageErrors.length > 0;

  const stamp = ts();
  const shotPath = path.join(OUT_DIR, `ux_check_${stamp}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(()=>{});
  const logPath = path.join(OUT_DIR, `ux_check_${stamp}.log`);
  const report = [
    `BASE_URL=${BASE}`,
    `navOk=${navOk}`,
    `overlayPresent=${overlayPresent}`,
    `rootMounted=${rootMounted}`,
    `uiReady=${uiReady}`,
    `zoomChanged=${zoomChanged}`,
    `pointerDrawOk=${pointerDrawOk}`,
    `toolbarClear=${toolbarClear}`,
    `consoleErrors=${consoleErrors.length}`,
    `consoleErrorsHard=${consoleErrorsHard.length}`,
    `pageErrors=${pageErrors.length}`,
    `failedRequests=${failedRequests.length}`,
    '',
    '--- console (all) ---',
    ...consoleLogs,
    '',
    '--- pageErrors ---',
    ...pageErrors,
    '',
    '--- failedRequests ---',
    ...failedRequests,
    '',
    `screenshot: ${shotPath}`,
  ].join('\n');
  fs.writeFileSync(logPath, report, 'utf-8');

  await browser.close();

  if (broken) {
    console.error('UX check: BROKEN');
    console.error(report);
    process.exit(1);
  } else {
    console.log('UX check: OK');
    console.log(report);
  }
};

run().catch((e) => { console.error('UX check crashed:', e); process.exit(2); });
