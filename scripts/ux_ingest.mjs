import fs from 'node:fs';
import path from 'node:path';

// Lightweight ingestion of UX notes: scan docs/ux/inbox for *.md and images
// Generate docs/ux/index.md with links; optionally move processed notes to docs/ux/processed

const ROOT = process.cwd();
const INBOX = path.resolve('docs', 'ux', 'inbox');
const PROCESSED = path.resolve('docs', 'ux', 'processed');
const OUT_INDEX = path.resolve('docs', 'ux', 'index.md');

fs.mkdirSync(INBOX, { recursive: true });
fs.mkdirSync(PROCESSED, { recursive: true });

const isMd = (p) => /\.md$/i.test(p);

const main = async () => {
  const entries = fs.readdirSync(INBOX).filter(f => isMd(f));
  const lines = [
    '# UX Notes Index',
    '',
    `Updated: ${new Date().toISOString()}`,
    '',
  ];
  for (const f of entries) {
    const p = path.join(INBOX, f);
    const txt = fs.readFileSync(p, 'utf-8');
    // extract first heading and optional route tag
    const title = (txt.match(/^#\s+(.+)$/m) || [,'(untitled)'])[1];
    const route = (txt.match(/^Route:\s*(.+)$/mi) || [,'(unknown)'])[1];
    lines.push(`- [${title} – ${route}](inbox/${encodeURIComponent(f)})`);
  }
  fs.writeFileSync(OUT_INDEX, lines.join('\n'), 'utf-8');
  console.log(`Index written: ${OUT_INDEX}`);
};

main().catch((e)=>{ console.error('ux_ingest failed:', e); process.exit(2); });

