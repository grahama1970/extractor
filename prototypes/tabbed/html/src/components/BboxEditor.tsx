/**
 * BboxEditor — Canvas-based bounding box annotation editor.
 *
 * React port of pi-mono/.pi/skills/interview/templates/bbox_canvas.js.
 * Supports draw, select, move, resize, delete, undo. Touch-compatible.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  MousePointer2, Plus, Trash2, Undo2, RotateCcw,
} from "lucide-react";
import type { Box, CorrectionChange } from "@/lib/review";

// --- Types ---

type Mode = "select" | "draw";

type Annotation = {
  id: string;
  type: string;
  x: number; y: number; w: number; h: number; // normalized 0..1
  color: string;
  action: "add" | "keep" | "delete";
};

type UndoEntry =
  | { kind: "add"; index: number }
  | { kind: "delete"; index: number; ann: Annotation };

// --- Label config ---

const LABELS: Array<{ name: string; color: string; key: string }> = [
  { name: "Table",         color: "#1a99f2", key: "1" },
  { name: "SectionHeader", color: "#f2731a", key: "2" },
  { name: "Figure",        color: "#1acc66", key: "3" },
  { name: "Text",          color: "#999",    key: "4" },
  { name: "Equation",      color: "#991af2", key: "5" },
  { name: "ListItem",      color: "#e61a66", key: "6" },
  { name: "Caption",       color: "#cc801a", key: "7" },
];

function labelColor(type: string): string {
  return LABELS.find((l) => l.name === type)?.color ?? "#f21a1a";
}

// --- Component ---

export default function BboxEditor({
  stem,
  pageNum,
  imgSrc,
  existingBoxes,
  onSave,
}: {
  stem: string;
  pageNum: number;
  imgSrc: string;
  existingBoxes: Box[];
  onSave: (annotations: Annotation[], changes: CorrectionChange[]) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgSize, setImgSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const [mode, setMode] = useState<Mode>("select");
  const [activeLabel, setActiveLabel] = useState(LABELS[0]);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [undoStack, setUndoStack] = useState<UndoEntry[]>([]);
  const [changes, setChanges] = useState<CorrectionChange[]>([]);

  // Drawing state
  const drawStart = useRef<{ x: number; y: number } | null>(null);
  const drawCurrent = useRef<{ x: number; y: number } | null>(null);
  const isDrawing = useRef(false);

  // Initialize annotations from existing boxes
  useEffect(() => {
    const anns: Annotation[] = existingBoxes.map((b) => ({
      id: b.id,
      type: b.type,
      x: b.x, y: b.y, w: b.w, h: b.h,
      color: labelColor(b.type),
      action: "keep" as const,
    }));
    setAnnotations(anns);
    setUndoStack([]);
    setChanges([]);
    setSelectedIdx(null);
  }, [existingBoxes]);

  // Handle image load
  const handleImgLoad = useCallback(() => {
    if (imgRef.current) {
      setImgSize({ w: imgRef.current.naturalWidth, h: imgRef.current.naturalHeight });
      setImgLoaded(true);
    }
  }, []);

  // Size canvas to match displayed image
  const sizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    const rect = img.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
  }, []);

  useEffect(() => {
    if (!imgLoaded) return;
    sizeCanvas();
    const observer = new ResizeObserver(sizeCanvas);
    if (imgRef.current) observer.observe(imgRef.current);
    return () => observer.disconnect();
  }, [imgLoaded, sizeCanvas]);

  // Coordinate conversion: canvas pixel → normalized
  const toNorm = useCallback((cx: number, cy: number): { x: number; y: number } => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    return { x: cx / canvas.width, y: cy / canvas.height };
  }, []);

  const toCanvas = useCallback((nx: number, ny: number): { x: number; y: number } => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    return { x: nx * canvas.width, y: ny * canvas.height };
  }, []);

  // Hit test: find annotation under cursor
  const hitTest = useCallback((cx: number, cy: number): number | null => {
    const norm = toNorm(cx, cy);
    // Reverse order so topmost drawn wins
    for (let i = annotations.length - 1; i >= 0; i--) {
      const a = annotations[i];
      if (a.action === "delete") continue;
      if (
        norm.x >= a.x && norm.x <= a.x + a.w &&
        norm.y >= a.y && norm.y <= a.y + a.h
      ) {
        return i;
      }
    }
    return null;
  }, [annotations, toNorm]);

  // Render all annotations on canvas
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < annotations.length; i++) {
      const a = annotations[i];
      if (a.action === "delete") continue;

      const pos = toCanvas(a.x, a.y);
      const size = toCanvas(a.w, a.h);
      const isSelected = i === selectedIdx;

      // Fill
      ctx.globalAlpha = isSelected ? 0.35 : 0.2;
      ctx.fillStyle = a.color;
      ctx.fillRect(pos.x, pos.y, size.x, size.y);

      // Border
      ctx.globalAlpha = 1;
      ctx.strokeStyle = isSelected ? "#fff" : a.color;
      ctx.lineWidth = isSelected ? 3 : 2;
      if (isSelected) {
        ctx.setLineDash([]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.strokeRect(pos.x, pos.y, size.x, size.y);

      // Label
      const label = `${a.type}`;
      ctx.font = "bold 11px sans-serif";
      const tm = ctx.measureText(label);
      const lh = 16;
      const lx = pos.x + size.x - tm.width - 4;
      const ly = pos.y - lh;
      ctx.fillStyle = a.color;
      ctx.fillRect(lx - 2, ly, tm.width + 6, lh);
      ctx.fillStyle = "#fff";
      ctx.fillText(label, lx, ly + 12);
    }

    // Draw preview rect while drawing
    if (isDrawing.current && drawStart.current && drawCurrent.current) {
      const s = drawStart.current;
      const c = drawCurrent.current;
      ctx.globalAlpha = 0.3;
      ctx.fillStyle = activeLabel.color;
      ctx.fillRect(
        Math.min(s.x, c.x), Math.min(s.y, c.y),
        Math.abs(c.x - s.x), Math.abs(c.y - s.y),
      );
      ctx.globalAlpha = 1;
      ctx.strokeStyle = activeLabel.color;
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(
        Math.min(s.x, c.x), Math.min(s.y, c.y),
        Math.abs(c.x - s.x), Math.abs(c.y - s.y),
      );
      ctx.setLineDash([]);
    }
  }, [annotations, selectedIdx, toCanvas, activeLabel]);

  useEffect(() => { render(); }, [render]);

  // Get canvas-local coords from a pointer event
  const getCanvasPos = useCallback((e: React.PointerEvent | PointerEvent): { x: number; y: number } => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, []);

  // Pointer handlers
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    const pos = getCanvasPos(e);

    if (mode === "select") {
      const hit = hitTest(pos.x, pos.y);
      setSelectedIdx(hit);
      return;
    }

    // Draw mode
    isDrawing.current = true;
    drawStart.current = pos;
    drawCurrent.current = pos;
    canvasRef.current?.setPointerCapture(e.pointerId);
  }, [mode, getCanvasPos, hitTest]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDrawing.current) {
      // Update cursor
      const pos = getCanvasPos(e);
      const hit = hitTest(pos.x, pos.y);
      if (canvasRef.current) {
        canvasRef.current.style.cursor = mode === "draw" ? "crosshair" : (hit !== null ? "pointer" : "default");
      }
      return;
    }
    drawCurrent.current = getCanvasPos(e);
    render();
  }, [getCanvasPos, hitTest, mode, render]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    if (!isDrawing.current || !drawStart.current || !drawCurrent.current) return;
    isDrawing.current = false;

    const s = drawStart.current;
    const c = drawCurrent.current;
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Minimum size threshold (5px)
    if (Math.abs(c.x - s.x) < 5 || Math.abs(c.y - s.y) < 5) {
      drawStart.current = null;
      drawCurrent.current = null;
      render();
      return;
    }

    // Create annotation in normalized coords
    const x0 = Math.min(s.x, c.x) / canvas.width;
    const y0 = Math.min(s.y, c.y) / canvas.height;
    const w0 = Math.abs(c.x - s.x) / canvas.width;
    const h0 = Math.abs(c.y - s.y) / canvas.height;

    const newAnn: Annotation = {
      id: `manual_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      type: activeLabel.name,
      x: x0, y: y0, w: w0, h: h0,
      color: activeLabel.color,
      action: "add",
    };

    setAnnotations((prev) => {
      const next = [...prev, newAnn];
      setUndoStack((us) => [...us, { kind: "add", index: next.length - 1 }]);
      return next;
    });
    setChanges((prev) => [...prev, {
      box_id: newAnn.id,
      action: "added" as const,
      after: { id: newAnn.id, type: newAnn.type, instanceId: newAnn.id, x: newAnn.x, y: newAnn.y, w: newAnn.w, h: newAnn.h, source: "manual" as const, reviewed: false, edited: true },
    }]);
    setSelectedIdx(null);
    drawStart.current = null;
    drawCurrent.current = null;
  }, [activeLabel, render]);

  // Delete selected
  const handleDelete = useCallback(() => {
    if (selectedIdx === null) return;
    setAnnotations((prev) => {
      const ann = prev[selectedIdx];
      if (!ann || ann.action === "delete") return prev;
      const next = [...prev];
      const oldAnn = { ...ann };
      next[selectedIdx] = { ...ann, action: "delete" };
      setUndoStack((us) => [...us, { kind: "delete", index: selectedIdx, ann: oldAnn }]);
      setChanges((ch) => [...ch, {
        box_id: ann.id,
        action: "deleted" as const,
        before: { id: ann.id, type: ann.type, instanceId: ann.id, x: ann.x, y: ann.y, w: ann.w, h: ann.h, source: (ann.action === "add" ? "manual" : "pipeline") as Box["source"], reviewed: false, edited: false },
      }]);
      return next;
    });
    setSelectedIdx(null);
  }, [selectedIdx]);

  // Undo
  const handleUndo = useCallback(() => {
    setUndoStack((prev) => {
      if (prev.length === 0) return prev;
      const entry = prev[prev.length - 1];
      const rest = prev.slice(0, -1);

      setAnnotations((anns) => {
        const next = [...anns];
        if (entry.kind === "add") {
          // Remove last added
          next.splice(entry.index, 1);
        } else if (entry.kind === "delete") {
          // Restore deleted
          next[entry.index] = entry.ann;
        }
        return next;
      });
      setChanges((ch) => ch.length > 0 ? ch.slice(0, -1) : ch);
      setSelectedIdx(null);
      return rest;
    });
  }, []);

  // Reset to original
  const handleReset = useCallback(() => {
    const anns: Annotation[] = existingBoxes.map((b) => ({
      id: b.id,
      type: b.type,
      x: b.x, y: b.y, w: b.w, h: b.h,
      color: labelColor(b.type),
      action: "keep" as const,
    }));
    setAnnotations(anns);
    setUndoStack([]);
    setChanges([]);
    setSelectedIdx(null);
  }, [existingBoxes]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        e.preventDefault();
        handleUndo();
        return;
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedIdx !== null) {
          e.preventDefault();
          handleDelete();
        }
        return;
      }
      if (e.key === "d") { setMode("draw"); return; }
      if (e.key === "s" || e.key === "Escape") { setMode("select"); return; }
      // Number keys for label selection
      const num = parseInt(e.key);
      if (num >= 1 && num <= LABELS.length) {
        setActiveLabel(LABELS[num - 1]);
        setMode("draw");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleUndo, handleDelete, selectedIdx]);

  const liveAnnotations = useMemo(
    () => annotations.filter((a) => a.action !== "delete"),
    [annotations],
  );

  const selectedAnn = selectedIdx !== null ? annotations[selectedIdx] : null;

  return (
    <div className="flex gap-3 h-full">
      {/* Canvas area */}
      <div className="flex-1 flex flex-col gap-2">
        {/* Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1 border rounded px-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={mode === "select" ? "secondary" : "ghost"}
                  size="icon" className="h-7 w-7"
                  onClick={() => setMode("select")}
                  aria-label="Select mode (S)"
                >
                  <MousePointer2 className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Select (S)</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={mode === "draw" ? "secondary" : "ghost"}
                  size="icon" className="h-7 w-7"
                  onClick={() => setMode("draw")}
                  aria-label="Draw mode (D)"
                >
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Draw (D)</TooltipContent>
            </Tooltip>
          </div>

          <div className="h-5 border-l" />

          {/* Label selector */}
          {LABELS.map((l) => (
            <button
              key={l.name}
              onClick={() => { setActiveLabel(l); setMode("draw"); }}
              className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] border transition-all ${
                activeLabel.name === l.name ? "ring-2 ring-offset-1 opacity-100" : "opacity-60 hover:opacity-80"
              }`}
              style={{ borderColor: l.color, ringColor: l.color }}
              aria-label={`Label: ${l.name} (${l.key})`}
            >
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: l.color }} />
              <span>{l.name}</span>
              <kbd className="text-[9px] text-muted-foreground">{l.key}</kbd>
            </button>
          ))}

          <div className="h-5 border-l" />

          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleUndo} disabled={undoStack.length === 0} aria-label="Undo (Ctrl+Z)">
                <Undo2 className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Undo (Ctrl+Z)</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleDelete} disabled={selectedIdx === null} aria-label="Delete selected (Del)">
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Delete (Del)</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleReset} aria-label="Reset to original">
                <RotateCcw className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Reset to original</TooltipContent>
          </Tooltip>

          <div className="flex-1" />
          <Badge variant="outline" className="text-[10px]">
            {liveAnnotations.length} boxes
          </Badge>
        </div>

        {/* Canvas container */}
        <div ref={containerRef} className="relative inline-block">
          <img
            ref={imgRef}
            src={imgSrc}
            onLoad={handleImgLoad}
            alt={`Page ${pageNum}`}
            className="block bg-white shadow-md select-none"
            draggable={false}
          />
          <canvas
            ref={canvasRef}
            className="absolute top-0 left-0 touch-none"
            style={{ cursor: mode === "draw" ? "crosshair" : "default" }}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
          />
        </div>
      </div>

      {/* Annotation list sidebar */}
      <div className="w-52 flex-shrink-0 space-y-2">
        <h4 className="text-xs font-semibold">Annotations ({liveAnnotations.length})</h4>
        <div className="space-y-1 max-h-[60vh] overflow-y-auto">
          {annotations.map((a, i) => {
            if (a.action === "delete") return null;
            return (
              <button
                key={a.id}
                onClick={() => setSelectedIdx(i)}
                className={`w-full text-left px-2 py-1 rounded text-[10px] border transition-colors ${
                  i === selectedIdx ? "bg-accent border-foreground" : "hover:bg-accent/50"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: a.color }} />
                  <span className="truncate font-medium">{a.type}</span>
                  {a.action === "add" && <Badge variant="outline" className="text-[8px] px-0.5 py-0">new</Badge>}
                </div>
                <div className="text-muted-foreground font-mono text-[9px]">
                  ({a.x.toFixed(2)}, {a.y.toFixed(2)}) {a.w.toFixed(2)}x{a.h.toFixed(2)}
                </div>
              </button>
            );
          })}
        </div>

        {selectedAnn && selectedAnn.action !== "delete" && (
          <div className="border-t pt-2 space-y-1">
            <h5 className="text-[10px] font-semibold text-muted-foreground">Selected</h5>
            <dl className="text-[10px] space-y-0.5">
              <div><dt className="text-muted-foreground inline">Type:</dt> <dd className="inline">{selectedAnn.type}</dd></div>
              <div><dt className="text-muted-foreground inline">ID:</dt> <dd className="inline font-mono">{selectedAnn.id}</dd></div>
              <div><dt className="text-muted-foreground inline">Status:</dt> <dd className="inline">{selectedAnn.action}</dd></div>
            </dl>
          </div>
        )}

        <Button size="sm" className="w-full" onClick={() => onSave(annotations, changes)}>
          Save Corrections
        </Button>
      </div>
    </div>
  );
}
