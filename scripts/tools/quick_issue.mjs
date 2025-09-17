#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function parseArgs(argv){
  const a={_:[]};
  for(let i=2;i<argv.length;i++){
    const k=argv[i];
    if(k==='--title') a.title=argv[++i];
    else if(k==='--route') a.route=argv[++i];
    else if(k==='--selector') a.selector=argv[++i];
    else if(k==='--contains') a.contains=argv[++i];
    else if(k==='--id') a.id=argv[++i];
    else if(k==='--dir') a.dir=argv[++i];
    else a._.push(k);
  }
  return a;
}

function slugify(s){return (s||'').toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/_+/g,'_').replace(/^_+|_+$/g,'');}
function detectNextId(dir){try{const f=fs.readdirSync(dir);let m=0;for(const x of f){const r=x.match(/^(\d{3})_/);if(r)m=Math.max(m,parseInt(r[1],10));}return (m+1).toString().padStart(3,'0');}catch{return '001';}}

const args=parseArgs(process.argv);
const issuesDir=path.resolve(args.dir||'prototypes/tabbed/issues');
fs.mkdirSync(issuesDir,{recursive:true});
const id=(args.id&&args.id.match(/^\d+$/))?args.id.padStart(3,'0'):detectNextId(issuesDir);
const title=args.title||'quick_issue';
const route=args.route||'/classic';
const selector=args.selector||'[data-testid="page-label"]';
const contains=args.contains||'';
const slug=slugify(title);
const issuePath=path.join(issuesDir,`${id}_${slug}.md`);

const body=`# url:

## Issue
Location: ${route}
Task: ${title}

## Acceptance
- [ ] Element exists: \`${selector}\`${contains?` and contains "${contains}"`:''}

## Routes
- ${route}

## Smokes to add
- scripts/smokes/issue_${id}.mjs

## Artifacts
- scripts/artifacts/issue_${id}_*.{log,png}

## Meta
- id: ${id}
Last_smoke_at: (pending)
Status: Open
`;
if(!fs.existsSync(issuePath)) fs.writeFileSync(issuePath,body);

const smokePath=path.resolve('scripts','smokes',`issue_${id}.mjs`);
if(!fs.existsSync(smokePath)){
  const smoke=`import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';
const BASE=process.env.BASE_URL||'http://127.0.0.1:8080';
const DISC=process.env.BROWSERLESS_DISCOVERY_URL||'http://127.0.0.1:3000/json/version';
const OUT=path.resolve('scripts','artifacts');fs.mkdirSync(OUT,{recursive:true});
async function ws(){try{const r=await fetch(DISC);const j=await r.json();if(j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1');}catch{}return null;}
const ts=()=>new Date().toISOString().replace(/[:.]/g,'-');
(async()=>{const w=await ws();if(!w){console.error('No CDP');process.exit(3);}const b=await puppeteer.connect({browserWSEndpoint:w,defaultViewport:null});const p=await b.newPage();
await p.goto(BASE.replace(/\/$/,'')+'${route}',{waitUntil:'domcontentloaded'});
await p.waitForSelector('${selector}',{timeout:10000});
let ok=true;${contains?`const txt=await p.$eval('${selector}',el=>el.innerText||el.textContent||''); ok = txt.includes(${JSON.stringify(contains)});`:''}
const stamp=ts();const shot=path.join(OUT,'issue_${id}_'+stamp+'.png');await p.screenshot({path:shot,fullPage:true}).catch(()=>{});const log=path.join(OUT,'issue_${id}_'+stamp+'.log');
fs.writeFileSync(log,[\
  'BASE_URL='+BASE,\
  'route=${route}',\
  'selector=${selector}',\
  ${contains?`'contains=${contains}',`:' '}
  'ok='+ok,\
  'screenshot='+shot\
].join('\n'));
await p.close();await b.disconnect();
if(!ok){console.error('issue_${id}: FAIL');process.exit(1);}console.log('issue_${id}: OK');process.exit(0);
})().catch(e=>{console.error('issue_${id} crashed:',e.message||e);process.exit(2);});
`;
  fs.writeFileSync(smokePath,smoke);
}

// add VS Code task entry
try{
  const tasksPath=path.resolve('.vscode','tasks.json');
  const json=JSON.parse(fs.readFileSync(tasksPath,'utf-8'));
  json.tasks=json.tasks||[];
  const label=`Smokes: Issue ${id}`;
  if(!json.tasks.find(t=>t.label===label)){
    json.tasks.push({label,type:'shell',command:'bash',args:['-lc',`BASE_URL=\"\${input:uxRoute}\" node scripts/smokes/issue_${id}.mjs`],problemMatcher:[],presentation:{reveal:'always',panel:'dedicated'}});
  }
  fs.writeFileSync(tasksPath,JSON.stringify(json,null,2));
}catch{}

console.log('Created', issuePath);
console.log('Smoke stub at', smokePath);
console.log('VS Code task added: Smokes: Issue', id);
process.exit(0);

