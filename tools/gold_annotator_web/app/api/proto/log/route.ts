import { NextRequest, NextResponse } from "next/server";
import { join, resolve } from "path";
import { mkdirSync, appendFileSync, existsSync, readFileSync } from "fs";

const REPO_ROOT = resolve(process.cwd(), "../..");
const DIR = join(REPO_ROOT, "tools", "gold_annotator_web", "proto");
const FILE = join(DIR, "client_errors.jsonl");

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    mkdirSync(DIR, { recursive: true });
    const line = JSON.stringify({
      ts: new Date().toISOString(),
      ua: req.headers.get("user-agent") || "",
      ...body,
    }) + "\n";
    appendFileSync(FILE, line, { encoding: "utf8" });
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message || String(e) }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const n = Math.max(1, Math.min(500, parseInt(searchParams.get('n') || '100', 10)));
    if (!existsSync(FILE)) return NextResponse.json({ lines: [] });
    const text = readFileSync(FILE, 'utf8');
    const lines = text.trim().split(/\r?\n+/);
    const tail = lines.slice(-n);
    return NextResponse.json({ lines: tail });
  } catch (e: any) {
    return NextResponse.json({ error: e.message || String(e) }, { status: 500 });
  }
}
