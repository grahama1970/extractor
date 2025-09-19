#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = `${BASE}/main`;
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const NAME = 'ui_filters_basic';
const SHOT = path.join(OUT_DIR, `${NAME}_${stamp}.png`);
const LOG = path.join(OUT_DIR, `${NAME}_${stamp}.log`);
const append = (line) => fs.appendFileSync(LOG, `${line}\n`, 'utf8');

const TYPE_FILTERS = ['section', 'table', 'figure', 'text'];
const SELECTORS = {
  owner: '[data-testid="filter-owner"]',
  confidence: '[data-testid="filter-confidence"]',
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
  await new Promise(r=>setTimeout(r,500));

  // Verify type toggles exist and respond to clicks.
  for (const type of TYPE_FILTERS) {
    const selector = `[data-testid="filter-type-${type}"]`;
    const toggle = await page.$(selector);
    if (!toggle) {
      failures.push(`missing filter toggle ${type}`);
      continue;
    }
    const stateBefore = await page.evaluate((sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const aria = el.getAttribute('aria-pressed');
      const dataState = el.getAttribute('data-state');
      return aria ?? dataState ?? null;
    }, selector);
    await page.click(selector).catch(() => failures.push(`unable to click filter toggle ${type}`));
    await new Promise(r=>setTimeout(r,150));
    const stateAfter = await page.evaluate((sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const aria = el.getAttribute('aria-pressed');
      const dataState = el.getAttribute('data-state');
      return aria ?? dataState ?? null;
    }, selector);
    if (stateBefore !== null && stateAfter !== null && stateBefore === stateAfter) {
      failures.push(`filter toggle ${type} state did not change`);
    }
  }

  // Confidence slider should emit change when adjusted.
  const confidenceResult = await page.evaluate((selector) => {
    const host = document.querySelector(selector);
    if (!host) return { ok: false, reason: 'missing' };
    const input = host.matches('input') ? host : host.querySelector('input');
    if (!input) return { ok: false, reason: 'no-input' };
    const before = Number(input.value || '0');
    const target = Math.max(0, Math.min(1, before - 0.25));
    input.value = String(target);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return { ok: Number(input.value || '0') !== before, before, after: Number(input.value || '0') };
  }, SELECTORS.confidence);
  if (!confidenceResult.ok) {
    failures.push(`confidence slider did not emit change (${JSON.stringify(confidenceResult)})`);
  }

  // Owner filter should surface multiple options and allow change.
  const ownerResult = await page.evaluate((selector) => {
    const el = document.querySelector(selector);
    if (!el) return { ok: false, reason: 'missing' };
    const describeSelect = (select) => {
      const before = select.value;
      const values = Array.from(select.options).map((o) => o.value);
      if (values.length < 2) return { ok: false, reason: 'not-enough-options', values };
      const next = values.find((v) => v !== before) ?? values[0];
      select.value = next;
      select.dispatchEvent(new Event('input', { bubbles: true }));
      select.dispatchEvent(new Event('change', { bubbles: true }));
      return { ok: next !== before, before, after: select.value, values };
    };
    if (el instanceof HTMLSelectElement) {
      return describeSelect(el);
    }
    const role = el.getAttribute('role');
    if (role === 'listbox') {
      const options = Array.from(el.querySelectorAll('[role="option"]'));
      if (options.length < 2) return { ok: false, reason: 'not-enough-options', values: options.map((o) => o.textContent || '') };
      const active = document.activeElement;
      options[0].dispatchEvent(new Event('pointerdown', { bubbles: true }));
      options[0].dispatchEvent(new Event('click', { bubbles: true }));
      const selected = options[0].getAttribute('data-state') || options[0].getAttribute('aria-selected');
      return { ok: selected === 'true', role, option: options[0].textContent || '' };
    }
    return { ok: false, reason: 'unknown-control' };
  }, SELECTORS.owner);
  if (!ownerResult.ok) {
    failures.push(`owner filter did not change state (${JSON.stringify(ownerResult)})`);
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
  console.error('FAIL ui_filters_basic: crash', crashed?.message || crashed);
  process.exit(3);
}
if (failures.length) {
  append(`failures=${JSON.stringify(failures)}`);
  console.error(`FAIL ui_filters_basic: ${failures.join('; ')}`);
  process.exit(2);
}
console.log('OK ui_filters_basic');
append('status=ok');
process.exit(0);
