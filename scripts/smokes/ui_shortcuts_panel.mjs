#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_shortcuts_panel';
const SHOT = path.join(OUT_DIR, `${NAME}_${stamp}.png`);
const LOG = path.join(OUT_DIR, `${NAME}_${stamp}.log`);
const append = (line) => fs.appendFileSync(LOG, `${line}\n`, 'utf8');

const launched = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});
let page;
const failures = [];
let crashed = null;
try {
  page = await launched.newPage();
  page.setDefaultTimeout(20000);
  page.on('console', (msg) => append(`[console.${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => append(`[pageerror] ${err?.message || err}`));

  append(`BASE_URL=${BASE}`);
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(500);

  await page.keyboard.press('Shift+?').catch(() => page.keyboard.press('?'));
  const panel = await page
    .waitForSelector('[data-testid="help-shortcuts"]', { timeout: 5000 })
    .catch(() => null);
  if (!panel) {
    failures.push('shortcuts panel did not appear after pressing ?');
  } else {
    const text = await panel.evaluate((el) => el.textContent?.trim() || '');
    append(`shortcutsPanelText=${text}`);
    if (!/page|zoom|draw|hud/i.test(text)) {
      failures.push('shortcuts panel missing expected hints (page/zoom/draw/HUD)');
    }
  }
} catch (err) {
  crashed = err;
  append(`[crash] ${err?.stack || err}`);
} finally {
  if (page) {
    await page.screenshot({ path: SHOT, fullPage: true }).catch(() => {});
    append(`screenshot=${SHOT}`);
  }
  await launched.close().catch(() => {});
}

if (crashed) {
  console.error('FAIL ui_shortcuts_panel: crash', crashed?.message || crashed);
  process.exit(3);
}
if (failures.length) {
  append(`failures=${JSON.stringify(failures)}`);
  console.error(`FAIL ui_shortcuts_panel: ${failures.join('; ')}`);
  process.exit(2);
}
console.log('OK ui_shortcuts_panel');
append('status=ok');
process.exit(0);
