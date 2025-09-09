import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import { resolve, join } from "path";
import { existsSync } from "fs";

const REPO_ROOT = resolve(process.cwd(), "../..");
const SCRIPT = resolve(process.cwd(), "scripts", "annotate_pdf.py");

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const pdfRel = String(body.pdf || "");
    const doc = String(body.doc || "");
    if (!pdfRel || !doc) return NextResponse.json({ error: "pdf and doc required" }, { status: 400 });

    const pdfPath = resolve(join(REPO_ROOT, pdfRel));
    if (!pdfPath.startsWith(REPO_ROOT)) return NextResponse.json({ error: "pdf path escapes repo" }, { status: 400 });

    const imagesRootEnv = process.env.IMAGES_ROOT ? resolve(join(REPO_ROOT, process.env.IMAGES_ROOT)) : null;
    const imagesRootA = imagesRootEnv || resolve(join(REPO_ROOT, "data", "images"));
    const imagesRootB = resolve(join(REPO_ROOT, "data", "labelstudio", "images"));
    const imagesRoot = existsSync(imagesRootA) ? imagesRootA : imagesRootB;
    const boxesPath = resolve(join(imagesRoot, doc, `${doc}.boxes.json`));
    if (!boxesPath.startsWith(REPO_ROOT)) return NextResponse.json({ error: "boxes path escapes repo" }, { status: 400 });
    if (!existsSync(boxesPath)) return NextResponse.json({ error: `boxes json not found for doc '${doc}'` }, { status: 400 });

    const outRel = join("data", "annotated_pdfs", `${doc}_annotated.pdf`);
    const outPath = resolve(join(REPO_ROOT, outRel));

    await new Promise<void>((resolvePromise, rejectPromise) => {
      const proc = spawn("python3", [SCRIPT, "--pdf", pdfPath, "--boxes", boxesPath, "--out", outPath], { stdio: "inherit" });
      proc.on("exit", (code) => (code === 0 ? resolvePromise() : rejectPromise(new Error("annotate failed"))));
    });

    return NextResponse.json({ ok: true, out: outRel });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
