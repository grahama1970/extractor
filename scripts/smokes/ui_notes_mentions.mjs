#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const pagePath = process.env.PAGE_PATH || '/main';
const URL = /\/(main|classic)(\/)?$/.test(BASE) ? BASE : BASE + pagePath;
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_notes_mentions';
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
  await new Promise(r=>setTimeout(r,300));
  try { await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 8000 }); } catch {}

  const notesInput = await page.$('[data-testid="notes-input"]');
  if (!notesInput) {
    failures.push('missing notes input');
  } else {
    await notesInput.click().catch(() => failures.push('unable to focus notes input'));
    await page.type('[data-testid="notes-input"]', '@', { delay: 10 }).catch(() => failures.push('unable to type into notes input'));

    const suggestions = await page
      .waitForSelector('[data-testid="mention-suggest"]', { timeout: 5000 })
      .catch(() => null);
    if (!suggestions) {
      failures.push('mention suggestions did not appear');
    } else {
      const firstOption = await suggestions.$('[data-testid="mention-option"]')
        || (await suggestions.$('li,button,[role="option"]'));
      if (!firstOption) {
        failures.push('no mention suggestion options');
      } else {
        const suggestion = await firstOption.evaluate((el) => el.textContent?.trim() || '');
        append(`firstSuggestion=${suggestion}`);
        await firstOption.click().catch(() => failures.push('unable to select mention suggestion'));
        await new Promise(r=>setTimeout(r,200));
        const noteValue = await page.$eval('[data-testid="notes-input"]', (el) => el.value || el.textContent || '');
        if (!noteValue.includes('@')) failures.push('note input did not capture @mention');
      }
    }

    // Ensure note persists in localStorage for current doc
    const persisted = await page.evaluate(() => {
      let keys = [];
      try {
        keys = Object.keys(window.localStorage || {});
      } catch {}
      const notesKey = keys.find((k) => k.startsWith('tabbed.review.') && k.endsWith('.notes'));
      if (!notesKey) return { ok: false };
      try {
        const payload = JSON.parse(window.localStorage.getItem(notesKey) || 'null');
        return { ok: !!payload, key: notesKey };
      } catch {
        return { ok: false, key: notesKey };
      }
    });
    if (!persisted.ok) failures.push('notes did not persist to tabbed.review.* localStorage');
    else append(`notesKey=${persisted.key}`);
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
  console.error('FAIL ui_notes_mentions: crash', crashed?.message || crashed);
  process.exit(3);
}
if (failures.length) {
  append(`failures=${JSON.stringify(failures)}`);
  console.error(`FAIL ui_notes_mentions: ${failures.join('; ')}`);
  process.exit(2);
}
console.log('OK ui_notes_mentions');
append('status=ok');
process.exit(0);
