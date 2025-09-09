import { NextRequest, NextResponse } from "next/server";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { resolve, join } from "path";

const REPO_ROOT = resolve(process.cwd(), "../..");

function getImagesRoot() {
  const envRoot = process.env.IMAGES_ROOT ? resolve(join(REPO_ROOT, process.env.IMAGES_ROOT)) : null;
  const candidateA = envRoot || resolve(join(REPO_ROOT, "data", "images"));
  const candidateB = resolve(join(REPO_ROOT, "data", "labelstudio", "images"));
  return existsSync(candidateA) ? candidateA : candidateB;
}

function boxesPathForDoc(doc: string) {
  const imagesRoot = getImagesRoot();
  const dir = resolve(join(imagesRoot, doc));
  if (!dir.startsWith(REPO_ROOT)) throw new Error("doc path escapes repo");
  return resolve(join(dir, `${doc}.boxes.json`));
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const doc = searchParams.get("doc");
    if (!doc) return NextResponse.json({ error: "doc required" }, { status: 400 });
    const p = boxesPathForDoc(doc);
    if (!existsSync(p)) return NextResponse.json({ boxes: [] });
    const data = JSON.parse(readFileSync(p, "utf-8"));
    return NextResponse.json({ boxes: data });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const doc = String(body.doc || "");
    const boxes = body.boxes || [];
    if (!doc) return NextResponse.json({ error: "doc required" }, { status: 400 });
    const p = boxesPathForDoc(doc);
    mkdirSync(resolve(join(p, "..")), { recursive: true });
    writeFileSync(p, JSON.stringify(boxes, null, 2) + "\n");
    return NextResponse.json({ ok: true, path: p });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
