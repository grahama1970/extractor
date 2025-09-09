import { NextRequest, NextResponse } from "next/server";
import { resolve, join } from "path";
import { spawn } from "child_process";

const REPO_ROOT = resolve(process.cwd(), "../..");
// Scripts are colocated under this app's scripts/ directory when running dev from tools/gold_annotator_web
const SCRIPT = resolve(process.cwd(), "scripts", "export_region_image.py");

function runPython(args: string[]): Promise<{ code: number; stdout: string; stderr: string }>{
  return new Promise((resolvePromise) => {
    const proc = spawn("python3", args, { cwd: process.cwd() });
    let stdout = ""; let stderr = "";
    proc.stdout.on("data", (d) => stdout += d.toString());
    proc.stderr.on("data", (d) => stderr += d.toString());
    proc.on("exit", (code) => resolvePromise({ code: code ?? 1, stdout, stderr }));
  });
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const pdf = String(body.pdf || "");
    const page = Number(body.page || 1);
    const box = body.box || { x: 0, y: 0, w: 1, h: 1 };
    const zoom = Number(body.zoom || 2.0);
    if (!pdf) return NextResponse.json({ error: "pdf required" }, { status: 400 });
    const pdfPath = resolve(join(REPO_ROOT, pdf));
    if (!pdfPath.startsWith(REPO_ROOT)) return NextResponse.json({ error: "path escapes repo" }, { status: 400 });

    const args = ["-u", SCRIPT, "--pdf", pdfPath, "--page", String(page), "--rect", `${box.x},${box.y},${box.w},${box.h}`, "--zoom", String(zoom)];
    const res = await runPython(args);
    if (res.code !== 0) {
      return NextResponse.json({ error: res.stderr || "crop failed" }, { status: 500 });
    }
    const payload = JSON.parse(res.stdout || "{}");
    return NextResponse.json({ image: payload.png_base64, width: payload.width, height: payload.height, zoom: payload.zoom, contentType: "image/png" });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
