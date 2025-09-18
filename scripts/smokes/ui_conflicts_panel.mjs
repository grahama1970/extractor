#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_conflicts_panel';
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

  const conflictsTab = await page.$('[data-testid="conflicts-tab"]');
  if (!conflictsTab) {
    failures.push('missing conflicts tab');
  } else {
    await conflictsTab.click().catch(() => failures.push('unable to open conflicts tab'));
  }

  let firstConflict = null;
  if (!failures.length) {
    firstConflict = await page
      .waitForSelector('[data-testid="conflict-item"]', { timeout: 8000 })
      .catch(() => null);
    if (!firstConflict) {
      failures.push('no conflict items rendered');
    }
  }

  if (firstConflict) {
    const summary = await firstConflict.evaluate((el) => ({
      text: el.textContent?.trim() || '',
      status: el.getAttribute('data-status') || el.getAttribute('data-state') || '',
    }));
    append(`firstConflict=${JSON.stringify(summary)}`);

    // Clicking the conflict should navigate/highlight overlays.
    await firstConflict.click().catch(() => failures.push('unable to focus conflict item'));
    await page.waitForTimeout(250);
    const highlight = await page.evaluate(() => {
      const highlighted = document.querySelector('[data-testid="conflict-active"]')
        || document.querySelector('[data-testid="overlay-conflict"]');
      return !!highlighted;
    });
    if (!highlight) failures.push('conflict selection did not signal active highlight');

    const adjudicateBtn = await firstConflict.$('[data-testid="btn-adjudicate"]');
    if (!adjudicateBtn) {
      failures.push('missing adjudicate button for conflict');
    } else {
      const stateBefore = await adjudicateBtn.evaluate((el) => el.getAttribute('data-state') || el.getAttribute('aria-pressed') || '');
      await adjudicateBtn.click().catch(() => failures.push('unable to click adjudicate button'));
      await page.waitForTimeout(200);
      const stateAfter = await adjudicateBtn.evaluate((el) => el.getAttribute('data-state') || el.getAttribute('aria-pressed') || '');
      if (stateBefore === stateAfter) failures.push('adjudicate button state did not change');
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
  console.error('FAIL ui_conflicts_panel: crash', crashed?.message || crashed);
  process.exit(3);
}
if (failures.length) {
  append(`failures=${JSON.stringify(failures)}`);
  console.error(`FAIL ui_conflicts_panel: ${failures.join('; ')}`);
  process.exit(2);
}
console.log('OK ui_conflicts_panel');
append('status=ok');
process.exit(0);
