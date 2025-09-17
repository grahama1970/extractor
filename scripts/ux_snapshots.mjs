import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const ORIGIN = process.env.BASE_ORIGIN || 'http://127.0.0.1:8080';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

const routes = [
  { path: '/main', name: 'classic' },
  { path: '/tabbed', name: 'tabbed' },
  { path: '/dashboard', name: 'dashboard' },
];

const main = async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  page.setDefaultTimeout(20000);

  // Enable dev overlays for labeled screenshots
  await page.goto(`${ORIGIN}/`, { waitUntil: 'domcontentloaded' }).catch(()=>{});
  await page.evaluate(() => {
    try {
      localStorage.setItem('debug_grid', '1');
      localStorage.setItem('debug_components', '1');
    } catch {}
  });

  const stamp = ts();
  for (const r of routes) {
    const url = `${ORIGIN}${r.path}`;
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    // wait for app mount marker
    await page.waitForFunction(() => document.body.dataset.appReady === '1');
    // ensure some UI is visible
    await page.waitForSelector('#root');
    const file = path.join(OUT_DIR, `${r.name}_${stamp}.png`);
    await page.screenshot({ path: file, fullPage: true }).catch(()=>{});
    console.log(`saved: ${file}`);
  }

  await browser.close();
};

main().catch((e) => { console.error('ux_snapshots failed:', e); process.exit(2); });

