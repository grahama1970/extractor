/* eslint-disable no-console */
import fs from 'node:fs';
import path from 'node:path';

const ROOT = 'prototypes/tabbed/html/src';
const ENDPOINT_RX = /\/api\/(build|list|pipeline\/latest|requirements\/list)/;
const GUARD_RX = /(isPreview\(|isDev\()/;
const WINDOW_UP = 3; // lines above must include a guard

function walk(dir, files=[]) {
  for (const e of fs.readdirSync(dir, { withFileTypes:true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, files);
    else if (e.isFile() && /\.(t|j)sx?$/.test(e.name)) files.push(p);
  }
  return files;
}

function checkFile(file){
  const txt = fs.readFileSync(file, 'utf8').split('\n');
  const offenders = [];
  for (let i=0; i<txt.length; i++){
    const line = txt[i];
    if (!ENDPOINT_RX.test(line)) continue;
    let guarded = false;
    for (let k=1; k<=WINDOW_UP && (i-k)>=0; k++) {
      if (GUARD_RX.test(txt[i-k])) { guarded = true; break; }
    }
    if (!guarded) offenders.push({ file, line: i+1, text: line.trim() });
  }
  return offenders;
}

function main(){
  const files = walk(ROOT);
  let bad=[];
  for (const f of files) bad = bad.concat(checkFile(f));
  if (bad.length){
    console.error('[lint-api-gates] Found ungated mount-time /api references:');
    for (const o of bad) console.error(`${o.file}:${o.line}: ${o.text}`);
    process.exit(1);
  }
  console.log('[lint-api-gates] OK');
}

main();
