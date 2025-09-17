import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

let BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
try {
  const u = new URL(BASE);
  const p = (u.pathname || '/').replace(/\/+$/,'');
  if (p === '' || p === '/') {
    u.pathname = '/classic';
    BASE = u.toString();
  }
} catch {}
const WS = process.env.BROWSERLESS_WS || 'ws://127.0.0.1:9222/devtools/browser';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

const run = async () => {
  const browser = await puppeteer.connect({ browserWSEndpoint: WS, defaultViewport: null });
  const page = await browser.newPage();
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

  const overlayPresent = await page.evaluate(() => !!document.querySelector('vite-error-overlay')).catch(() => false);
  const rootMounted = await page.evaluate(() => {
    const root = document.getElementById('root');
    return !!root && root.childElementCount > 0;
  }).catch(() => false);
  let uiReady = false;
  try { await page.waitForSelector('[data-testid="page-label"]', { timeout: 3000 }); uiReady = true; } catch {}

  const broken = !navOk || overlayPresent || !rootMounted || !uiReady || consoleErrors.length > 0 || pageErrors.length > 0;

  const stamp = ts();
  const shotPath = path.join(OUT_DIR, `ux_check_cdp_${stamp}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(()=>{});
  const logPath = path.join(OUT_DIR, `ux_check_cdp_${stamp}.log`);
  const report = [
    `BASE_URL=${BASE}`,
    `WS=${WS}`,
    `navOk=${navOk}`,
    `overlayPresent=${overlayPresent}`,
    `rootMounted=${rootMounted}`,
    `uiReady=${uiReady}`,
    `consoleErrors=${consoleErrors.length}`,
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

  await page.close();
  await browser.disconnect();

  if (broken) {
    console.error('UX check (CDP): BROKEN');
    console.error(report);
    process.exit(1);
  } else {
    console.log('UX check (CDP): OK');
    console.log(report);
  }
};

run().catch((e) => { console.error('UX check (CDP) crashed:', e); process.exit(2); });
