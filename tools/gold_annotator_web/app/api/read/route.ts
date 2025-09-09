import { NextRequest, NextResponse } from "next/server";
import { readFileSync } from "fs";
import { join, resolve } from "path";

const REPO_ROOT = resolve(process.cwd(), "../..");

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const rel = String(searchParams.get('path') || '');
    if (!rel) return NextResponse.json({ error: 'path required' }, { status: 400 });
    const abs = resolve(join(REPO_ROOT, rel));
    if (!abs.startsWith(REPO_ROOT)) return NextResponse.json({ error: 'path escapes repo' }, { status: 400 });
    const text = readFileSync(abs, 'utf-8');
    return NextResponse.json({ path: rel, text });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
