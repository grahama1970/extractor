// Attach to an existing Chrome via CDP and send a prompt to an already-open Copilot Web tab.
// Intent: avoid TCC by driving inside the browser process (non-headless).
// Requires: an already-running Chrome with --remote-debugging-port (or a Browserless WebSocket).

import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

function ts() { return new Date().toISOString().replace(/[:.]/g, '-'); }

async function discoverWS(discUrl) {
  try {
    const r = await fetch(discUrl, { cache: 'no-store' });
    const j = await r.json();
    if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0', '127.0.0.1');
  } catch (e) {
    // ignore
  }
  return null;
}

function readFileSafe(p) {
  try { return fs.readFileSync(p, 'utf8'); } catch { return ''; }
}

const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const m = a.match(/^--([^=]+)=(.*)$/);
  if (m) return [m[1], m[2]];
  return [a.replace(/^--/, ''), true];
}));

const DISC = args.disc || process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:9222/json/version';
const WSE = args.ws || '';
const PROMPT_FILE = args['prompt-file'] || path.resolve('scripts', 'artifacts', 'copilot_prompt.md');
const TAB_HINT = args['tab-hint'] || 'Copilot';

const PROMPT = readFileSafe(PROMPT_FILE) || (args.prompt || '').toString();
if (!PROMPT) {
  console.error('No prompt provided (empty file and no --prompt)');
  process.exit(2);
}

const LOG = [];
function log(...x) { const s = x.join(' '); LOG.push(s); console.log(s); }

(async () => {
  // Resolve WebSocket endpoint
  let ws = WSE;
  if (!ws) {
    ws = await discoverWS(DISC);
  }
  if (!ws) {
    console.error('Unable to discover CDP WebSocket. Ensure Chrome is running with --remote-debugging-port.');
    process.exit(3);
  }
  log('WS =', ws);

  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const pages = await browser.pages();
  if (!pages.length) {
    console.error('No pages found in target browser.');
    await browser.disconnect();
    process.exit(4);
  }

  // Pick a likely Copilot page by title/url hint
  let page = pages.find(p => (p.url() || '').includes('github.com') && (await p.title?.())?.includes?.(TAB_HINT));
  if (!page) page = pages.find(p => (p.url() || '').includes('github.com')) || pages[0];
  await page.bringToFront();
  log('Using page:', await page.title(), page.url());

  // Try to focus a chat input: textarea or contenteditable
  const injected = await page.evaluate((promptText) => {
    function findInput() {
      const ta = document.querySelector('textarea');
      if (ta) return { el: ta, kind: 'textarea' };
      const ce = document.querySelector('[contenteditable="true"]');
      if (ce) return { el: ce, kind: 'contenteditable' };
      return null;
    }
    const target = findInput();
    if (!target) return { ok: false, reason: 'no-input' };
    try {
      if (target.kind === 'textarea') {
        target.el.focus();
        target.el.value = promptText;
        target.el.dispatchEvent(new Event('input', { bubbles: true }));
      } else {
        target.el.focus();
        target.el.textContent = promptText;
        const ev = new InputEvent('input', { bubbles: true, composed: true });
        target.el.dispatchEvent(ev);
      }
      return { ok: true, kind: target.kind };
    } catch (e) {
      return { ok: false, reason: String(e) };
    }
  }, PROMPT);
  log('Inject result:', JSON.stringify(injected));

  if (!injected.ok) {
    const shot = path.join(OUT_DIR, `copilot_send_${ts()}.png`);
    await page.screenshot({ path: shot, fullPage: true }).catch(() => {});
    fs.writeFileSync(path.join(OUT_DIR, 'copilot_send.log'), LOG.join('\n'));
    console.error('Failed to find input. Saved screenshot/log.');
    await browser.disconnect();
    process.exit(5);
  }

  // Send via Enter with small human-like delay
  await page.keyboard.press('Enter');
  await page.waitForTimeout(200);

  // Wait for some response growth or DOM change; fallback to screenshot
  let content = '';
  try {
    // crude: wait up to 20s for any new markdown/answer area to appear/grow
    const SELECTORS = ['[data-testid="markdown"]', '.markdown-body', '[role="log"]'];
    const start = Date.now();
    let lastLen = 0;
    while (Date.now() - start < 20000) {
      for (const sel of SELECTORS) {
        const txt = await page.$$eval(sel, (els) => els.map(e => e.innerText).join('\n\n')); // naive concat
        if (txt && txt.length > lastLen) { lastLen = txt.length; content = txt; }
      }
      if (lastLen > 0) break;
      await page.waitForTimeout(500);
    }
  } catch {}

  const stamp = ts();
  const outTxt = path.join(OUT_DIR, `copilot_response_${stamp}.txt`);
  const outPng = path.join(OUT_DIR, `copilot_response_${stamp}.png`);
  if (!content) content = (await page.content()).slice(0, 200000);
  fs.writeFileSync(outTxt, content, 'utf8');
  await page.screenshot({ path: outPng, fullPage: true }).catch(() => {});
  fs.writeFileSync(path.join(OUT_DIR, 'copilot_send.log'), LOG.join('\n'));
  console.log('OK:', outTxt);
  await browser.disconnect();
  process.exit(0);
})().catch((e) => {
  console.error('copilot_send failed:', e?.message || e);
  process.exit(10);
});

