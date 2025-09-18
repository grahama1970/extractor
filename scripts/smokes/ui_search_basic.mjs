#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const QUERY = process.env.UI_SEARCH_QUERY || 'pressure';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_search_basic';
const SHOT = path.join(OUT_DIR, `${NAME}_${stamp}.png`);
const LOG = path.join(OUT_DIR, `${NAME}_${stamp}.log`);
const append = (line) => fs.appendFileSync(LOG, `${line}\n`, 'utf8');

const SELECTORS = {
  input: '[data-testid="search-input"]',
  next: '[data-testid="search-next"]',
  prev: '[data-testid="search-prev"]',
  result: '[data-testid="search-hit"]',
  pageNumber: '[data-testid="page-number"]',
};

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
  append(`query=${QUERY}`);
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  await await new Promise(r=>setTimeout(r,));

  for (const [label, selector] of Object.entries(SELECTORS)) {
    if (label === 'result') continue; // results appear after typing
    const element = await page.$(selector);
    if (!element) failures.push(`missing ${label} (${selector})`);
  }

  if (!failures.length) {
    await page.focus(SELECTORS.input);
    await page.evaluate((selector) => {
      const el = document.querySelector(selector);
      if (el) el.value = '';
    }, SELECTORS.input);
    await page.type(SELECTORS.input, QUERY, { delay: 30 });

    const nextEnabled = await page.evaluate((selector) => {
      const el = document.querySelector(selector);
      if (!el) return null;
      const disabledAttr = el.getAttribute('disabled');
      const aria = el.getAttribute('aria-disabled');
      return !(disabledAttr !== null || aria === 'true');
    }, SELECTORS.next);

    if (nextEnabled === null) {
      failures.push('search-next selector missing after typing');
    } else if (!nextEnabled) {
      failures.push('search-next remained disabled after query input');
    }

    const firstResultHandle = await page
      .waitForSelector(SELECTORS.result, { timeout: 8000 })
      .catch(() => null);
    if (!firstResultHandle) {
      failures.push('no search results rendered');
    } else {
      const firstResultData = await firstResultHandle.evaluate((el) => ({
        page: el.getAttribute('data-page') || '',
        snippet: el.getAttribute('data-snippet') || el.textContent || '',
      }));
      append(`firstResult=${JSON.stringify(firstResultData)}`);

      await firstResultHandle.click();
      if (firstResultData.page) {
        const landed = await page
          .waitForFunction(
            (selector, pageLabel) => {
              const el = document.querySelector(selector);
              if (!el) return false;
              const text = (el.textContent || '').trim();
              return text.includes(pageLabel);
            },
            { timeout: 6000 },
            SELECTORS.pageNumber,
            firstResultData.page,
          )
          .then(() => true)
          .catch(() => false);
        if (!landed) {
          failures.push(`page number did not reflect search hit page (${firstResultData.page})`);
        }
      }

      // Exercise next/prev controls to ensure they respond
      await page.click(SELECTORS.next).catch(() => failures.push('unable to click search-next'));
      await await new Promise(r=>setTimeout(r,));
      await page.click(SELECTORS.prev).catch(() => failures.push('unable to click search-prev'));
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
  console.error('FAIL ui_search_basic: crash', crashed?.message || crashed);
  process.exit(3);
}
if (failures.length) {
  append(`failures=${JSON.stringify(failures)}`);
  console.error(`FAIL ui_search_basic: ${failures.join('; ')}`);
  process.exit(2);
}
console.log('OK ui_search_basic');
append('status=ok');
process.exit(0);
