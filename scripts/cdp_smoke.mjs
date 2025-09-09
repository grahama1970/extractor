import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const WS = process.env.BROWSERLESS_WS || 'ws://localhost:3000?token=devtoken123';
const URLS = (process.env.TARGET_URLS || 'http://localhost:3002,http://localhost:3003').split(',');
const outDir = path.resolve('artifacts');
fs.mkdirSync(outDir, { recursive: true });

const delay = (ms) => new Promise(r => setTimeout(r, ms));

const main = async () => {
  const browser = await puppeteer.connect({ browserWSEndpoint: WS });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);
  for (const url of URLS) {
    try {
      await page.goto(url.trim(), { waitUntil: 'domcontentloaded' });
      await delay(1000);
      const safe = url.replace(/[^a-z0-9]+/gi, '_');
      const file = path.join(outDir, `smoke_${safe}.png`);
      await page.screenshot({ path: file, fullPage: true });
      console.log('screenshot', file);
    } catch (e) {
      console.error('failed', url, e.message);
    }
  }
  await browser.close();
};

main().catch((e) => { console.error(e); process.exit(1); });

