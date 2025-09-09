import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";
import { resolve, join } from "path";
import { existsSync, mkdirSync, statSync, readFileSync } from "fs";
import { spawn } from "child_process";

const REPO_ROOT = resolve(process.cwd(), "../..");
const SCRIPT = resolve(process.cwd(), "scripts", "render_page.py");
const CACHE_ROOT = join(REPO_ROOT, "tmp", "pdf_pages");
const TTL_MS = 14 /*days*/ * 24 * 60 * 60 * 1000;

function sha(s: string) {
  return createHash("sha256").update(s).digest("hex");
}

function ensureDir(p: string) {
  if (!existsSync(p)) mkdirSync(p, { recursive: true });
}

async function runPython(args: string[]): Promise<{ code: number; stdout: string; stderr: string }>{
  return new Promise((resolve) => {
    const proc = spawn("python3", args, { cwd: process.cwd() });
    let stdout = "", stderr = "";
    proc.stdout.on("data", d => stdout += d.toString());
    proc.stderr.on("data", d => stderr += d.toString());
    proc.on("exit", code => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const pdfRel = String(searchParams.get("pdf") || "");
    const page = Math.max(1, Number(searchParams.get("page") || 1));
    const dpi = Math.max(48, Number(searchParams.get("dpi") || 96));
    if (!pdfRel) return NextResponse.json({ error: "pdf required" }, { status: 400 });
    const pdfPath = resolve(join(REPO_ROOT, pdfRel));
    if (!pdfPath.startsWith(REPO_ROOT)) return NextResponse.json({ error: "path escapes repo" }, { status: 400 });
    const key = sha(`${pdfPath}|${dpi}`);
    const dir = join(CACHE_ROOT, key, String(dpi));
    ensureDir(dir);
    const outPath = join(dir, `${page}.png`);
    const now = Date.now();
    let needRender = true;
    if (existsSync(outPath)) {
      try { const m = statSync(outPath).mtimeMs; if (now - m < TTL_MS) needRender = false; } catch {}
    }
    if (needRender) {
      const res = await runPython([SCRIPT, "--pdf", pdfPath, "--page", String(page), "--out", outPath, "--dpi", String(dpi)]);
      if (res.code !== 0) {
        return NextResponse.json({ error: res.stderr || "render failed" }, { status: 500 });
      }
    }
    const buf = readFileSync(outPath);
    return new NextResponse(buf, { headers: { "Content-Type": "image/png", "Cache-Control": "public, max-age=3600" } });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

