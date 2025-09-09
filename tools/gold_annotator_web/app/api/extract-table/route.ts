import { NextRequest, NextResponse } from "next/server";
import { resolve, join } from "path";
import { spawn } from "child_process";
import { tmpdir } from "os";
import { mkdtempSync, writeFileSync, rmSync } from "fs";

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

    // Write cropped image to a temp file for the LiteLLM call
    const dir = mkdtempSync(join(tmpdir(), "extract-table-"));
    const imgPath = join(dir, "region.png");
    try {
      const b64 = payload.png_base64 as string;
      const buf = Buffer.from(b64, "base64");
      writeFileSync(imgPath, buf);
    } catch (e: any) {
      rmSync(dir, { recursive: true, force: true });
      return NextResponse.json({ error: "failed to persist crop image" }, { status: 500 });
    }

    // Use the project's LiteLLM thin wrapper to perform a JSON-mode extraction.
    // It auto-detects local image paths in the prompt text.
    const prompt = buildPrompt(imgPath);
    const model = process.env.LITELLM_MODEL || process.env.LITELLM_VLM_MODEL; // prefer any configured model
    const pyPath = resolve(process.cwd(), "src", "extractor", "pipeline", "utils", "litellm_call.py");
    const llmArgs = [pyPath, "--response-format", "json_object", "--timeout", "60"]; // respect LiteLLM JSON mode
    llmArgs.push(prompt);
    const llm = await runPython(["-u", ...llmArgs]);
    try {
      rmSync(dir, { recursive: true, force: true });
    } catch {}
    if (llm.code !== 0) {
      // Fallback to manual paste path with the image and prompt for user to use externally
      return NextResponse.json({
        error: llm.stderr || "llm extract failed",
        prompt: prompt,
        image_base64: payload.png_base64,
        contentType: "image/png",
      }, { status: 500 });
    }

    // Parse the LLM JSON result. litellm_call returns text; with JSON mode it should be JSON.
    let table: any = {};
    try {
      table = JSON.parse((llm.stdout || "").trim());
    } catch (e: any) {
      return NextResponse.json({ error: "invalid LLM JSON", raw: (llm.stdout || "").slice(0, 500) }, { status: 500 });
    }
    // Normalize accepted shapes: {columns, rows, title?} or {table: {...}}
    if (table && table.table && typeof table.table === 'object') {
      table = table.table;
    }
    if (!Array.isArray(table.columns) || !Array.isArray(table.rows)) {
      return NextResponse.json({ error: "missing columns/rows in extraction" }, { status: 500 });
    }
    return NextResponse.json({ table });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

function buildPrompt(imgPath: string) {
  return `You are a precise document table extractor. Extract the table from this image: ${imgPath}
Return ONLY a compact JSON object with this schema and nothing else:
{
  "type": "table",
  "title": string | null,
  "columns": string[],
  "rows": string[][]
}
Rules:
- Use the image to detect headers and rows accurately.
- Clean header names minimally (trim spaces, preserve content).
- Each row must have the same number of columns; pad empty cells with "".
- If a table title appears within the crop, put it in "title", else null.
- Do NOT include any explanations.`;
}
