#!/usr/bin/env node
// Debug via DevTools Protocol against a visible Chrome container (selenium/standalone-chromium)
// Usage:
//   BROWSER_URL=http://127.0.0.1:9222 TARGET_URL=http://192.168.86.49:3002/proto/canvas \
//     node tools/gold_annotator_web/scripts/debug_proto_cdp.js
//
// Notes:
// - BROWSER_URL may be either an http DevTools URL (e.g. http://host:9222)
//   or a WebSocket endpoint (e.g. ws://host:3000?token=...). Both are supported.

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

function env(name, def) { return process.env[name] || def; }
function ensureDir(p){ fs.mkdirSync(p, { recursive: true }); }

(async () => {
  const browserURL = env('BROWSER_URL','http://127.0.0.1:9222');
  const targetURL = env('TARGET_URL','http://localhost:3002/proto/canvas');
  const outPng = 'tools/gold_annotator_web/docs/screenshots/proto_cdp.png';
  const logFile = 'tools/gold_annotator_web/proto/cdp_debug.jsonl';
  ensureDir(path.dirname(outPng)); ensureDir(path.dirname(logFile));
  const write = (o) => fs.appendFileSync(logFile, JSON.stringify({ ts: new Date().toISOString(), ...o })+'\n');

  const isWS = /^wss?:\/\//i.test(browserURL);
  const browser = isWS
    ? await puppeteer.connect({ browserWSEndpoint: browserURL })
    : await puppeteer.connect({ browserURL });
  const page = await browser.newPage();
  page.on('console', m => write({ type:'console', level:m.type(), text:m.text() }));
  page.on('pageerror', e => write({ type:'pageerror', message:String(e) }));
  page.on('requestfailed', r => write({ type:'requestfailed', url:r.url(), err:r.failure() }));

  await page.goto(targetURL, { waitUntil:'domcontentloaded' });
  await new Promise(r=>setTimeout(r,400));
  const sels=['#add-box','#add-text','#add-arrow'];
  for (const sel of sels) {
    try { await page.click(sel); await new Promise(r=>setTimeout(r,150)); }
    catch(e){ write({ type:'click_error', selector: sel, error:String(e) }); }
  }
  try {
    await page.evaluate(()=>{
      const all=[...document.querySelectorAll('button')];
      const el=all.find(b=> (b.innerText||'').includes('Save (server)'));
      if (el) el.click();
    });
  } catch(e){ write({ type:'click_error', selector:'Save (server)', error:String(e)}); }
  await new Promise(r=>setTimeout(r,500));
  await page.screenshot({ path: outPng, fullPage:true });

  // Pull server-side log tail if same-origin reachable
  try {
    const resp = await page.goto(new URL('/api/proto/log?n=100', targetURL).toString(), { waitUntil: 'networkidle0' });
    const json = await resp.json();
    write({ type:'server_log_tail', lines: json.lines || [] });
  } catch {}

  await page.close();
  await browser.disconnect();
  console.log(`CDP debug complete: screenshot => ${outPng}, log => ${logFile}`);
})().catch(e=>{ console.error(e); process.exit(1); });
