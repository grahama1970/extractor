import { NextRequest, NextResponse } from "next/server";
import { createReadStream, existsSync } from "fs";
import { join, resolve } from "path";

const REPO_ROOT = resolve(process.cwd(), "../..");

function getImagesRoot() {
  const envRoot = process.env.IMAGES_ROOT ? resolve(join(REPO_ROOT, process.env.IMAGES_ROOT)) : null;
  const candidateA = envRoot || resolve(join(REPO_ROOT, "data", "images"));
  const candidateB = resolve(join(REPO_ROOT, "data", "labelstudio", "images"));
  return existsSync(candidateA) ? candidateA : candidateB;
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const doc = String(searchParams.get("doc") || "");
    const file = String(searchParams.get("file") || "");
    if (!doc || !file) return NextResponse.json({ error: "doc and file required" }, { status: 400 });
    const root = getImagesRoot();
    const p = resolve(join(root, doc, file));
    if (!p.startsWith(root)) return NextResponse.json({ error: "path escapes images root" }, { status: 400 });
    if (!existsSync(p)) return NextResponse.json({ error: "not found" }, { status: 404 });
    const ext = file.toLowerCase().endsWith(".jpg") ? "image/jpeg" : "image/png";
    const stream = createReadStream(p);
    return new Response(stream as any, { headers: { "Content-Type": ext } });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

