#!/usr/bin/env node
// Verifies PDF fast and accurate modes using the single CLI produce expected artifacts.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const ART_DIR = path.join('scripts','artifacts');
fs.mkdirSync(ART_DIR, { recursive: true });
const outJson = path.join(ART_DIR, `cli_pdf_modes.json`);

const samplePdf = process.env.SAMPLE_PDF || 'data/input/pipeline/BHT_CV32A65X_marked.pdf';
const fastOut = path.join('out_fast');
const accOut = path.join('data','results','pipeline');

function sh(cmd, args, opts={}) {
  const r = spawnSync(cmd, args, { encoding:'utf8', shell:false, ...opts });
  return { status: r.status, stdout: r.stdout || '', stderr: r.stderr || '' };
}
function exists(p) { try { return fs.existsSync(p); } catch { return false; } }

// Run fast
const f = sh('python', ['-m','src.cli','extract', samplePdf, fastOut, '--mode','fast']);
const stem = path.basename(samplePdf).replace(/\.pdf$/i,'');
const fastArtifact = path.join(fastOut, `${stem}_fast.json`);
const okFast = f.status === 0 && exists(fastArtifact);

// Run accurate
const a = sh('python', ['-m','src.cli','extract', samplePdf, accOut, '--mode','accurate']);
const acc07 = path.join(accOut,'07_reflow_section','json_output','07_reflowed.json');
const acc10 = path.join(accOut,'10_arangodb_exporter','json_output','10_flattened_data.json');
const okAcc = a.status === 0 && exists(acc07) && exists(acc10);

const payload = {
  ok_fast: okFast,
  ok_accurate: okAcc,
  status_fast: f.status,
  status_accurate: a.status,
  fast_artifact: fastArtifact,
  acc07, acc10,
};
fs.writeFileSync(outJson, JSON.stringify(payload, null, 2));
const ok = okFast && okAcc;
if (!ok) { console.error('FAIL smoke_cli_pdf_modes'); process.exit(2); }
console.log('OK smoke_cli_pdf_modes');
