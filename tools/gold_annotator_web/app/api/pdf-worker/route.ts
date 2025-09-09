import { NextResponse } from "next/server";
import { readFileSync } from "fs";
import { resolve } from "path";

export async function GET() {
  try {
    const workerPath = resolve(process.cwd(), "node_modules/pdfjs-dist/build/pdf.worker.min.mjs");
    const code = readFileSync(workerPath, "utf-8");
    return new NextResponse(code, { headers: { "Content-Type": "application/javascript" } });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

