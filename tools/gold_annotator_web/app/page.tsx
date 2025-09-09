"use client";
import * as React from "react";
import dynamic from "next/dynamic";
import { Table as TableIcon, FileText, ListChecks, Image as ImageIcon, Type as TypeIcon, Eye as EyeIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PdfTree } from "@/components/PdfTree";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const PdfViewer = dynamic(() => import("@/components/PdfViewer").then(m => m.PdfViewer), { ssr: false });
const OverlayCanvas = dynamic(() => import("@/components/OverlayCanvas").then(m => m.OverlayCanvas), { ssr: false }) as any;

type LabelType = 'table' | 'section' | 'requirements' | 'figure' | 'text';
type CBox = { id: string; page: number; x: number; y: number; w: number; h: number; type?: LabelType; expected_json?: string; part_idx?: number; notes?: string };

export default function Page() {
  // Document + viewer state
  const [pdfs, setPdfs] = React.useState<string[]>([]);
  const [pdfPath, setPdfPath] = React.useState("tools/gold_annotator_web/data/input/BHT CV32A65X.pdf");
  const [pdfUrl, setPdfUrl] = React.useState<string>("");
  const [pdfQuery, setPdfQuery] = React.useState("");
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const [pageIdx, setPageIdx] = React.useState(0);
  const [pageCount, setPageCount] = React.useState(0);
  const [scale, setScale] = React.useState(1.2);
  const [viewport, setViewport] = React.useState<{w:number;h:number}>({w:1000,h:1400});

  // Boxes + selection
  const [boxes, setBoxes] = React.useState<CBox[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [defaultType, setDefaultType] = React.useState<LabelType>('table');
  const [doc, setDoc] = React.useState<string>("");

  // Inspector fields
  const [bName, setBNameState] = React.useState("");
  const [bType, setBTypeState] = React.useState<LabelType>('table');
  const [bExpected, setBExpectedState] = React.useState("");
  const [bPart, setBPartState] = React.useState("");
  const nameRef = React.useRef<HTMLInputElement | null>(null);
  const [goldJson, setGoldJson] = React.useState<string>("");

  // UI helpers
  const [visibleTypes, setVisibleTypes] = React.useState<Set<LabelType>>(new Set(['table','section','requirements','figure','text']));
  const [saveState, setSaveState] = React.useState<'idle'|'dirty'|'saving'|'saved'|'error'>('idle');
  const [showThumbs, setShowThumbs] = React.useState(true);
  const autoSaveRef = React.useRef<any>(null);

  // Load PDFs (recursive)
  React.useEffect(() => {
    fetch('/api/pdfs?recursive=1')
      .then(r=>r.json())
      .then(j=> setPdfs(Array.isArray(j.pdfs)? j.pdfs: []))
      .catch(()=>{});
  }, []);

  const onLoadPdf = () => {
    const url = `/api/pdf?path=${encodeURIComponent(pdfPath)}`;
    setPdfUrl(url);
    setPageIdx(0);
    // Auto-fill doc name from filename if empty
    if (!doc && pdfPath) {
      const base = (pdfPath.split('/').pop() || '').replace(/\.pdf$/i, '');
      const slug = base.replace(/[^a-zA-Z0-9]+/g, '_');
      setDoc(slug);
    }
  };

  // Load saved boxes when doc changes
  React.useEffect(() => {
    if (!doc) return;
    fetch(`/api/boxes?doc=${encodeURIComponent(doc)}`)
      .then(r=>r.json()).then(j=> setBoxes(j.boxes || []))
      .catch(()=>{});
  }, [doc]);

  // Sync inspector when selection changes
  React.useEffect(() => {
    const sel = boxes.find(b=>b.id===selectedId);
    if (!sel) return;
    setBNameState(sel.id);
    setBTypeState((sel.type||'table'));
    setBExpectedState(sel.expected_json||"");
    setBPartState(sel.part_idx!=null? String(sel.part_idx):"");
  }, [selectedId]);

  const updateBox=(id:string,patch:Partial<CBox>)=> setBoxes(prev=>prev.map(b=>b.id===id?{...b,...patch}:b));
  const setBName=(v:string)=>{ setBNameState(v); if(selectedId){ setBoxes(prev=>prev.map(b=>b.id===selectedId?{...b,id:v}:b)); setSelectedId(v);} };
  const setBType=(v:LabelType)=>{ setBTypeState(v); if(selectedId) updateBox(selectedId,{type:v}); };
  const setBExpected=(v:string)=>{ setBExpectedState(v); if(selectedId) updateBox(selectedId,{expected_json:v}); };
  const setBPart=(v:string)=>{ setBPartState(v); if(selectedId) updateBox(selectedId,{part_idx: v.trim()===''? undefined: Number(v)}); };

  const saveBoxes=async()=>{
    try {
      setSaveState('saving');
      const res = await fetch('/api/boxes', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ doc, boxes })});
      if (!res.ok) throw new Error(String(res.status));
      setSaveState('saved');
      setTimeout(()=> setSaveState('idle'), 1500);
    } catch {
      setSaveState('error');
    }
  };

  const exportAnnotated = async () => {
    try {
      if (!pdfPath || !doc) { alert('Set PDF and doc name first'); return; }
      const res = await fetch('/api/export-annotated', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pdf: pdfPath, doc }) });
      const j = await res.json();
      if (!res.ok) { alert(j.error || 'Export failed'); return; }
      const out = j.out; if (out) window.open(`/api/pdf?path=${encodeURIComponent(out)}`, '_blank');
    } catch { alert('Export failed'); }
  };

  const saveGold=async()=>{
    try {
      let path = bExpected;
      if(!path){ const base=bType==='table'?'tables':bType; path=`data/gold_standards/${base}/${bName||selectedId}.json`; setBExpectedState(path); if (selectedId) updateBox(selectedId,{ expected_json: path }); }
      let payload: any;
      try { payload = goldJson?.trim()? JSON.parse(goldJson) : (bType==='table'? {type:'table', id:bName, columns:[], rows:[]} : {type:bType, id:bName, title:`INFERRED: ${bName}`, columns:[], rows:[]}); }
      catch (e) { alert('Gold JSON is not valid JSON'); return; }
      await fetch('/api/save',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ path, data: payload })});
    } catch {}
  };

  const onRendered=(w:number,h:number)=> setViewport(v=> (v.w!==w||v.h!==h)?{w,h}:v);

  // Mark dirty + autosave
  React.useEffect(() => {
    if (!doc) return;
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
    setSaveState((s)=> s==='saving' ? s : 'dirty');
    autoSaveRef.current = setTimeout(() => { saveBoxes(); }, 800);
    return () => { if (autoSaveRef.current) clearTimeout(autoSaveRef.current); };
  }, [boxes, doc]);

  // Keyboard page nav
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase();
      const isEditable = tag==='input'||tag==='textarea'||tag==='select'||(e.target as any)?.isContentEditable;
      if (isEditable) return;
      if (e.key === 'ArrowLeft') setPageIdx(p=> Math.max(0, p-1));
      else if (e.key === 'ArrowRight') setPageIdx(p=> Math.min(pageCount-1, p+1));
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [pageCount]);

  const toggleTypeVisible = (t: LabelType) => {
    setVisibleTypes(prev => { const next = new Set(prev); if (next.has(t)) next.delete(t); else next.add(t); return next; });
  };
  const showAllTypes = () => setVisibleTypes(new Set(['table','section','requirements','figure','text']));

  return (
    <div className="flex h-screen">
      {/* Left: pinned controls + simple list */}
      <aside className="w-72 border-r p-3 flex flex-col min-h-0">
        <h2 className="font-semibold">Document</h2>
        <div className="space-y-2">
          <Label>PDF path</Label>
          <Input data-testid="pdf-input" value={pdfPath} onChange={e=>setPdfPath(e.target.value)} placeholder="tools/gold_annotator_web/data/input/....pdf" />
          <div className="flex gap-2">
            <Button data-testid="load-pdf-btn" variant="secondary" onClick={onLoadPdf}>Load PDF</Button>
            <Input value={doc} onChange={e=>setDoc(e.target.value)} placeholder="doc name (for boxes)" />
          </div>
          <div className="flex items-center gap-2">
            <input ref={fileInputRef} type="file" accept="application/pdf" multiple onChange={e=> (async()=>{ try{ const files=e.target.files; if(!files||files.length===0) return; const fd=new FormData(); Array.from(files).forEach(f=>fd.append('file', f)); const res=await fetch('/api/upload', { method: 'POST', body: fd }); const j=await res.json(); if(!res.ok){ alert(j.error||'Upload failed'); return;} const r=await fetch('/api/pdfs?recursive=1'); const jr=await r.json(); setPdfs(Array.isArray(jr.pdfs)? jr.pdfs: []); }catch{ alert('Upload failed'); } })()} />
            <Button size="sm" variant="secondary" onClick={()=> fileInputRef.current?.click()}>Add PDFs…</Button>
          </div>
        </div>
        <div className="mt-2 space-y-2 flex-1 min-h-0">
          <div>
            <div className="text-xs text-muted-foreground mb-1">Search</div>
            <Input data-testid="pdf-search" value={pdfQuery} onChange={e=>setPdfQuery(e.target.value)} placeholder="Filter PDFs by name" />
          </div>
          <div className="space-y-1 flex-1 min-h-0">
            <div className="text-xs text-muted-foreground">PDFs</div>
            {pdfs.length === 0 ? (
              <div className="text-sm text-muted-foreground">No PDFs found. Add PDFs above or enter a path.</div>
            ) : (
              <div className="flex-1 min-h-0 overflow-auto border rounded p-1">
                {(() => {
                  const ROOT = "tools/gold_annotator_web/data/input";
                  const files = pdfs
                    .filter(rel => !pdfQuery || rel.toLowerCase().includes(pdfQuery.toLowerCase()))
                    .map(rel => (rel.startsWith(ROOT+"/") ? rel.slice((ROOT+"/").length) : rel));
                  const currentDisp = pdfPath.startsWith(ROOT+"/") ? pdfPath.slice((ROOT+"/").length) : pdfPath;
                  return (
                    <PdfTree
                      files={files}
                      current={currentDisp}
                      onSelect={(display) => {
                        const full = display.startsWith(ROOT+"/") ? display : `${ROOT}/${display}`;
                        setPdfPath(full);
                        setPdfUrl(`/api/pdf?path=${encodeURIComponent(full)}`);
                      }}
                    />
                  );
                })()}
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Center: viewer + overlay */}
      <main className="flex-1 overflow-auto">
        <div className="p-2">
          {pdfUrl ? (
            <div style={{ position:"relative", width: viewport.w, height: viewport.h }}>
              <PdfViewer url={pdfUrl} pageNumber={pageIdx+1} scale={scale} onRendered={onRendered} onDocLoaded={setPageCount} />

              {/* Viewer toolbar: default label tool + keyboard hints */}
              <div style={{ position:'absolute', left:8, top:8, zIndex:10 }}>
                <div className="flex items-center gap-1 rounded border bg-white/80 backdrop-blur px-2 py-1 text-xs">
                  <span className="opacity-60 mr-1">Tool:</span>
                  <Button size="sm" variant={defaultType==='table'?'default':'secondary'} onClick={()=>setDefaultType('table')} title="Table"><TableIcon size={14}/></Button>
                  <Button size="sm" variant={defaultType==='section'?'default':'secondary'} onClick={()=>setDefaultType('section')} title="Section"><FileText size={14}/></Button>
                  <Button size="sm" variant={defaultType==='requirements'?'default':'secondary'} onClick={()=>setDefaultType('requirements')} title="Requirements"><ListChecks size={14}/></Button>
                  <Button size="sm" variant={defaultType==='figure'?'default':'secondary'} onClick={()=>setDefaultType('figure')} title="Figure"><ImageIcon size={14}/></Button>
                  <Button size="sm" variant={defaultType==='text'?'default':'secondary'} onClick={()=>setDefaultType('text')} title="Text"><TypeIcon size={14}/></Button>
                  <span className="ml-2 opacity-60">Hints: <kbd className="px-1 border rounded">V</kbd> box • <kbd className="px-1 border rounded">←/→</kbd> page</span>
                </div>
              </div>

              {/* Label filters (show/hide types) */}
              <div style={{ position:'absolute', right:8, top:8, zIndex:10 }}>
                <div className="flex items-center gap-1 rounded border bg-white/80 backdrop-blur px-2 py-1 text-xs">
                  <EyeIcon size={14} className="opacity-60 mr-1" />
                  {(['table','section','requirements','figure','text'] as LabelType[]).map(t => (
                    <Button key={t} size="sm" variant={visibleTypes.has(t)?'default':'outline'} onClick={()=>toggleTypeVisible(t)} title={`Toggle ${t}`}>{t.slice(0,1).toUpperCase()}</Button>
                  ))}
                  <Button size="sm" variant="secondary" onClick={showAllTypes} title="Show all">All</Button>
                </div>
              </div>

              <div style={{ position:'absolute', left:0, top:0 }} data-testid="overlay-layer">
                <OverlayCanvas
                  page={pageIdx+1}
                  width={viewport.w}
                  height={viewport.h}
                  boxes={boxes.filter(b=>b.page===pageIdx+1).filter(b => !b.type || visibleTypes.has(b.type as LabelType))}
                  selectedId={selectedId}
                  onSelect={(id:string|null)=>setSelectedId(id)}
                  onCreate={(nb:CBox)=>{ const next={...nb, type: defaultType} as CBox; setBoxes(prev=>[...prev,next]); setSelectedId(next.id); setBNameState(next.id); setBTypeState(defaultType); setTimeout(()=>nameRef.current?.focus(),0); }}
                  onDelete={(id:string)=>{ setBoxes(prev=>prev.filter(b=>b.id!==id)); setSelectedId(null); }}
                  onChange={(pageBoxes:CBox[])=>{ const others=boxes.filter(b=>b.page!==pageIdx+1); setBoxes([...others, ...pageBoxes]); }}
                />
              </div>

              {/* Bottom bar: page controls, status chip, thumbnails, export */}
              <div style={{ position:'absolute', left:8, right:8, bottom:8, zIndex:10 }}>
                <div className="rounded border bg-white/80 backdrop-blur px-2 py-1 text-xs">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="secondary" onClick={()=>setPageIdx(p=>Math.max(0,p-1))} disabled={pageIdx<=0}>Prev</Button>
                      <span>{pageIdx+1} / {pageCount}</span>
                      <Button size="sm" variant="secondary" onClick={()=>setPageIdx(p=>Math.min(pageCount-1,p+1))} disabled={pageIdx>=pageCount-1}>Next</Button>
                    </div>
                    <div className="ml-auto flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded border ${saveState==='dirty'?'border-amber-500 text-amber-700': saveState==='saving'?'border-blue-500 text-blue-700': saveState==='saved'?'border-emerald-500 text-emerald-700': saveState==='error'?'border-rose-500 text-rose-700':'border-slate-300 text-slate-600'}`}>
                        {saveState==='dirty'?'Pending': saveState==='saving'?'Saving…': saveState==='saved'?'Saved': saveState==='error'?'Error':'Idle'}
                      </span>
                      <Button size="sm" variant="secondary" onClick={saveBoxes}>Save Boxes</Button>
                      <Button size="sm" variant="secondary" onClick={exportAnnotated}>Export Annotated</Button>
                      <Button size="sm" variant="secondary" onClick={()=>setShowThumbs(v=>!v)}>{showThumbs? 'Hide' : 'Show'} thumbs</Button>
                    </div>
                  </div>
                  {showThumbs && pageCount>0 && (
                    <div className="mt-1 flex items-center gap-2 overflow-x-auto py-1">
                      {(() => {
                        const start = Math.max(1, (pageIdx+1)-3);
                        const end = Math.min(pageCount, (pageIdx+1)+3);
                        const pages = [] as number[];
                        for (let p=start; p<=end; p++) pages.push(p);
                        return pages.map(p => (
                          <button key={p} className={`border rounded ${p-1===pageIdx? 'border-black' : 'border-slate-300'}`} onClick={()=>setPageIdx(p-1)}>
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img alt={`p${p}`} src={`/api/page-image?pdf=${encodeURIComponent(pdfPath)}&page=${p}&dpi=56`} className="block h-16" />
                          </button>
                        ));
                      })()}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : <p>Load a PDF to start.</p>}
        </div>
      </main>

      {/* Right: inspector */}
      <aside className="w-80 border-l p-3 space-y-3">
        <h2 className="font-semibold">Inspector</h2>
        {!selectedId ? (
          <div className="text-sm text-muted-foreground">No selection. Draw a region then edit its properties here.</div>
        ) : (
          <div className="space-y-2">
            <Label>Type</Label>
            <div className="flex gap-1 flex-wrap">
              {(['table','section','requirements','figure','text'] as LabelType[]).map(t => (
                <Button key={t} size="sm" variant={bType===t? 'default':'secondary'} onClick={()=>setBType(t)}>{t}</Button>
              ))}
            </div>
            <Label>ID</Label>
            <div className="flex items-center gap-2">
              <Input ref={nameRef} value={bName} onChange={e=>setBName(e.target.value)} />
              <Button size="sm" variant="outline" title="Rename ID to match type prefix" onClick={()=>{
                if (!selectedId) return;
                const sel = boxes.find(b=>b.id===selectedId); if (!sel) return;
                const m = sel.id.match(/^[^_]+_(.+)$/); const suffix = m? m[1] : sel.id;
                const next = `${bType}_${suffix}`;
                setBoxes(prev => prev.map(b => b.id===sel.id ? { ...b, id: next } : b));
                setSelectedId(next); setBNameState(next);
              }}>Prefix→{bType}</Button>
            </div>
            <Label>expected_json</Label>
            <div className="flex items-center gap-2">
              <Input value={bExpected} onChange={e=>setBExpected(e.target.value)} placeholder={`data/gold_standards/${bType==='table'?'tables':bType}/${bName||selectedId}.json`} />
              {!bExpected && (
                <Button size="sm" variant="secondary" onClick={()=>{ const base=bType==='table'?'tables':bType; const def=`data/gold_standards/${base}/${bName||selectedId}.json`; setBExpected(def); if (selectedId) updateBox(selectedId,{ expected_json: def }); }}>Use default</Button>
              )}
            </div>
            <Label>part_idx</Label>
            <Input value={bPart} onChange={e=>setBPart(e.target.value)} placeholder="optional" />
            <Label>notes</Label>
            <Textarea rows={3} value={(boxes.find(b=>b.id===selectedId)?.notes)||''} onChange={e=>{ if (selectedId) updateBox(selectedId, { notes: e.target.value }); }} />
            <div className="flex gap-2 flex-wrap pt-2">
              <Button onClick={saveBoxes}>Save Boxes</Button>
              <Button variant="outline" onClick={saveGold}>Save Gold</Button>
              <Button variant="outline" title="Duplicate selected" onClick={()=>{ if(!selectedId) return; const sel=boxes.find(b=>b.id===selectedId); if(!sel) return; let newId=`${sel.id}_copy`; let i=1; while(boxes.some(b=>b.id===newId)){ i++; newId=`${sel.id}_copy${i}`;} const nx=Math.min(0.98, sel.x+0.02), ny=Math.min(0.98, sel.y+0.02); const dup={...sel, id:newId, x:nx, y:ny} as CBox; setBoxes(prev=>[...prev,dup]); setSelectedId(newId); setBNameState(newId); }}>Duplicate</Button>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
