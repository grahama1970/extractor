"use client";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Box = { id: string; page: number; x: number; y: number; w: number; h: number };

type Suggestion = { type: string; confidence: number; reason?: string; expected_json?: string };

export function InlineHud({
  box,
  viewport,
  pdfPath,
  bName,
  bType,
  bExpected,
  setBName,
  setBType,
  setBExpected,
  onSaveGold,
  onAutoLabel,
  onApplyExtract,
  suggestions,
  loading,
  compact,
}: {
  box: Box;
  viewport: { w: number; h: number };
  pdfPath: string;
  bName: string;
  bType: string;
  bExpected: string;
  setBName: (v: string) => void;
  setBType: (v: string) => void;
  setBExpected: (v: string) => void;
  onSaveGold: () => void;
  onAutoLabel: () => void;
  onApplyExtract: (data: any) => void;
  suggestions: Suggestion[];
  loading?: boolean;
  compact?: boolean;
}) {
  const [pasting, setPasting] = React.useState(false);
  const [pasteValue, setPasteValue] = React.useState("");
  const [extracting, setExtracting] = React.useState(false);
  // Draggable HUD state
  const defaultPos = React.useMemo(() => {
    const px = box.x * viewport.w;
    const py = box.y * viewport.h;
    const bw = box.w * viewport.w;
    const bh = box.h * viewport.h;
    const hudW = 300;
    const hudH = 240;
    // Prefer placing to the right of the box if space, else to the left; then below/above as fallback
    let lx = px + bw + 8;
    if (lx + hudW > viewport.w) lx = Math.max(8, px - hudW - 8);
    let ly = py;
    if (ly + hudH > viewport.h) ly = Math.max(8, viewport.h - hudH - 8);
    return { lx: Math.max(8, Math.min(viewport.w - hudW - 8, lx)), ly: Math.max(8, Math.min(viewport.h - hudH - 8, ly)) };
  }, [box.x, box.y, box.w, box.h, viewport.w, viewport.h]);
  const [pos, setPos] = React.useState<{ x: number; y: number } | null>(null);
  React.useEffect(() => {
    // reset position when box or viewport changes
    setPos({ x: defaultPos.lx, y: defaultPos.ly });
  }, [defaultPos.lx, defaultPos.ly]);

  const dragRef = React.useRef<{ dx: number; dy: number; dragging: boolean } | null>(null);
  const onDragStart = (e: React.MouseEvent) => {
    dragRef.current = { dx: e.clientX - (pos?.x || 0), dy: e.clientY - (pos?.y || 0), dragging: true };
    e.preventDefault();
    e.stopPropagation();
  };
  const onDragMove = (e: React.MouseEvent) => {
    if (!dragRef.current?.dragging) return;
    const nx = e.clientX - dragRef.current.dx;
    const ny = e.clientY - dragRef.current.dy;
    const hudW = 300;
    const hudH = 260;
    setPos({
      x: Math.max(8, Math.min(viewport.w - hudW - 8, nx)),
      y: Math.max(8, Math.min(viewport.h - hudH - 8, ny)),
    });
    e.preventDefault();
    e.stopPropagation();
  };
  const onDragEnd = (e: React.MouseEvent) => {
    if (dragRef.current) dragRef.current.dragging = false;
    e.preventDefault();
    e.stopPropagation();
  };

  return (
    <div style={{ position: "absolute", left: (pos?.x ?? defaultPos.lx), top: (pos?.y ?? defaultPos.ly), width: 300 }} className="rounded-md border bg-white/95 shadow p-2 space-y-2 text-sm">
      <div className="flex items-center justify-between select-none cursor-move" onMouseDown={onDragStart} onMouseMove={onDragMove} onMouseUp={onDragEnd}>
        <div className="text-xs font-medium text-muted-foreground">Box HUD</div>
        <Button size="sm" variant="ghost" onClick={(e)=>{ e.stopPropagation(); e.preventDefault(); const ev = new CustomEvent('inlinehud:close'); window.dispatchEvent(ev); }}>✕</Button>
      </div>
      {compact ? (
        <div className="flex items-center gap-2">
          <div className="text-xs text-muted-foreground truncate" title={bName || box.id}>Sel: {bName || box.id}</div>
          <Button size="sm" onClick={onSaveGold}>Save</Button>
          <Button size="sm" variant="outline" onClick={onAutoLabel} disabled={loading}>{loading?"Suggest…":"Auto"}</Button>
          {bType === 'table' && (
            <>
              <Button size="sm" variant="secondary" onClick={async ()=>{
                try {
                  const res = await fetch('/api/crop', { method:'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pdf: pdfPath, page: box.page, box: { x: box.x, y: box.y, w: box.w, h: box.h }, zoom: 2.0 }) });
                  const data = await res.json();
                  if (!res.ok) { window.dispatchEvent(new CustomEvent('app:toast', { detail: { level:'error', msg: data.error || 'Crop failed' } })); return; }
                  const url = `data:${data.contentType};base64,${data.image}`;
                  window.open(url, '_blank');
                } catch (e:any) { window.dispatchEvent(new CustomEvent('app:toast', { detail: { level:'error', msg: e.message || 'Crop failed' } })); }
              }}>Crop</Button>
              <Button size="sm" variant="outline" onClick={async ()=>{
                try {
                  setExtracting(true);
                  const res = await fetch('/api/extract-table', { method:'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pdf: pdfPath, page: box.page, box: { x: box.x, y: box.y, w: box.w, h: box.h }, zoom: 2.0 }) });
                  const data = await res.json();
                  const table = data?.table || data;
                  if (res.ok && table?.columns && table?.rows) onApplyExtract(table);
                  else window.dispatchEvent(new CustomEvent('app:toast', { detail: { level:'warn', msg: 'No table returned; paste manually.' } }));
                } catch (e:any) { window.dispatchEvent(new CustomEvent('app:toast', { detail: { level:'error', msg: e.message || 'Extract failed' } })); }
                finally { setExtracting(false); }
              }}>{extracting? '…' : 'Extract'}</Button>
            </>
          )}
        </div>
      ) : (
        <>
      <div className="flex items-center gap-2">
        <Label className="w-10">ID</Label>
        <Input value={bName} onChange={e=>setBName(e.target.value)} placeholder="id" />
      </div>
      <div className="flex items-center gap-2">
        <Label className="w-10">Type</Label>
        <div className="flex gap-1 flex-wrap">
          {(["table","section","requirements","figure"]).map(t => (
            <Button key={t} size="sm" variant={bType===t?"default":"secondary"} onClick={()=>{
              setBType(t);
              if (!bExpected) {
                const base = t === 'table' ? 'tables' : t;
                setBExpected(`data/gold_standards/${base}/${bName||box.id}.json`);
              }
            }}>{t}</Button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Label className="w-10">JSON</Label>
        <Input value={bExpected} onChange={e=>setBExpected(e.target.value)} placeholder="data/gold_standards/...json" />
      </div>
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={onSaveGold}>Save</Button>
        <Button size="sm" variant="outline" onClick={onAutoLabel} disabled={loading}>{loading?"Suggesting...":"Auto-label"}</Button>
        {bType === 'table' && (
          <Button size="sm" variant="secondary" onClick={async ()=>{
            try {
              const res = await fetch('/api/crop', { method:'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pdf: pdfPath, page: box.page, box: { x: box.x, y: box.y, w: box.w, h: box.h }, zoom: 2.0 }) });
              const data = await res.json();
              if (!res.ok) { alert(data.error || 'Crop failed'); return; }
              const url = `data:${data.contentType};base64,${data.image}`;
              // Open cropped image in a new tab for quick inspection or copy to external tools
              window.open(url, '_blank');
            } catch (e:any) {
              alert(e.message || 'Crop failed');
            }
          }}>Crop</Button>
        )}
        {bType === 'table' && (
          <Button size="sm" variant="outline" onClick={async ()=>{
            try {
              setExtracting(true);
              const res = await fetch('/api/extract-table', { method:'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pdf: pdfPath, page: box.page, box: { x: box.x, y: box.y, w: box.w, h: box.h }, zoom: 2.0 }) });
              const data = await res.json();
              if (res.ok && data && (data.columns || (data.table && data.table.columns))) {
                const table = data.table || data;
                onApplyExtract(table);
              } else {
                // Provider missing or not implemented; allow pasting JSON
                setPasting(true);
                if (data && data.prompt) {
                  console.info('LLM prompt for extraction:', data.prompt);
                }
              }
            } catch (e:any) {
              setPasting(true);
            } finally {
              setExtracting(false);
            }
          }} disabled={extracting}>{extracting? 'Extracting…' : 'Extract'}</Button>
        )}
      </div>
      {pasting && (
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">Paste extracted table JSON (columns, rows, optional title), then Apply:</div>
          <textarea className="w-full h-24 border rounded p-1 text-xs" value={pasteValue} onChange={e=>setPasteValue(e.target.value)} placeholder='{"columns":["A","B"],"rows":[["1","x"],["2","y"]],"title":null}' />
          <div className="flex gap-2">
            <Button size="sm" onClick={()=>{
              try {
                const obj = JSON.parse(pasteValue || '{}');
                onApplyExtract(obj);
                setPasting(false);
                setPasteValue('');
              } catch (e:any) { alert('Invalid JSON'); }
            }}>Apply</Button>
            <Button size="sm" variant="ghost" onClick={()=>{ setPasting(false); setPasteValue(''); }}>Cancel</Button>
          </div>
        </div>
      )}
      {suggestions?.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">Suggestions:</div>
          <div className="flex gap-1 flex-wrap">
            {suggestions.map((s, idx) => (
              <Button key={idx} size="sm" variant="secondary" title={s.reason||""} onClick={()=>{
                setBType(s.type);
                if (s.expected_json) setBExpected(s.expected_json);
              }}>{s.type} {Math.round(s.confidence*100)}%</Button>
            ))}
          </div>
        </div>
      )}
        </>
      )}
    </div>
  );
}
