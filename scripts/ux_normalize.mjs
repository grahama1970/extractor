
import fs from 'node:fs';
import path from 'node:path';

const INBOX = path.resolve('docs', 'ux', 'inbox');
const OUT_DIR = path.resolve('docs', 'ux', 'notes');
fs.mkdirSync(OUT_DIR, { recursive: true });

const toSlug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,64) || 'untitled';

const read = (p) => fs.readFileSync(p, 'utf-8');
const write = (p, s) => fs.writeFileSync(p, s, 'utf-8');

const parse = (txt) => {
  const title = (txt.match(/^#\s+(.+)$/m) || [,'Untitled'])[1].trim();
  const route = (txt.match(/^Route:\s*(.+)$/mi) || [,'(unknown)'])[1].trim();
  const viewport = (txt.match(/^Viewport:\s*(.+)$/mi) || [,'1440x900'])[1].trim();
  return { title, route, viewport };
};

const template = ({ title, route, viewport }, body) => `# ${title}

Route: ${route}  
Viewport: ${viewport}

## Summary
- Auto-normalized from inbox freeform note.

## Details
${body}
`;

const main = async () => {
  const files = fs.readdirSync(INBOX).filter(f => f.toLowerCase().endsWith('.md') && f !== 'TEMPLATE.md');
  for (const f of files) {
    const p = path.join(INBOX, f);
    const txt = read(p);
    const meta = parse(txt);
    const slug = toSlug(meta.title);
    const out = path.join(OUT_DIR, `${slug}.md`);
    write(out, template(meta, txt));
    console.log(`normalized: ${f} -> notes/${slug}.md`);
  }
};

main().catch(e => { console.error('ux_normalize failed:', e); process.exit(2); });
