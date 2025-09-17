import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const OUT_DIR = path.resolve('scripts', 'artifacts');
const POINTER_ONLY = process.env.POINTER_ONLY === '1';
fs.mkdirSync(OUT_DIR, { recursive: true });

const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

async function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

const run = async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
  page.setDefaultTimeout(25000);

  const consoleErrors = [];
  const pageErrors = [];
  const consoleLogs = [];
  page.on('console', (msg) => {
    const entry = `[console:${msg.type()}] ${msg.text()}`;
    consoleLogs.push(entry);
    if (msg.type() === 'error') consoleErrors.push(entry);
  });
  page.on('pageerror', (err) => pageErrors.push(`[pageerror] ${err.message}`));

  let navOk = true;
  try {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  } catch (e) { navOk = false; }

  let uiReady = false;
  try { await page.waitForSelector('[data-testid="page-label"]', { timeout: 5000 }); uiReady = true; } catch {}

  // Wait for canvas to mount and measure
  try { await page.waitForSelector('canvas', { timeout: 8000 }); } catch {}
  const canvasInfo = await page.evaluate(() => {
    const c = document.querySelector('canvas');
    if (!c) return { present:false };
    const r = c.getBoundingClientRect();
    return { present:true, width: Math.round(r.width), height: Math.round(r.height), x: Math.round(r.x), y: Math.round(r.y) };
  }).catch(() => ({ present:false }));

  // Check overlay present and attempt draw
  try { await page.waitForSelector('[data-testid="overlay"]', { timeout: 8000 }); } catch {}
  const overlayInfo = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="overlay"]');
    if (!el) return { present:false };
    const r = el.getBoundingClientRect();
    return { present:true, width: Math.round(r.width), height: Math.round(r.height), cx: Math.round(r.left + r.width/2), cy: Math.round(r.top + r.height/2) };
  }).catch(() => ({ present:false }));

  let drawOk = false;
  let hudArmed = false;
  if (overlayInfo.present && overlayInfo.width > 20 && overlayInfo.height > 20) {
    try {
      // Focus the overlay area, then arm draw
      await page.mouse.move(overlayInfo.cx, overlayInfo.cy);
      await page.mouse.click(overlayInfo.cx, overlayInfo.cy);
      await wait(50);
      await page.keyboard.press('n'); // arm draw
      try { await page.waitForSelector('[data-testid="hud-draw-armed"]', { timeout: 1000 }); hudArmed = true; } catch {}
      await wait(200); // ensure state updates
      await page.mouse.move(overlayInfo.cx, overlayInfo.cy);
      await page.mouse.down();
      await page.mouse.move(overlayInfo.cx + 120, overlayInfo.cy + 90, { steps: 10 });
      await page.mouse.up();
      await page.waitForSelector('[data-testid="box"]', { timeout: 3000 });
      drawOk = true;
    } catch (e) {
      // keep drawOk false
    }
  }

  // Fallback: try dev helper
  if (!drawOk && !POINTER_ONLY) {
    try {
      // wait for dev helper to be available
      await page.waitForFunction(() => !!window.__ux && typeof window.__ux.drawBox === 'function', { timeout: 5000 });
      await page.evaluate(() => {
        // @ts-ignore
        const ux = (window).__ux;
        if (ux && typeof ux.drawBox === 'function') ux.drawBox(1, 0.2, 0.2, 0.5, 0.4, 'Section');
      });
      await wait(500);
      await page.waitForSelector('[data-testid="box"]', { timeout: 2000 });
      drawOk = true;
    } catch {}
  }

  const boxCount = await page.evaluate(() => document.querySelectorAll('[data-testid="box"]').length).catch(() => -1);

  const broken = !navOk || !uiReady || !canvasInfo.present || (canvasInfo.width < 50 || canvasInfo.height < 50) || !overlayInfo.present || !drawOk || consoleErrors.length > 0 || pageErrors.length > 0;

  const stamp = ts();
  const shotPath = path.join(OUT_DIR, `ux_center_${stamp}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(()=>{});
  const logPath = path.join(OUT_DIR, `ux_center_${stamp}.log`);
  const report = [
    `BASE_URL=${BASE}`,
    `navOk=${navOk}`,
    `uiReady=${uiReady}`,
    `canvas.present=${canvasInfo.present} size=${canvasInfo.width||0}x${canvasInfo.height||0}`,
    `overlay.present=${overlayInfo.present} size=${overlayInfo.width||0}x${overlayInfo.height||0}`,
    `drawOk=${drawOk}`,
    `hudArmed=${hudArmed}`,
    `boxCount=${boxCount}`,
    `consoleErrors=${consoleErrors.length}`,
    `pageErrors=${pageErrors.length}`,
    '',
    '--- console (all) ---',
    ...consoleLogs,
    '',
    '--- pageErrors ---',
    ...pageErrors,
    '',
    `screenshot: ${shotPath}`,
  ].join('\n');
  fs.writeFileSync(logPath, report, 'utf-8');

  await browser.close();

  if (broken) {
    console.error('Center pane check: BROKEN');
    console.error(report);
    process.exit(1);
  } else {
    console.log('Center pane check: OK');
    console.log(report);
  }
};

run().catch((e) => { console.error('Center pane check crashed:', e); process.exit(2); });
