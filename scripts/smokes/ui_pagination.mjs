#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_pagination';
const SHOT = path.join(OUT_DIR, `${NAME}_${stamp}.png`);
const LOG = path.join(OUT_DIR, `${NAME}_${stamp}.log`);

const append = (line) => fs.appendFileSync(LOG, `${line}\n`, 'utf8');

const REQ_SELECTORS = {
  prev: '[data-testid="pager-prev"]',
  next: '[data-testid="pager-next"]',
  number: '[data-testid="page-number"]',
  slider: '[data-testid="page-slider"]',
  toolbar: '[data-testid="top-toolbar"]',
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
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(500);

  // Ensure core markers exist
  for (const [key, selector] of Object.entries(REQ_SELECTORS)) {
    const el = await page.$(selector);
    if (!el) failures.push(`missing ${key} (${selector})`);
  }

  if (!failures.length) {
    // Verify toolbar does not occlude canvas center
    const toolbarClear = await page.evaluate(() => {
      const toolbar = document.querySelector('[data-testid="top-toolbar"]');
      const canvas = document.querySelector('canvas');
      if (!toolbar || !canvas) return true;
      const tr = toolbar.getBoundingClientRect();
      const cr = canvas.getBoundingClientRect();
      const cx = cr.left + cr.width / 2;
      const cy = cr.top + cr.height / 2;
      const centerElement = document.elementFromPoint(cx, cy);
      const overlapsCenter = !!centerElement && (centerElement === toolbar || toolbar.contains(centerElement));
      const intersects = tr.bottom > cr.top && tr.top < cr.bottom && tr.right > cr.left && tr.left < cr.right;
      return !(overlapsCenter || intersects);
    });
    if (!toolbarClear) failures.push('top toolbar overlaps canvas');
  }

  if (!failures.length) {
    const getPageNumber = async () => {
      const raw = await page.$eval(REQ_SELECTORS.number, (el) => el.textContent || '');
      return raw.trim();
    };

    const initialNumber = await getPageNumber().catch(() => null);
    if (!initialNumber) {
      failures.push('page number text missing');
    } else {
      await page.click(REQ_SELECTORS.next);
      const advancedByClick = await page
        .waitForFunction(
          (selector, initial) => {
            const el = document.querySelector(selector);
            if (!el) return false;
            return (el.textContent || '').trim() !== initial;
          },
          { timeout: 5000 },
          REQ_SELECTORS.number,
          initialNumber,
        )
        .then(() => true)
        .catch(() => false);
      if (!advancedByClick) failures.push('pager next did not change page number');

      if (advancedByClick) {
        const afterClick = await getPageNumber();
        await page.click(REQ_SELECTORS.prev);
        await page.waitForFunction(
          (selector, expected) => {
            const el = document.querySelector(selector);
            if (!el) return false;
            return (el.textContent || '').trim() === expected;
          },
          { timeout: 5000 },
          REQ_SELECTORS.number,
          initialNumber,
        ).catch(() => failures.push('pager prev failed to restore page number'));

        // Keyboard navigation
        await page.keyboard.press(']');
        const advancedByKey = await page
          .waitForFunction(
            (selector, previous) => {
              const el = document.querySelector(selector);
              if (!el) return false;
              return (el.textContent || '').trim() !== previous;
            },
            { timeout: 5000 },
            REQ_SELECTORS.number,
            initialNumber,
          )
          .then(() => true)
          .catch(() => false);
        if (!advancedByKey) failures.push('keyboard ] did not advance page');

        if (advancedByKey) {
          await page.keyboard.press('[');
          await page.waitForFunction(
            (selector, expected) => {
              const el = document.querySelector(selector);
              if (!el) return false;
              return (el.textContent || '').trim() === expected;
            },
            { timeout: 5000 },
            REQ_SELECTORS.number,
            initialNumber,
          ).catch(() => failures.push('keyboard [ failed to restore page number'));
        }
      }
    }
  }

  if (!failures.length) {
    // Test slider moves by dispatching events
    const sliderResult = await page.evaluate((selector) => {
      const host = document.querySelector(selector);
      if (!host) return { ok: false, reason: 'missing' };
      const input = host.matches('input') ? host : host.querySelector('input');
      if (!input) return { ok: false, reason: 'no-input' };
      const before = Number(input.value || '0');
      try {
        input.stepUp();
      } catch {}
      const after = Number(input.value || '0');
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return { ok: after !== before, before, after };
    }, REQ_SELECTORS.slider);
    if (!sliderResult.ok) {
      failures.push(`page slider did not change value (${JSON.stringify(sliderResult)})`);
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
  console.error('FAIL ui_pagination: crash', crashed?.message || crashed);
  process.exit(3);
}
if (failures.length) {
  append(`failures=${JSON.stringify(failures)}`);
  console.error(`FAIL ui_pagination: ${failures.join('; ')}`);
  process.exit(2);
}
console.log('OK ui_pagination');
append('status=ok');
process.exit(0);
