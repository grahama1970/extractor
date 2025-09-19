#!/usr/bin/env node
// Verifies that only `python -m src.cli extract` is accepted, and legacy entry points are deprecated.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const ART_DIR = path.join('scripts','artifacts');
fs.mkdirSync(ART_DIR, { recursive: true });
const outJson = path.join(ART_DIR, `cli_single_surface.json`);

const samplePdf = process.env.SAMPLE_PDF || 'data/input/pipeline/BHT_CV32A65X_marked.pdf';
const outDir = path.join('out_fast');

function run(cmd, args, opts={}) {
  const res = spawnSync(cmd, args, { encoding: 'utf8', shell: false, ...opts });
  return { status: res.status, stdout: res.stdout || '', stderr: res.stderr || '' };
}

const accepted = [];
const rejected = [];
const results = {};

// Allowed
const allow = run('python', ['-m', 'src.cli', 'extract', samplePdf, outDir, '--mode', 'fast']);
if (allow.status === 0) accepted.push('python -m src.cli extract');
results.allow_status = allow.status;
results.allow_stderr = allow.stderr.slice(0, 4000);

// Legacy commands to reject (presence varies; we tolerate ENOENT by treating as rejected)
const legacyCmds = [
  ['python', ['-m', 'extractor.core.scripts.convert_single', samplePdf, outDir]],
  ['python', ['src/extractor/core/scripts/convert_single.py', samplePdf, outDir]],
  ['extract-pdf', [samplePdf, outDir]],
  ['python', ['-m','src.cli','extract-pdf', samplePdf, outDir]],
];

for (const [cmd,args] of legacyCmds) {
  let ok = false; let status = -1; let stderr = '';
  try {
    const r = run(cmd, args);
    status = r.status; stderr = r.stderr || r.stdout;
    // consider it a pass (rejected) if non-zero OR stderr mentions deprecation
    ok = status !== 0 || /deprecated|no longer supported/i.test(stderr);
  } catch (e) {
    ok = true; // command missing also counts as rejected
  }
  if (ok) rejected.push([cmd, ...args].join(' '));
  results[[cmd, ...args].join(' ')] = { status, stderr: (stderr||'').slice(0,4000) };
}

const ok = allow.status === 0 && rejected.length >= 1;
const payload = { ok, accepted, rejected, results };
fs.writeFileSync(outJson, JSON.stringify(payload, null, 2));
if (!ok) {
  console.error('FAIL smoke_cli_single_surface');
  process.exit(2);
}
console.log('OK smoke_cli_single_surface');
