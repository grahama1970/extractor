#!/usr/bin/env node
// Auto-detect Vite overlay via Puppeteer/CDP and apply targeted TSX fixes.
// Heuristics: fixes missing </SidebarContent> in ClassicLayout.tsx introduced by sidebar migration.

import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '') + '/main';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = () => new Date().toISOString().replace(/[:.]/g,'-');
const logp = path.join(OUT_DIR, `ux_autofix_${stamp()}.log`);
const log = (line) => fs.appendFileSync(logp, String(line)+"\n");

async function getBrowser() {
  const ws = process.env.BROWSERLESS_WS || null;
  if (ws) {
    const puppeteer = await import('puppeteer-core');
    return puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  }
  const puppeteer = await import('puppeteer');
  return puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
}

function extractPaths(text) {
  const re = /(\/[^\s:'\"]+\.(?:tsx|ts|jsx|js)):(\d+):(\d+)/g;
  const out = []; let m;
  while ((m = re.exec(text))) out.push({ file: m[1], line: Number(m[2]), col: Number(m[3]) });
  return out;
}

function safeRead(p) { try { return fs.readFileSync(p,'utf8'); } catch { return null; } }
function safeWrite(p, s) { fs.writeFileSync(p, s, 'utf8'); }

function fixMissingSidebarContentClose(filePath) {
  const src = safeRead(filePath); if (!src) return { fixed:false, reason:'unreadable' };
  const open = (src.match(/<SidebarContent\b/g) || []).length;
  const close = (src.match(/<\/SidebarContent>/g) || []).length;
  if (open <= close) return { fixed:false, reason:'balanced' };
  // Heuristic: insert closing tag before the Export All button or before the left drag handle, whichever comes first.
  let idx = src.indexOf('data-testid="btn-export-all"');
  if (idx < 0) idx = src.indexOf('Drag handle (left)');
  if (idx < 0) idx = src.length;
  const before = src.slice(0, idx);
  const after = src.slice(idx);
  const patched = before + "\n          </SidebarContent>\n" + after;
  safeWrite(filePath, patched);
  return { fixed:true };
}

function fixAdjacentElements(filePath, line) {
  const src = safeRead(filePath); if (!src) return { fixed:false, reason:'unreadable' };
  const lines = src.split(/\r?\n/);
  const i = Math.max(0, Math.min(lines.length - 1, (line|0) - 1));
  // Heuristic: wrap a small block around the error line with a fragment
  const start = Math.max(0, i - 2);
  const end = Math.min(lines.length - 1, i + 2);
  const before = lines.slice(0, start).join('\n');
  const block = lines.slice(start, end + 1).join('\n');
  const after = lines.slice(end + 1).join('\n');
  // Avoid double wrapping
  if (/^\s*<>[\s\S]*<\/>
$/m.test(block)) return { fixed:false, reason:'already_wrapped' };
  const patched = `${before}\n<>\n${block}\n</>\n${after}`;
  safeWrite(filePath, patched);
  return { fixed:true };
}

function balanceCount(s) {
  let open = 0, close = 0;
  for (const ch of s) { if (ch === '{') open++; else if (ch === '}') close++; }
  return { open, close };
}

function fixDanglingBraces(filePath, line) {
  const src = safeRead(filePath); if (!src) return { fixed:false, reason:'unreadable' };
  const lines = src.split(/\r?\n/);
  const i = Math.max(0, Math.min(lines.length - 1, (line|0) - 1));
  const start = Math.max(0, i - 3);
  const end = Math.min(lines.length - 1, i + 3);
  const window = lines.slice(start, end + 1);
  const joined = window.join('\n');
  const { open, close } = balanceCount(joined);
  let patched = null;
  if (open > close) {
    // add missing closing brace after the error line
    const before = lines.slice(0, i + 1).join('\n');
    const after = lines.slice(i + 1).join('\n');
    patched = `${before}\n}\n${after}`;
  } else if (close > open) {
    // remove a lone '}' line if present
    const idx = window.findIndex(l => l.trim() === '}');
    if (idx >= 0) {
      const global = start + idx;
      const newLines = lines.slice();
      newLines.splice(global, 1);
      patched = newLines.join('\n');
    }
  }
  if (patched) { safeWrite(filePath, patched); return { fixed:true }; }
  return { fixed:false, reason:'balanced' };
}

(async()=>{
  const browser = await getBrowser();
  try {
    log(`BASE_URL=${BASE}`);
    const page = await browser.newPage();
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    // Check for Vite overlay
    const hasOverlay = await page.$('#vite-error-overlay, .vite-error-overlay');
    if (!hasOverlay) { log('No overlay detected; nothing to fix.'); process.exit(0); }
    const overlayText = await page.evaluate(() => {
      const el = document.querySelector('#vite-error-overlay, .vite-error-overlay');
      return el ? el.innerText : '';
    });
    log('Overlay captured.');
  const paths = extractPaths(overlayText);
  log(`Paths: ${JSON.stringify(paths)}`);
  let fixedAny = false;
  for (const p of paths) {
    if (p.file.endsWith('ClassicLayout.tsx')) {
      const res = fixMissingSidebarContentClose(p.file);
      log(`ClassicLayout.tsx fix: ${JSON.stringify(res)}`);
      fixedAny = fixedAny || res.fixed;
    }
    if (/Adjacent JSX elements must be wrapped/i.test(overlayText)) {
      const r2 = fixAdjacentElements(p.file, p.line);
      log(`Adjacent elements fix (${p.file}:${p.line}): ${JSON.stringify(r2)}`);
      fixedAny = fixedAny || r2.fixed;
    }
    if (/Unexpected token '}'|Expected '}'|Unterminated JSX contents|Unterminated regular expression literal/i.test(overlayText)) {
      const r3 = fixDanglingBraces(p.file, p.line);
      log(`Dangling braces fix (${p.file}:${p.line}): ${JSON.stringify(r3)}`);
      fixedAny = fixedAny || r3.fixed;
    }
  }
    if (!fixedAny) { log('No applicable fixes.'); process.exit(1); }
    log('Applied autofix.');
    process.exit(0);
  } catch (e) {
    log(`autofix error: ${e?.message||e}`);
    process.exit(2);
  } finally {
    try { await browser.close(); } catch {}
  }
})();
