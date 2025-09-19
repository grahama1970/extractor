#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const URL = /\/(main|classic)(\/)?$/.test(BASE) ? BASE : BASE + '/main';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR,{recursive:true});

function run(cmd, args, opts={}){
  const res = spawnSync(cmd, args, { encoding: 'utf8', shell: false, ...opts });
  return { status: res.status, stdout: res.stdout||'', stderr: res.stderr||'' };
}

// 1) Run fast CLI on sample PDF (no heavy deps)
const sample = process.env.SAMPLE_PDF || 'data/input/pipeline/BHT_CV32A65X_marked.pdf';
const outDir = path.resolve('data/results/cli_smoke_out');
fs.mkdirSync(outDir,{recursive:true});
const cli = run('python', ['-m','src.cli','extract', '--mode','fast', sample, outDir]);
if (cli.status !== 0) {
  const msg = (cli.stderr||cli.stdout||'').slice(0,1000);
  // Graceful fallback when this environment doesn't expose --mode yet
  if (/No such option:\s+--mode/.test(msg)) {
    console.warn('ui_extract_load: CLI lacks --mode; continuing without pre-run fast extract');
  } else {
    console.error('ui_extract_load: CLI failed:', msg);
    process.exit(2);
  }
}

// 2) Navigate to the app and verify app-ready and toolbar
(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 15000 });
    await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 5000 });
    // Basic pager draw probe
    await page.click('[data-testid="pager-next"]').catch(()=>{});
    const shot = path.join(OUT_DIR, `ui_extract_load_${Date.now()}.png`);
    await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
    console.log('OK ui_extract_load');
    process.exit(0);
  } catch (e) {
    console.error('FAIL ui_extract_load:', e?.message||e);
    process.exit(3);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
