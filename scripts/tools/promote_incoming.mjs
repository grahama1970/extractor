#!/usr/bin/env node
// Split raw multi-topic issues in prototypes/tabbed/issues/incoming into atomic issues + smokes.
import fs from 'node:fs';
import path from 'node:path';

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

function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }

function issueTemplate(id, title, context) {
  const now = new Date().toISOString();
  return `# url:\n\n## Issue\nLocation: __FILL_ME__\nTask: ${title}\n\n## Context\n${context || ''}\n\n## Desired Behavior\n__FILL_ME__\n\n## Acceptance\n- [ ] Failing smoke exists and passes after fix\n- [ ] Verified on /classic\n- [ ] Artifacts linked below\n\n## Routes\n- /classic\n\n## Selectors (if known)\n- __FILL_ME__\n\n## Smokes to add\n- scripts/smokes/issue_${id}.mjs\n\n## Artifacts\n- scripts/artifacts/issue_${id}_*.{log,png}\n\n## Meta\n- id: ${id}\n- created_at: ${now}\n\nLast_smoke_at: (pending)\nLast_suite_at: (pending)\nStatus: Open\n`;
}

function splitSections(md) {
  const lines = md.split(/\r?\n/);
  const sections = [];
  let cur = null;
  for (const line of lines) {
    const m = line.match(/^###\s+(.+)$/);
    const sep = line.trim() === '---';
    if (m) {
      if (cur) sections.push(cur);
      cur = { title: m[1].trim(), body: '' };
    } else if (sep) {
      if (cur) { sections.push(cur); cur = null; }
    } else {
      if (!cur) cur = { title: 'Untitled', body: '' };
      cur.body += line + '\n';
    }
  }
  if (cur) sections.push(cur);
  return sections.filter(s => s.title && s.title.trim());
}

function promoteFile(incomingPath, issuesDir, smokesDir, tasksPath) {
  const raw = fs.readFileSync(incomingPath, 'utf-8');
  const sections = splitSections(raw);
  if (!sections.length) {
    console.log('No sections found in', incomingPath);
    return [];
  }
  const created = [];
  for (const sec of sections) {
    const id = detectNextId(issuesDir);
    const slug = slugify(sec.title).slice(0, 60) || 'new_issue';
    const issuePath = path.join(issuesDir, `${id}_${slug}.md`);
    fs.writeFileSync(issuePath, issueTemplate(id, sec.title, sec.body));
    // smoke stub
    const smokePath = path.join(smokesDir, `issue_${id}.mjs`);
    if (!fs.existsSync(smokePath)) {
      fs.writeFileSync(smokePath, `import puppeteer from 'puppeteer-core';\nimport fs from 'node:fs';\nimport path from 'node:path';\nconst BASE=process.env.BASE_URL||'http://127.0.0.1:8080';\nconst DISC=process.env.BROWSERLESS_DISCOVERY_URL||'http://127.0.0.1:3000/json/version';\nconst OUT=path.resolve('scripts','artifacts');fs.mkdirSync(OUT,{recursive:true});\nasync function getWS(){try{const r=await fetch(DISC);const j=await r.json();if(j.webSocketDebuggerUrl)return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1');}catch{}return null;}\nconst ts=()=>new Date().toISOString().replace(/[:.]/g,'-');\n(async()=>{const ws=await getWS();if(!ws){console.error('No CDP');process.exit(3);}const b=await puppeteer.connect({browserWSEndpoint:ws,defaultViewport:null});const p=await b.newPage();await p.goto(BASE.replace(/\/$/,'')+'/classic',{waitUntil:'domcontentloaded'});await p.waitForSelector('[data-testid="page-label"]',{timeout:10000});const ok=false;const stamp=ts();const shot=path.join(OUT,'issue_${id}_'+stamp+'.png');await p.screenshot({path:shot,fullPage:true}).catch(()=>{});const log=path.join(OUT,'issue_${id}_'+stamp+'.log');fs.writeFileSync(log,[`BASE_URL=${BASE}`,`ok=${ok}`,`screenshot=${shot}`].join('\n'));await p.close();await b.disconnect();if(!ok){console.error('issue_${id}: FAIL (fill acceptance)');process.exit(1);}console.log('issue_${id}: OK');process.exit(0);} )().catch(e=>{console.error('issue_${id} crashed:',e.message||e);process.exit(2);});`);
    }
    // VS Code task append
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
    } catch {}
    created.push({ id, issuePath });
  }
  // Move incoming to archive with summary
  const archiveDir = path.join(path.dirname(incomingPath), 'archive');
  ensureDir(archiveDir);
  const base = path.basename(incomingPath);
  const newPath = path.join(archiveDir, base);
  const links = created.map(c => `- ${path.basename(c.issuePath)}`).join('\n');
  fs.writeFileSync(incomingPath, fs.readFileSync(incomingPath,'utf-8') + `\n\n---\nPromoted:\n${links}\n`);
  fs.renameSync(incomingPath, newPath);
  return created;
}

const incomingDir = path.resolve('prototypes','tabbed','issues','incoming');
const issuesDir   = path.resolve('prototypes','tabbed','issues');
const smokesDir   = path.resolve('scripts','smokes');
const tasksPath   = path.resolve('.vscode','tasks.json');

fs.mkdirSync(incomingDir, { recursive: true });
const files = fs.readdirSync(incomingDir).filter(f => f.endsWith('.md'));
if (!files.length) { console.log('No incoming md files'); process.exit(0); }
const results = [];
for (const f of files) {
  const created = promoteFile(path.join(incomingDir, f), issuesDir, smokesDir, tasksPath);
  results.push({ file: f, created });
}
console.log(JSON.stringify(results, null, 2));
process.exit(0);

