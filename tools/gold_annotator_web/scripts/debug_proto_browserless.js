#!/usr/bin/env node
// Connect to a shared browserless instance and debug the proto canvas.
// Usage:
//   node tools/gold_annotator_web/scripts/debug_proto_browserless.js \
//     --endpoint=ws://127.0.0.1:3000?token=changeme \
//     --url=http://192.168.86.49:3002/proto_canvas.html \
//     --out=tools/gold_annotator_web/docs/screenshots/proto_browserless.png

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

function parseArgs(argv) {
  const out = {};
  for (const a of argv.slice(2)) {
    const m = a.match(/^--([^=]+)=(.*)$/);
    if (m) out[m[1]] = m[2];
  }
  return out;
}

function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }

async function main() {
  const args = parseArgs(process.argv);
  const wsEndpoint = args.endpoint || process.env.BROWSERLESS_WS || 'ws://127.0.0.1:3000?token=changeme';
  const url = args.url || 'http://localhost:3002/proto_canvas.html';
  const outPng = args.out || 'tools/gold_annotator_web/docs/screenshots/proto_browserless.png';
  const logFile = 'tools/gold_annotator_web/proto/browserless_debug.jsonl';
  ensureDir(path.dirname(outPng));
  ensureDir(path.dirname(logFile));

  const write = (obj) => fs.appendFileSync(logFile, JSON.stringify({ ts: new Date().toISOString(), ...obj }) + "\n");

  const browser = await puppeteer.connect({ browserWSEndpoint: wsEndpoint });
  const page = await browser.newPage();

  page.on('console', (msg) => write({ type: 'console', level: msg.type(), text: msg.text() }));
  page.on('pageerror', (err) => write({ type: 'pageerror', message: String(err) }));
  page.on('requestfailed', (req) => write({ type: 'requestfailed', url: req.url(), err: req.failure() }));

  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await new Promise(r=>setTimeout(r,400));

  // Exercise UI
  const clicks = ['#add-box','#add-text','#add-arrow'];
  for (const sel of clicks) {
    try { await page.click(sel); await new Promise(r=>setTimeout(r,150)); }
    catch (e) { write({ type: 'click_error', selector: sel, error: String(e) }); }
  }
  // Save
  try {
    await page.evaluate(() => {
      const all = Array.from(document.querySelectorAll('button'));
      const el = all.find(b => (b.innerText||'').includes('Save (server)'));
      if (el) el.click();
    });
  } catch (e) { write({ type: 'click_error', selector: 'Save (server)', error: String(e) }); }

  await new Promise(r=>setTimeout(r,400));
  await page.screenshot({ path: outPng, fullPage: true });

  // Pull server log tail if available
  try {
    const resp = await page.goto(new URL('/api/proto/log?n=100', url).toString(), { waitUntil: 'networkidle0' });
    const json = await resp.json();
    write({ type: 'server_log_tail', lines: json.lines || [] });
  } catch {}

  await page.close();
  await browser.disconnect();
  console.log(`Remote debug complete: screenshot => ${outPng}, log => ${logFile}`);
}

main().catch((e)=>{ console.error(e); process.exit(1); });
