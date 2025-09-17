import { execSync } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

function getGitShort() {
  try {
    return execSync('git rev-parse --short HEAD', { encoding: 'utf8' }).trim();
  } catch {
    return 'unknown';
  }
}

const payload = { git: getGitShort(), built_at: new Date().toISOString() };
// Support running from repo root OR from the frontend dir
let outDir;
try {
  // If a local public/ exists, use it
  outDir = resolve('public');
  mkdirSync(outDir, { recursive: true });
} catch {
  // Fallback to repo-root path
  outDir = resolve('prototypes/tabbed/html/public');
  try { mkdirSync(outDir, { recursive: true }); } catch {}
}
const outPath = resolve(outDir, 'build.json');
writeFileSync(outPath, JSON.stringify(payload, null, 2));
console.log('Wrote', outPath, payload);
