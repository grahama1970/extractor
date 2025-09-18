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
const NAME = 'ui_review_queue';
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

  const claimBtn = await page.$('[data-testid="btn-claim"]');
  const releaseBtn = await page.$('[data-testid="btn-release"]');
  const statusBadge = await page.$('[data-testid="status-badge"]');

  if (!claimBtn) failures.push('missing claim button');
  if (!releaseBtn) failures.push('missing release button');
  if (!statusBadge) failures.push('missing status badge');

  if (!failures.length) {
    const statusBefore = await statusBadge.evaluate((el) => el.textContent?.trim() || '');
    append(`statusBefore=${statusBefore}`);

    await claimBtn.click().catch(() => failures.push('unable to click claim button'));
    await new Promise(r=>setTimeout(r,200));
    const statusAfterClaim = await statusBadge.evaluate((el) => el.textContent?.trim() || '');
    append(`statusAfterClaim=${statusAfterClaim}`);
    if (statusAfterClaim === statusBefore) failures.push('status badge did not update after claim');

    const reviewerName = await page.evaluate(() => {
      try {
        return window.localStorage?.getItem('tabbed.review.identity') || '';
      } catch {
        return '';
      }
    });
    append(`reviewerIdentity=${reviewerName}`);

    await releaseBtn.click().catch(() => failures.push('unable to click release button'));
    await new Promise(r=>setTimeout(r,200));
    const statusAfterRelease = await statusBadge.evaluate((el) => el.textContent?.trim() || '');
    append(`statusAfterRelease=${statusAfterRelease}`);
    if (statusAfterRelease === statusAfterClaim) failures.push('status badge did not change after release');
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
  console.error('FAIL ui_review_queue: crash', crashed?.message || crashed);
  process.exit(3);
}
if (failures.length) {
  append(`failures=${JSON.stringify(failures)}`);
  console.error(`FAIL ui_review_queue: ${failures.join('; ')}`);
  process.exit(2);
}
console.log('OK ui_review_queue');
append('status=ok');
process.exit(0);
