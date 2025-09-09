import { NextResponse } from "next/server";
import { readdirSync, existsSync, statSync } from "fs";
import { join, resolve } from "path";

const REPO_ROOT = resolve(process.cwd(), "../..");
function getPdfRoot() {
  const envRel = process.env.PDF_ROOT || "tools/gold_annotator_web/data/input";
  return resolve(join(REPO_ROOT, envRel));
}

export async function GET(req: Request) {
  try {
    const url = new URL(req.url);
    const recursive = url.searchParams.get('recursive') === '1';
    const root = getPdfRoot();
    const baseRel = root.replace(REPO_ROOT + '/', '').replace(REPO_ROOT, '');
    if (!existsSync(root)) return NextResponse.json({ root, baseRel, pdfs: [] });
    if (!recursive) {
      const items = readdirSync(root)
        .filter((f) => f.toLowerCase().endsWith(".pdf"))
        .filter((f) => {
          try { return statSync(join(root, f)).isFile(); } catch { return false; }
        })
        .map((f) => join(baseRel, f));
      return NextResponse.json({ root, baseRel, pdfs: items });
    }
    const results: string[] = [];
    const walk = (dirRel: string) => {
      const dirAbs = resolve(join(root, dirRel));
      let items: string[] = [];
      try { items = readdirSync(dirAbs); } catch { return; }
      for (const name of items) {
        const abs = resolve(join(dirAbs, name));
        const relFromRoot = join(baseRel, dirRel, name).replace(/\\/g, '/');
        try {
          const st = statSync(abs);
          if (st.isDirectory()) walk(join(dirRel, name));
          else if (name.toLowerCase().endsWith('.pdf')) results.push(relFromRoot);
        } catch {}
      }
    };
    walk("");
    results.sort();
    return NextResponse.json({ root, baseRel, pdfs: results });
  } catch (e: any) {
    const root = getPdfRoot();
    const baseRel = root.replace(REPO_ROOT + '/', '').replace(REPO_ROOT, '');
    return NextResponse.json({ root, baseRel, pdfs: [], warn: e.message });
  }
}
