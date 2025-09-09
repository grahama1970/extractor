import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import { resolve, join } from "path";

const REPO_ROOT = resolve(process.cwd(), "../..");
const SCRIPT = resolve(process.cwd(), "scripts", "render_pdf.py");

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const pdf = String(body.pdf || "");
    const out = String(body.out || "");
    const dpi = Number(body.dpi || 300);
    if (!pdf || !out) return NextResponse.json({ error: "pdf and out required" }, { status: 400 });
    const pdfPath = resolve(join(REPO_ROOT, pdf));
    const outDir = resolve(join(REPO_ROOT, out));
    if (!pdfPath.startsWith(REPO_ROOT) || !outDir.startsWith(REPO_ROOT)) return NextResponse.json({ error: "paths must be inside repo" }, { status: 400 });
    await new Promise<void>((resolvePromise, rejectPromise) => {
      const proc = spawn("python3", [SCRIPT, "--pdf", pdfPath, "--out", outDir, "--dpi", String(dpi)], { stdio: "inherit" });
      proc.on("exit", (code) => (code === 0 ? resolvePromise() : rejectPromise(new Error("render failed"))));
    });
    return NextResponse.json({ ok: true, out: outDir });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
