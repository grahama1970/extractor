#!/usr/bin/env node
// Minimal Puppeteer debugger for proto canvas and /proto/canvas
// Usage:
//   node scripts/debug_proto.js --url=http://localhost:3002/proto_canvas.html --out=tools/gold_annotator_web/docs/screenshots/proto_debug.png

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
  const url = args.url || 'http://localhost:3002/proto_canvas.html';
  const outPng = args.out || 'tools/gold_annotator_web/docs/screenshots/proto_debug.png';
  const logFile = 'tools/gold_annotator_web/proto/puppeteer_debug.jsonl';
  ensureDir(path.dirname(outPng));
  ensureDir(path.dirname(logFile));

  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  const write = (obj) => fs.appendFileSync(logFile, JSON.stringify({ ts: new Date().toISOString(), ...obj })+"\n");

  page.on('console', (msg) => write({ type: 'console', level: msg.type(), text: msg.text() }));
  page.on('pageerror', (err) => write({ type: 'pageerror', message: String(err) }));
  page.on('requestfailed', (req) => write({ type: 'requestfailed', url: req.url(), err: req.failure() }));

  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await new Promise(r=>setTimeout(r,400));

  // Try both selectors for canvas variants
  const clicks = ["#add-box","#add-text","#add-arrow","button:has-text('Self-Test')","button:has-text('Save (server)')"]; 
  for (const sel of clicks) {
    try {
      if (sel.includes('has-text')) {
        // fallback to text search
        await page.evaluate(()=>{
          const all = Array.from(document.querySelectorAll('button'));
          const el = all.find(b => (b.innerText||'').includes('Save (server)'));
          if (el) el.click();
        });
      } else {
        await page.click(sel);
      }
      await new Promise(r=>setTimeout(r,150));
    } catch (e) { write({ type: 'click_error', selector: sel, error: String(e) }); }
  }

  await new Promise(r=>setTimeout(r,300));
  await page.screenshot({ path: outPng, fullPage: true });

  // Pull server-side client logs if available
  try {
    const resp = await page.goto(new URL('/api/proto/log?n=100', url).toString(), { waitUntil: 'networkidle0' });
    const json = await resp.json();
    write({ type: 'server_log_tail', lines: json.lines || [] });
  } catch {}

  await browser.close();
  console.log(`Debug complete: screenshot => ${outPng}, log => ${logFile}`);
}

main().catch((e)=>{ console.error(e); process.exit(1); });
