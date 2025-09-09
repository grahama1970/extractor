import { NextRequest, NextResponse } from "next/server";
import { join, resolve } from "path";
import { mkdirSync, existsSync, writeFileSync } from "fs";

const REPO_ROOT = resolve(process.cwd(), "../..");

function getPdfRoot() {
  const envRel = process.env.PDF_ROOT || "tools/gold_annotator_web/data/input";
  return resolve(join(REPO_ROOT, envRel));
}

function sanitizeName(name: string) {
  const base = name.replace(/\\/g, "/").split("/").pop() || "upload.pdf";
  return base.replace(/[^a-zA-Z0-9._-]+/g, "_");
}

export async function POST(req: NextRequest) {
  try {
    const data = await req.formData();
    const files = data.getAll("file");
    if (!files || files.length === 0) return NextResponse.json({ error: "file required" }, { status: 400 });
    const root = getPdfRoot();
    mkdirSync(root, { recursive: true });
    const saved: string[] = [];
    for (const f of files) {
      // @ts-ignore - Next provides Blob/File
      const file: File = f as any;
      const name = sanitizeName(file.name || "upload.pdf");
      const outPath = resolve(join(root, name));
      if (!outPath.startsWith(root)) return NextResponse.json({ error: "path escapes root" }, { status: 400 });
      const buf = Buffer.from(await file.arrayBuffer());
      // Avoid clobber by adding numeric suffix
      let finalPath = outPath;
      let tries = 0;
      const stem = name.replace(/\.pdf$/i, "");
      const ext = name.toLowerCase().endsWith(".pdf") ? ".pdf" : "";
      while (existsSync(finalPath) && tries < 999) {
        tries += 1;
        const candidate = `${stem}_${String(tries).padStart(2, "0")}${ext}`;
        finalPath = resolve(join(root, candidate));
      }
      writeFileSync(finalPath, buf);
      const rel = finalPath.replace(REPO_ROOT + "/", "");
      saved.push(rel);
    }
    return NextResponse.json({ ok: true, saved });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
