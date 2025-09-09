import { NextRequest, NextResponse } from "next/server";
import { resolve, join } from "path";
import { spawn } from "child_process";

const REPO_ROOT = resolve(process.cwd(), "../..");
// Scripts are colocated under this app's scripts/ directory when running dev from tools/gold_annotator_web
const SCRIPT = resolve(process.cwd(), "scripts", "extract_region_text.py");

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
    if (!pdf) return NextResponse.json({ error: "pdf required" }, { status: 400 });
    const pdfPath = resolve(join(REPO_ROOT, pdf));
    if (!pdfPath.startsWith(REPO_ROOT)) return NextResponse.json({ error: "path escapes repo" }, { status: 400 });
    const args = [SCRIPT, "--pdf", pdfPath, "--page", String(page), "--rect", `${box.x},${box.y},${box.w},${box.h}`];
    const res = await runPython(["-u", ...args]);
    if (res.code !== 0) {
      // graceful degradation: return empty suggestions
      return NextResponse.json({ suggestions: [], warn: res.stderr || "extract failed" });
    }
    const payload = JSON.parse(res.stdout || "{}");
    const text: string = payload.text || "";
    const suggestions = heuristics(text, box);
    return NextResponse.json({ suggestions, text });
  } catch (e: any) {
    return NextResponse.json({ error: e.message, suggestions: [] }, { status: 500 });
  }
}

function heuristics(text: string, _box: any) {
  const t = (text || "").trim();
  const lower = t.toLowerCase();
  const lines = t.split(/\r?\n/).filter(Boolean);
  const alphaNumDensity = (t.replace(/[^\w]+/g, "").length) / (t.length || 1);
  const hasManyLines = lines.length >= 3;
  const hasTableHeaders = /(name|type|direction|description|parameter|register|bit|width)/i.test(t);
  const multiColSeparators = /\s{2,}|[,\t\|;]/.test(t);
  const containsFigure = /(figure\s*\d+|fig\.)/i.test(t);
  const containsSection = /(section\s*\d+|overview|introduction|summary)/i.test(t);
  const containsReq = /(shall|must|should|will)/i.test(t);

  const scores: Record<string, number> = {
    table: 0,
    section: 0,
    requirements: 0,
    figure: 0,
  };
  // Table scoring
  if (hasManyLines) scores.table += 0.2;
  if (hasTableHeaders) scores.table += 0.5;
  if (multiColSeparators) scores.table += 0.3;
  // Section scoring
  if (containsSection) scores.section += 0.6;
  if (alphaNumDensity > 0.6 && lines.length < 10) scores.section += 0.2;
  // Requirements scoring
  if (containsReq) scores.requirements += 0.6;
  if (lines.length > 1) scores.requirements += 0.1;
  // Figure scoring
  if (containsFigure) scores.figure += 0.8;
  if (alphaNumDensity < 0.4 && lines.length <= 5) scores.figure += 0.1;

  const out = Object.entries(scores)
    .map(([type, score]) => ({ type, confidence: Math.max(0, Math.min(1, score)), expected_json: defaultJsonPath(type, t) }))
    .filter(s => s.confidence > 0)
    .sort((a, b) => b.confidence - a.confidence);
  return out;
}

function defaultJsonPath(type: string, idLike: string) {
  const slug = (idLike || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 40) || "item";
  const base = type === 'table' ? 'tables' : type;
  return `data/gold_standards/${base}/${slug}.json`;
}
