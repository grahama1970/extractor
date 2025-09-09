// Connect to an existing browserless (Chromium) instance and capture
// console logs, page errors, request failures, and non-2xx responses.
// Also grabs an initial screenshot.
//
// Usage:
//   BROWSERLESS_WS='ws://localhost:3000?token=devtoken123' \
//   TARGET_URL='http://192.168.86.49:3002' \
//   DURATION_SEC=30 \
//   node scripts/cdp_capture.mjs

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import puppeteer from 'puppeteer-core';

const WS = process.env.BROWSERLESS_WS || 'ws://localhost:3000?token=devtoken123';
const URL = process.env.TARGET_URL || 'http://localhost:3003';
const DURATION = parseInt(process.env.DURATION_SEC || '30', 10);
const OUT = path.resolve('tools/gold_annotator_2/artifacts');

fs.mkdirSync(OUT, { recursive: true });

const logFile = path.join(OUT, `console-${Date.now()}.jsonl`);
const append = (obj) => fs.appendFileSync(logFile, JSON.stringify({ ts: new Date().toISOString(), ...obj }) + '\n');

const toJSONable = async (arg) => {
  try {
    const v = await arg.jsonValue();
    return v;
  } catch {
    return { preview: String(arg) };
  }
};

(async () => {
  console.log(`Connecting to ${WS}`);
  const browser = await puppeteer.connect({ browserWSEndpoint: WS });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);

  page.on('console', async (msg) => {
    try {
      const args = await Promise.all(msg.args().map(toJSONable));
      append({ type: 'console', level: msg.type(), text: msg.text(), args });
    } catch (e) {
      append({ type: 'console', level: msg.type(), text: msg.text(), error: String(e) });
    }
  });

  page.on('pageerror', (err) => append({ type: 'pageerror', message: err?.message, stack: err?.stack }));
  page.on('requestfailed', (req) => append({ type: 'requestfailed', url: req.url(), method: req.method(), failure: req.failure()?.errorText }));
  page.on('response', async (res) => {
    const status = res.status();
    if (status >= 400) append({ type: 'response', url: res.url(), status });
  });

  console.log(`Navigating to ${URL}`);
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  await page.screenshot({ path: path.join(OUT, 'initial.png'), fullPage: true }).catch(() => {});
  console.log(`Capturing for ${DURATION}s. Logs -> ${logFile}`);
  await new Promise((r) => setTimeout(r, DURATION * 1000));
  await browser.close();
  console.log('Done.');
})().catch((e) => { console.error('capture failed:', e); process.exit(1); });

