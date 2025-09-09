import { NextResponse } from "next/server";
import { readdirSync, statSync, existsSync } from "fs";
import { join } from "path";

const REPO_ROOT = join(process.cwd(), "../..");
function getImagesRoot() {
  const envRoot = process.env.IMAGES_ROOT ? join(REPO_ROOT, process.env.IMAGES_ROOT) : null;
  const candidateA = envRoot || join(REPO_ROOT, "data", "images");
  const candidateB = join(REPO_ROOT, "data", "labelstudio", "images");
  if (existsSync(candidateA)) return candidateA;
  if (existsSync(candidateB)) return candidateB;
  // default to new path location
  return candidateA;
}

export async function GET() {
  try {
    const IMAGES_ROOT = getImagesRoot();
    const docs = existsSync(IMAGES_ROOT) ? readdirSync(IMAGES_ROOT).filter((d) => statSync(join(IMAGES_ROOT, d)).isDirectory()) : [];
    const map: Record<string, string[]> = {};
    for (const d of docs) {
      const dir = join(IMAGES_ROOT, d);
      const pages = existsSync(dir) ? readdirSync(dir).filter((f) => f.endsWith(".png") || f.endsWith(".jpg")).sort() : [];
      map[d] = pages;
    }
    return NextResponse.json({ root: IMAGES_ROOT, docs: map });
  } catch (e: any) {
    return NextResponse.json({ root: getImagesRoot(), docs: {}, warn: e.message });
  }
}
