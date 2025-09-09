import { NextRequest, NextResponse } from "next/server";
import { resolve, join, sep } from "path";
import { existsSync, readFileSync, statSync } from "fs";

// Serves files under node_modules/pdfjs-dist/build so module worker can import its relatives.
export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  try {
    const parts = (params.path || []).filter(Boolean);
    // Only allow files under build/
    const base = resolve(process.cwd(), "node_modules", "pdfjs-dist", "build");
    let target = resolve(join(base, ...parts));
    if (!target.startsWith(base)) return NextResponse.json({ error: "path escapes base" }, { status: 400 });
    if (!existsSync(target) || !statSync(target).isFile()) return NextResponse.json({ error: "not found" }, { status: 404 });
    const buf = readFileSync(target);
    const ext = target.split('.').pop()?.toLowerCase();
    const type = ext === 'mjs' ? 'text/javascript' : ext === 'js' ? 'application/javascript' : 'application/octet-stream';
    return new NextResponse(buf, { headers: { 'Content-Type': type, 'Cache-Control': 'public, max-age=3600' } });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
