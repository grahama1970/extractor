#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--id') args.id = argv[++i];
    else if (a === '--title') args.title = argv[++i];
    else if (a === '--dir') args.dir = argv[++i];
    else args._.push(a);
  }
  return args;
}

function slugify(s) {
  return (s || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function detectNextId(dir) {
  try {
    const files = fs.readdirSync(dir);
    let max = 0;
    for (const f of files) {
      const m = f.match(/^(\d{3})_/);
      if (m) max = Math.max(max, parseInt(m[1], 10));
    }
    return (max + 1).toString().padStart(3, '0');
  } catch {
    return '001';
  }
}

function issueTemplate(id, title, opt={}) {
  const now = new Date().toISOString();
  const location = opt.location || '__FILL_ME__';
  const routes = (opt.routes || '/classic').split(/[\s,]+/).filter(Boolean);
  const contextParts = [];
  if (opt.context) contextParts.push(opt.context);
  if (opt.stdin) contextParts.push(opt.stdin);
  for (const img of (opt.images || [])) contextParts.push(`![image](${img})`);
  const context = contextParts.join('\n\n') || 'Short context and screenshot.';
  const accept = (opt.accept || []).map(a => `- [ ] ${a}`).join('\n') || '- [ ] Failing smoke exists and passes after fix\n- [ ] Verified on /classic\n- [ ] Artifacts linked below';
  return `# url:

## Issue
Location: ${location}
Task: ${title || '__FILL_ME__'}

## Context
${context}

## Desired Behavior
What the user expects to see/do.

## Acceptance
${accept}

## Routes
${routes.map(r => `- ${r}`).join('\n')}

## Selectors (if known)
- __FILL_ME__

## Smokes to add
- scripts/smokes/issue_${id}.mjs

## Artifacts
- scripts/artifacts/issue_${id}_*.{log,png}

## Meta
- id: ${id}
- created_at: ${now}

Last_smoke_at: (pending)
Last_suite_at: (pending)
Last_smoke_at: (pending)
Last_suite_at: (pending)
Status: Open
`;
}

function smokeStub(id) {
  return `import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts','artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }
const ts = () => new Date().toISOString().replace(/[:.]/g,'-');

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/classic', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });

  // TODO: replace with real assertions from the issue acceptance
  const ok = false; // start as failing until you implement acceptance

  const stamp = ts();
  const shot = path.join(OUT_DIR, `issue_${id}_\${stamp}.png`);
  await page.screenshot({ path: shot, fullPage: true }).catch(()=>{});
  const log = path.join(OUT_DIR, `issue_${id}_\${stamp}.log`);
  fs.writeFileSync(log, [\
    `BASE_URL=\${BASE}`,\
    `ok=\${ok}`,\
    `screenshot=\${shot}`\
  ].join('\n'));
  await page.close(); await browser.disconnect();
  if (!ok) { console.error('issue_${id}: FAIL (fill acceptance)'); process.exit(1); }
  console.log('issue_${id}: OK');
  process.exit(0);
})().catch(e => { console.error('issue_${id} crashed:', e.message || e); process.exit(2); });
`;
}

function addVsTask(tasksPath, id) {
  try {
    const json = JSON.parse(fs.readFileSync(tasksPath, 'utf-8'));
    json.tasks = json.tasks || [];
    const label = `Smokes: Issue ${id}`;
    if (!json.tasks.find(t => t.label === label)) {
      json.tasks.push({
        label,
        type: 'shell',
        command: 'bash',
        args: ['-lc', `BASE_URL=\"\${input:uxRoute}\" node scripts/smokes/issue_${id}.mjs`],
        problemMatcher: [],
        presentation: { reveal: 'always', panel: 'dedicated' }
      });
    }
    fs.writeFileSync(tasksPath, JSON.stringify(json, null, 2));
    return true;
  } catch (e) {
    console.error('Failed to update VS Code tasks:', e.message || e);
    return false;
  }
}

// Main
const args = parseArgs(process.argv);
const issuesDir = path.resolve(args.dir || 'prototypes/tabbed/issues');
fs.mkdirSync(issuesDir, { recursive: true });
const id = (args.id && args.id.match(/^\d+$/)) ? args.id.padStart(3,'0') : detectNextId(issuesDir);
const slug = slugify(args.title || 'new_issue');
const issuePath = path.join(issuesDir, `${id}_${slug}.md`);
const opt = { location: args.location, routes: args.routes, context: args.context, stdin: undefined, images: [], accept: [] };
try { opt.stdin = fs.readFileSync(0, 'utf-8'); } catch {}
opt.images = []; // no inline image copy; user can pass relative paths later
opt.accept = []; // accept bullets can be added later; leaving minimal acceptance
if (!fs.existsSync(issuePath)) fs.writeFileSync(issuePath, issueTemplate(id, args.title, opt));
console.log('Issue at', issuePath);

// Smoke stub
const smokePath = path.resolve('scripts','smokes', `issue_${id}.mjs`);
if (!fs.existsSync(smokePath)) fs.writeFileSync(smokePath, smokeStub(id));
console.log('Smoke stub at', smokePath);

// VS Code task
addVsTask(path.resolve('.vscode','tasks.json'), id);
console.log('VS Code task added: Smokes: Issue', id);

process.exit(0);
