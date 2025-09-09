import { NextRequest, NextResponse } from "next/server";
import { join, resolve } from "path";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";

const REPO_ROOT = resolve(process.cwd(), "../..");
const DIR = join(REPO_ROOT, "tools", "gold_annotator_web", "proto");
const FILE = join(DIR, "canvas_state.json");

 type ExcalState = { elements: any[]; appState?: any; files?: Record<string, any> } | null;
 type Stored = { version: number; state: ExcalState };
 
 function readStored(): Stored {
   try {
     if (!existsSync(FILE)) return { version: 1, state: null };
     const j = JSON.parse(readFileSync(FILE, "utf8"));
     if (j && typeof j.version === "number" && "state" in j) return j as Stored;
     return { version: 1, state: j } as Stored;
   } catch {
     return { version: 1, state: null };
   }
 }
 
 function writeStored(s: Stored) {
   mkdirSync(DIR, { recursive: true });
   writeFileSync(FILE, JSON.stringify(s, null, 2));
 }

export async function GET() {
  try {
    const s = readStored();
    return NextResponse.json({ version: s.version, state: s.state });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function PUT(req: NextRequest) {
  try {
    const body = await req.json();
    const ifVersion = typeof body.ifVersion === "number" ? body.ifVersion : undefined;
    const state = body.state as ExcalState;
    const cur = readStored();
    if (ifVersion && ifVersion != cur.version) {
      return NextResponse.json({ error: "version_conflict", currentVersion: cur.version }, { status: 409 });
    }
    const next: Stored = { version: cur.version + 1, state };
    writeStored(next);
    return NextResponse.json({ ok: true, version: next.version });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}


export async function PATCH(req: NextRequest) {
  try {
    const body = await req.json();
    const ifVersion = typeof body.ifVersion === "number" ? body.ifVersion : undefined;
    const ops: any[] = Array.isArray(body.ops) ? body.ops : [];
    const cur = readStored();
    if (ifVersion && ifVersion != cur.version) {
      return NextResponse.json({ error: "version_conflict", currentVersion: cur.version }, { status: 409 });
    }
    const state: any = cur.state || { elements: [], appState: {}, files: {} };
    const elements: any[] = Array.isArray(state?.elements) ? [...state.elements] : [];
    const findIdx = (id: string) => elements.findIndex((el) => el && el.id === id);
    const genId = () => `id_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
    for (const op of ops) {
      if (op.op === 'add_shape') {
        const id = op.id || genId();
        if (op.type === 'rectangle') {
          elements.push({ id, type: 'rectangle', x: op.x, y: op.y, width: op.w ?? 160, height: op.h ?? 80, strokeColor: '#1f2937', backgroundColor: 'transparent' });
        } else if (op.type === 'text') {
          elements.push({ id, type: 'text', x: op.x, y: op.y, text: op.text ?? '', fontSize: 20, width: op.w ?? 200, height: op.h ?? 30 });
        }
      } else if (op.op === 'update') {
        const idx = findIdx(op.id);
        if (idx >= 0) {
          const el = { ...elements[idx] };
          if (typeof op.x === 'number') el.x = op.x;
          if (typeof op.y === 'number') el.y = op.y;
          if (typeof op.w === 'number') el.width = op.w;
          if (typeof op.h === 'number') el.height = op.h;
          if (typeof op.text === 'string') el.text = op.text;
          elements[idx] = el;
        }
      } else if (op.op === 'delete') {
        const idx = findIdx(op.id);
        if (idx >= 0) elements.splice(idx, 1);
      }
    }
    const next = { version: cur.version + 1, state: { ...state, elements } };
    writeStored(next as any);
    return NextResponse.json({ ok: true, version: next.version });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}