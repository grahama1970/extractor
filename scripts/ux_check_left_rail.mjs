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

  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  // Ensure left rail mode
  await page.evaluate(() => localStorage.setItem('anno_thumb_mode','left'));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('canvas');
  let haveThumb = false;
  try {
    await page.waitForSelector('[data-testid="thumb-1"]', { timeout: 8000 });
    haveThumb = true;
  } catch {}

  const stamp = ts();
  const shotPath = path.join(OUT_DIR, `ux_left_rail_${stamp}.png`);
  await page.screenshot({ path: shotPath, fullPage: true }).catch(()=>{});
  const logPath = path.join(OUT_DIR, `ux_left_rail_${stamp}.log`);
  const report = [
    `BASE_URL=${BASE}`,
    `haveThumb=${haveThumb}`,
    `screenshot: ${shotPath}`,
  ].join('\n');
  fs.writeFileSync(logPath, report, 'utf-8');

  await browser.close();

  if (!haveThumb) {
    console.error('Left rail check: BROKEN');
    console.error(report);
    process.exit(1);
  } else {
    console.log('Left rail check: OK');
    console.log(report);
  }
};

run().catch((e) => { console.error('Left rail check crashed:', e); process.exit(2); });
