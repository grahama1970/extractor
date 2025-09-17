#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function parseArgs(argv) {
  const args = { artifacts: [] };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--id') args.id = argv[++i];
    else if (a === '--status') args.status = argv[++i];
    else if (a === '--smoke') args.smoke = argv[++i];
    else if (a === '--suite') args.suite = argv[++i];
    else if (a === '--smoke-now') args.smoke = new Date().toISOString();
    else if (a === '--suite-now') args.suite = new Date().toISOString();
    else if (a === '--artifact') args.artifacts.push(argv[++i]);
  }
  return args;
}

function findIssueFile(dir, id) {
  const files = fs.readdirSync(dir).filter(f => f.match(/^\d{3}_.*\.md$/));
  const wanted = files.find(f => f.startsWith(id.padStart(3,'0') + '_'));
  if (!wanted) throw new Error(`Issue ${id} not found in ${dir}`);
  return path.join(dir, wanted);
}

function upsertLine(lines, key, value) {
  const idx = lines.findIndex(l => l.trimStart().toLowerCase().startsWith(key.toLowerCase()));
  const newLine = `${key} ${value}`;
  if (idx >= 0) lines[idx] = newLine; else lines.push(newLine);
}

const args = parseArgs(process.argv);
if (!args.id) { console.error('Usage: update_issue_status.mjs --id NNN [--status STATUS] [--smoke-now|--smoke ISO] [--suite-now|--suite ISO] [--artifact PATH]...'); process.exit(1); }

const issuesDir = path.resolve('prototypes','tabbed','issues');
const file = findIssueFile(issuesDir, args.id);
let content = fs.readFileSync(file, 'utf-8');
let lines = content.split(/\r?\n/);

if (args.status) upsertLine(lines, 'Status:', args.status);
if (args.smoke) upsertLine(lines, 'Last_smoke_at:', args.smoke);
if (args.suite) upsertLine(lines, 'Last_suite_at:', args.suite);

if (args.artifacts && args.artifacts.length) {
  const artIdx = lines.findIndex(l => l.trim().toLowerCase() === '## artifacts');
  if (artIdx >= 0) {
    for (const a of args.artifacts) lines.splice(artIdx+1, 0, `- ${a}`);
  } else {
    lines.push('## Artifacts');
    for (const a of args.artifacts) lines.push(`- ${a}`);
  }
}

fs.writeFileSync(file, lines.join('\n'));
console.log('Updated', file);

