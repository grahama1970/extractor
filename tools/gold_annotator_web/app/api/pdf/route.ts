import { NextRequest, NextResponse } from "next/server";
import { readFileSync } from "fs";
import { resolve, join } from "path";

const REPO_ROOT = resolve(process.cwd(), "../..");

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const p = searchParams.get("path");
    if (!p) return NextResponse.json({ error: "path required" }, { status: 400 });
    const abs = resolve(join(REPO_ROOT, p));
    if (!abs.startsWith(REPO_ROOT)) return NextResponse.json({ error: "path escapes repo" }, { status: 400 });
    const buf = readFileSync(abs);
    return new NextResponse(buf, { headers: { "Content-Type": "application/pdf" } });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
