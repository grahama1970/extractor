import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:9222/json/version';
const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

async function discoverWS() {
  const res = await fetch(DISCOVERY);
  const j = await res.json();
  if (!j || !j.webSocketDebuggerUrl) throw new Error('No webSocketDebuggerUrl in discovery response');
  return j.webSocketDebuggerUrl.replace('0.0.0.0', '127.0.0.1');
}

async function main() {
  const ws = await discoverWS();
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);

  const outPath = path.join(OUT_DIR, `cdp_network_main_${ts()}.ndjson`);
  const fd = fs.openSync(outPath, 'w');
  const write = (obj) => fs.writeSync(fd, JSON.stringify(obj) + '\n');

  page.on('request', (req) => write({ t: Date.now(), ev: 'request', url: req.url(), method: req.method(), type: req.resourceType() }));
  page.on('response', async (res) => {
    try {
      const req = res.request();
      const bodyUsed = ['xhr','fetch'].includes(req.resourceType()) && res.status() >= 400;
      const payload = bodyUsed ? await res.text().catch(()=>null) : null;
      write({ t: Date.now(), ev: 'response', url: res.url(), status: res.status(), type: req.resourceType(), payload });
    } catch {}
  });

  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await new Promise((r) => setTimeout(r, 2000));
  await page.close();
  await browser.disconnect();
  fs.closeSync(fd);
  console.log(outPath);
}

main().catch((e) => { console.error('capture failed:', e.message); process.exit(2); });
