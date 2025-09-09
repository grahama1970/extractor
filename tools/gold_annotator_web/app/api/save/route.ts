import { NextRequest, NextResponse } from "next/server";
import { writeFile, mkdirSync } from "fs";
import { join, resolve } from "path";

const REPO_ROOT = resolve(process.cwd(), "../..");

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const relPath = String(body.path || "");
    const payload = body.data;
    if (!relPath) return NextResponse.json({ error: "path required" }, { status: 400 });

    const outPath = resolve(join(REPO_ROOT, relPath));
    if (!outPath.startsWith(REPO_ROOT)) return NextResponse.json({ error: "path escapes repo" }, { status: 400 });
    mkdirSync(join(outPath, ".."), { recursive: true });
    await new Promise((res, rej) => writeFile(outPath, JSON.stringify(payload, null, 2) + "\n", (e) => e ? rej(e) : res(null)));
    return NextResponse.json({ ok: true, path: outPath });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
