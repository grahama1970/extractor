#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--dir') args.dir = argv[++i];
    else if (a === '--id') args.id = argv[++i];
    else if (a === '--title') args.title = argv[++i];
    else if (a === '--path') args.path = argv[++i];
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
    const next = (max + 1).toString().padStart(3, '0');
    return next;
  } catch {
    return '001';
  }
}

function template(id, title) {
  const now = new Date().toISOString();
  return `# url:\n\n## Issue\nLocation: __FILL_ME__\nTask: ${title || '__FILL_ME__'}\n\n---\n\nResolution (TBD)\n\n- Summary:\n- Changes:\n\nAcceptance\n\n- [ ] Verify on /classic\n- [ ] Update artifacts\n\nArtifacts/Files\n\n- __FILL_ME__\n\nMeta\n\n- id: ${id}\n- created_at: ${now}\n\nStatus: Open\n`;
}

const args = parseArgs(process.argv);

try {
  let outPath;
  if (args.path) {
    outPath = path.resolve(args.path);
    const dir = path.dirname(outPath);
    fs.mkdirSync(dir, { recursive: true });
    const base = path.basename(outPath);
    const m = base.match(/^(\d{3})_([^.]*)/);
    const id = m ? m[1] : (args.id || '001');
    const title = args.title || (m ? m[2].replace(/_/g, ' ') : '');
    if (fs.existsSync(outPath)) {
      console.log('Issue exists:', outPath);
      process.exit(0);
    }
    fs.writeFileSync(outPath, template(id, title));
    console.log('Created', outPath);
    process.exit(0);
  }

  const dir = path.resolve(args.dir || 'prototypes/tabbed/issues');
  fs.mkdirSync(dir, { recursive: true });
  const id = (args.id && args.id.match(/^\d+$/)) ? args.id.padStart(3, '0') : detectNextId(dir);
  const slug = slugify(args.title || 'new_issue');
  const filename = `${id}_${slug || 'new_issue'}.md`;
  outPath = path.join(dir, filename);
  if (fs.existsSync(outPath)) {
    console.log('Issue exists:', outPath);
    process.exit(0);
  }
  fs.writeFileSync(outPath, template(id, args.title));
  console.log('Created', outPath);
  process.exit(0);
} catch (e) {
  console.error('Failed to create issue:', e.message || e);
  process.exit(1);
}

