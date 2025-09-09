import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Upload, Search, Archive, Copy, Trash2, Plus, Crosshair,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  Edit, Sparkles, ArrowLeft
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ThumbnailRail } from "@/components/ThumbnailRail";
import { ThumbnailStrip } from "@/components/ThumbnailStrip";
import { PdfCanvas } from "@/components/PdfCanvas";
import { loadPdf, type PdfDoc } from "@/lib/pdf";
import { DEFAULT_LABELS, loadLabels, saveLabel, type LabelDef } from "@/lib/labels";

// Types
type Box = {
  id: string;
  type: string;
  instanceId: string;
  x: number; // 0..1
  y: number; // 0..1
  w: number; // 0..1
  h: number; // 0..1
};

const SNAP = 0.01; // 1% snap
const MIN_SIZE = 0.02; // 2% minimum

const ClassicLayout = () => {
  // Prototype state
  const [currentPage, setCurrentPage] = useState(5);
  const [doc, setDoc] = useState<PdfDoc | null>(null);
  const [totalPages, setTotalPages] = useState<number>(50);
  const [zoom, setZoom] = useState(1);

  // Boxes per page
  const [boxesByPage, setBoxesByPage] = useState<Record<number, Box[]>>({
    5: [
      { id: "section", type: "Section", instanceId: "sec-001", x: 0.10, y: 0.15, w: 0.80, h: 0.15 },
      { id: "table", type: "Table", instanceId: "tbl-001", x: 0.15, y: 0.40, w: 0.70, h: 0.40 },
    ],
  });
  const [selectedId, setSelectedId] = useState<string | null>("section");
  const [defaultNewType, setDefaultNewType] = useState<string>("Section");
  const [labels, setLabels] = useState<LabelDef[]>(() => (typeof window !== 'undefined' ? loadLabels() : DEFAULT_LABELS));
  useEffect(() => { setLabels(loadLabels()); }, []);

  const [jsonOpen, setJsonOpen] = useState(false);
  const [jsonText, setJsonText] = useState("{}");

  // Scroll active thumbnail into view (pager chips removed; still keep util)
  const thumbRefs = useRef<Record<number, HTMLButtonElement | null>>({});
  useEffect(() => {
    thumbRefs.current[currentPage]?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, [currentPage]);

  const pdfFiles = [
    { name: "Research Paper 2024", pages: 45, status: "complete" },
    { name: "Technical Specification", pages: 89, status: "pending" },
    { name: "User Manual Draft", pages: 120, status: "complete" },
    { name: "Legal Document", pages: 67, status: "pending" },
    { name: "BHT Spec", pages: 2, status: "complete" },
    { name: "Whitepaper", pages: 18, status: "pending" },
    { name: "Proposal", pages: 12, status: "complete" },
  ];

  // load demo PDF once
  useEffect(() => {
    let mounted = true;
    loadPdf("/bht.pdf").then((d) => {
      if (!mounted) return;
      setDoc(d);
      setTotalPages(d.numPages || 2);
    });
    return () => { mounted = false };
  }, []);

  // Thumbnails mode (left | bottom | off) with persistence
  type ThumbMode = "left" | "bottom" | "off";
  const [thumbMode, setThumbMode] = useState<ThumbMode>(() => (localStorage.getItem("anno_thumb_mode") as ThumbMode) || "left");
  useEffect(() => { localStorage.setItem("anno_thumb_mode", thumbMode); }, [thumbMode]);

  // Derived helpers for current page
  const pageBoxes = useMemo(() => boxesByPage[currentPage] || [], [boxesByPage, currentPage]);
  const selectedBox = useMemo(() => pageBoxes.find((b) => b.id === selectedId) || null, [pageBoxes, selectedId]);
  const setPageBoxes = (updater: (prev: Box[]) => Box[]) => {
    setBoxesByPage((prev) => ({ ...prev, [currentPage]: updater(prev[currentPage] || []) }));
  };

  // Ensure selection valid on page change
  useEffect(() => {
    const boxes = boxesByPage[currentPage] || [];
    if (!boxes.length) setSelectedId(null);
    else if (!boxes.find((b) => b.id === selectedId)) setSelectedId(boxes[boxes.length - 1].id);
  }, [currentPage, boxesByPage, selectedId]);

  // Overlay interactivity
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<
    | null
    | {
        id: string;
        mode: "move" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw";
        startX: number;
        startY: number;
        startBox: Box;
        rect: { width: number; height: number };
      }
  >(null);

  // Drawing state
  const drawRef = useRef<
    | null
    | { startX: number; startY: number; rect: { width: number; height: number }; alt: boolean }
  >(null);
  const [draftBox, setDraftBox] = useState<Box | null>(null);
  const [drawArmed, setDrawArmed] = useState(false);
  // HUD state
  type HudMode = "free" | "attach";
  const [hudMode, setHudMode] = useState<HudMode>(() => (localStorage.getItem("anno_hud_mode") as HudMode) || "free");
  const [hudPos, setHudPos] = useState<{x:number;y:number}>(() => { try { return JSON.parse(localStorage.getItem("anno_hud_pos") || ""); } catch { return { x: 12, y: 12 }; } });
  useEffect(() => { localStorage.setItem("anno_hud_mode", hudMode); }, [hudMode]);
  useEffect(() => { if (hudPos && Number.isFinite(hudPos.x)) localStorage.setItem("anno_hud_pos", JSON.stringify(hudPos)); }, [hudPos]);
  const hudStyle = useMemo(() => {
    const base: any = { opacity: 0.98 };
    if (hudMode === "free") return { ...base, left: hudPos?.x ?? 12, top: hudPos?.y ?? 12 };
    const m = 8;
    const r = overlayRef.current?.getBoundingClientRect();
    const b = selectedBox;
    if (!r || !b) return { ...base, left: 12, top: 12 };
    const x = b.x * r.width + Math.min(20, (b.w * r.width) / 2);
    const y = Math.max(m, b.y * r.height - 40);
    return { ...base, left: Math.min(Math.max(m, x), r.width - 160), top: Math.min(Math.max(m, y), r.height - 44) };
  }, [hudMode, hudPos, selectedBox]);

  // Add Label dialog state
  const [addOpen, setAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newIcon, setNewIcon] = useState("Heading");
  const [newColor, setNewColor] = useState("annotation-section");
  const [newDesc, setNewDesc] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);


  // Utils
  const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
  const collectGuides = (excludeId?: string) => {
    const v: number[] = [0, 1];
    const h: number[] = [0, 1];
    for (const b of pageBoxes) {
      if (b.id === excludeId) continue;
      v.push(b.x, b.x + b.w);
      h.push(b.y, b.y + b.h);
    }
    return { v, h };
  };
  const snapTo = (value: number, guides: number[], tol = SNAP) => {
    let best = value, bestDelta = tol + 1;
    for (const g of guides) {
      const d = Math.abs(value - g);
      if (d < tol && d < bestDelta) { best = g; bestDelta = d; }
    }
    return best;
  };

  const beginDrag = (
    id: string,
    e: React.PointerEvent,
    mode: "move" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw"
  ) => {
    if (!overlayRef.current) return;
    const rect = overlayRef.current.getBoundingClientRect();
    const startBox = pageBoxes.find((b) => b.id === id);
    if (!startBox) return;
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    dragRef.current = {
      id,
      mode,
      startX: e.clientX,
      startY: e.clientY,
      startBox: { ...startBox },
      rect: { width: rect.width, height: rect.height },
    };
    setSelectedId(id);
  };

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      // Dragging
      if (dragRef.current) {
        const d = dragRef.current;
        const dx = (e.clientX - d.startX) / Math.max(1, d.rect.width);
        const dy = (e.clientY - d.startY) / Math.max(1, d.rect.height);
        setPageBoxes((prev) => prev.map((b) => {
          if (b.id !== d.id) return b;
          const guides = collectGuides(b.id);
          let { x, y, w, h } = d.startBox;
          if (d.mode === "move") {
            x = clamp01(Math.min(1 - w, x + dx));
            y = clamp01(Math.min(1 - h, y + dy));
            if (!e.altKey) {
              const L = snapTo(x, guides.v);
              const R = snapTo(x + w, guides.v);
              x = Math.abs(L - x) < Math.abs(R - (x + w)) ? L : R - w;
              const T = snapTo(y, guides.h);
              const B = snapTo(y + h, guides.h);
              y = Math.abs(T - y) < Math.abs(B - (y + h)) ? T : B - h;
              x = clamp01(Math.min(1 - w, x));
              y = clamp01(Math.min(1 - h, y));
            }
          } else {
            if (d.mode.includes("n")) {
              let newY = clamp01(Math.min(d.startBox.y + d.startBox.h - MIN_SIZE, d.startBox.y + dy));
              if (!e.altKey) newY = snapTo(newY, guides.h);
              h = d.startBox.h + (d.startBox.y - newY);
              y = newY;
            }
            if (d.mode.includes("s")) {
              let newB = clamp01(d.startBox.y + d.startBox.h + dy);
              if (!e.altKey) newB = snapTo(newB, guides.h);
              h = Math.max(MIN_SIZE, Math.min(1 - d.startBox.y, newB - d.startBox.y));
              y = d.startBox.y;
            }
            if (d.mode.includes("w")) {
              let newX = clamp01(Math.min(d.startBox.x + d.startBox.w - MIN_SIZE, d.startBox.x + dx));
              if (!e.altKey) newX = snapTo(newX, guides.v);
              w = d.startBox.w + (d.startBox.x - newX);
              x = newX;
            }
            if (d.mode.includes("e")) {
              let newR = clamp01(d.startBox.x + d.startBox.w + dx);
              if (!e.altKey) newR = snapTo(newR, guides.v);
              w = Math.max(MIN_SIZE, Math.min(1 - d.startBox.x, newR - d.startBox.x));
              x = d.startBox.x;
            }
          }
          return { ...b, x, y, w, h };
        }));
        return;
      }
      // Drawing
      if (drawRef.current && overlayRef.current) {
        const rect = overlayRef.current.getBoundingClientRect();
        const curX = (e.clientX - rect.left) / Math.max(1, rect.width);
        const curY = (e.clientY - rect.top) / Math.max(1, rect.height);
        let x = Math.min(drawRef.current.startX, curX);
        let y = Math.min(drawRef.current.startY, curY);
        let w = Math.abs(curX - drawRef.current.startX);
        let h = Math.abs(curY - drawRef.current.startY);
        if (!drawRef.current.alt) {
          const guides = collectGuides();
          const L = snapTo(x, guides.v);
          const R = snapTo(x + w, guides.v);
          const T = snapTo(y, guides.h);
          const B = snapTo(y + h, guides.h);
          x = L; y = T; w = Math.max(0, R - L); h = Math.max(0, B - T);
        }
        
        // Constrain with Shift to ~4:3 (w : h = 4 : 3)
        if (e.shiftKey) {
          const sx = drawRef.current.startX; const sy = drawRef.current.startY;
          const ratio = 3/4;
          let newH = w * ratio;
          if (curY >= sy) { // dragging downward
            y = sy;
          } else {
            y = sy - newH;
          }
          h = newH;
        }
        setDraftBox({ id: "draft", type: defaultNewType, instanceId: "new", x, y, w, h });

      }
    };
    const onUp = () => {
      if (dragRef.current) dragRef.current = null;
      if (drawRef.current) {
        const d = draftBox;
        drawRef.current = null;
        setDraftBox(null);
        if (d && d.w >= MIN_SIZE && d.h >= MIN_SIZE) {
          const newBox: Box = {
            id: `box-${Math.random().toString(36).slice(2, 7)}`,
            type: defaultNewType,
            instanceId: `${defaultNewType.toLowerCase()}-${Math.random().toString(36).slice(2, 5)}`,
            x: clamp01(d.x), y: clamp01(d.y), w: clamp01(d.w), h: clamp01(d.h),
          };
          setPageBoxes((prev) => [...prev, newBox]);
          setSelectedId(newBox.id);
        }
        setDrawArmed(false);
      }
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [draftBox, defaultNewType, pageBoxes]);

  // Persist boxes across reloads (demo)
  useEffect(() => {
    try {
      const raw = localStorage.getItem("anno_boxes_by_page");
      if (raw) setBoxesByPage(JSON.parse(raw));
    } catch {}
  }, []);
  useEffect(() => {
    try { localStorage.setItem("anno_boxes_by_page", JSON.stringify(boxesByPage)); } catch {}
  }, [boxesByPage]);

  // Keyboard shortcuts
  useEffect(() => {
    const isTyping = (el: EventTarget | null) => {
      if (!(el instanceof HTMLElement)) return false;
      const tag = el.tagName.toLowerCase();
      return tag === "input" || tag === "textarea" || el.isContentEditable;
    };
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return;
      if (e.key === "[") { e.preventDefault(); setCurrentPage((p) => Math.max(1, p - 1)); return; }
      if (e.key === "]") { e.preventDefault(); setCurrentPage((p) => Math.min(totalPages, p + 1)); return; }
      if (e.key.toLowerCase() === "h") { e.preventDefault(); setHudMode((m)=> m === "free" ? "attach" : "free"); return; }
      if (e.key.toLowerCase() === "r") { e.preventDefault(); setHudPos({ x: 12, y: 12 }); setHudMode("free"); return; }
      if (e.key.toLowerCase() === "n") { e.preventDefault(); setDrawArmed(true); return; }
      if (e.key === "Escape") { e.preventDefault(); if (drawRef.current || drawArmed) { drawRef.current = null; setDraftBox(null); setDrawArmed(false); } return; }
      if (e.key.toLowerCase() === "d" || (e.ctrlKey && e.key.toLowerCase() === "d")) {
        e.preventDefault();
        if (!selectedId) return;
        setPageBoxes((prev) => {
          const src = prev.find((b) => b.id === selectedId);
          if (!src) return prev;
          const copy: Box = { ...src, id: `${src.id}-${Math.random().toString(36).slice(2,6)}`, x: Math.min(0.98 - src.w, src.x + 0.02), y: Math.min(0.98 - src.h, src.y + 0.02) };
          const next = [...prev, copy];
          setSelectedId(copy.id);
          return next;
        });
        return;
      }
      if (e.key === "Delete") {
        e.preventDefault();
        if (!selectedId) return;
        setPageBoxes((prev) => {
          const filtered = prev.filter((b) => b.id !== selectedId);
          setSelectedId(filtered.length ? filtered[filtered.length-1].id : null);
          return filtered;
        });
        return;
      }
      if (["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(e.key)) {
        e.preventDefault();
        if (!selectedId) return;
        const step = e.shiftKey ? 0.02 : 0.005;
        setPageBoxes((prev) => prev.map((b) => {
          if (b.id !== selectedId) return b;
          let { x, y } = b;
          if (e.key === "ArrowLeft") x = Math.max(0, x - step);
          if (e.key === "ArrowRight") x = Math.min(1 - b.w, x + step);
          if (e.key === "ArrowUp") y = Math.max(0, y - step);
          if (e.key === "ArrowDown") y = Math.min(1 - b.h, y + step);
          return { ...b, x, y };
        }));
        return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, totalPages]);

  // JSON helpers
  const formatJson = () => {
    try { const obj = JSON.parse(jsonText); setJsonText(JSON.stringify(obj, null, 2)); } catch (_) {}
  };

  return (
    <div className="h-screen bg-background overflow-hidden">
      {/* Header */}
      <header className="h-16 border-b bg-card flex items-center px-6">
        <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Back to Prototypes
        </Link>
        <div className="flex-1 text-center">
          <h1 className="text-lg font-semibold">Classic Three-Panel Layout</h1>
        </div>
      </header>

      <div className="flex h-[calc(100vh-4rem)]">
        {/* Explorer Panel */}
        <div className="w-80 border-r bg-card p-6 flex flex-col">
          <h2 className="text-xl font-bold text-destructive mb-6 text-center">Explorer</h2>

          <div className="space-y-4 mb-4">
            <Button variant="outline" className="w-full justify-start">
              <Upload className="mr-2 h-4 w-4" /> Load PDF
            </Button>
            <Button variant="outline" className="w-full justify-start">
              <Search className="mr-2 h-4 w-4" /> Search PDF
            </Button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto pr-2">
            {pdfFiles.map((file, index) => (
              <Card key={index} className="p-4 hover:bg-muted/50 transition-colors cursor-pointer">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="font-medium text-sm">{file.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {file.pages} pages | <span className={`text-status-${file.status}`}>{file.status}</span>
                    </div>
                  </div>
                  <Button variant="link" size="sm" className="text-status-pending hover:text-status-complete">export</Button>
                </div>
              </Card>
            ))}
          </div>

          <Button className="w-full mt-4 bg-primary hover:bg-primary/90">
            <Archive className="mr-2 h-4 w-4" /> Export All
          </Button>
        </div>

        {/* Annotation Panel */}
        <div className="flex-1 p-6 flex flex-col min-w-0">
          <h2 className="text-xl font-bold text-destructive mb-4 text-center">Annotation</h2>

          <div className="flex-1 rounded-lg relative mb-4 overflow-hidden bg-muted flex">
            {/* Vertical thumbnail rail */}
            {doc && thumbMode === "left" && (
              <ThumbnailRail
                doc={doc}
                pageCount={totalPages}
                currentPage={currentPage}
                onJump={(n) => setCurrentPage(n)}
              />
            )}

            {/* Canvas viewer */}
            <div className="flex-1 p-4 overflow-auto flex items-start justify-center">
              {doc ? (
                <div
                  className={`relative inline-block ${drawArmed ? "cursor-crosshair" : ""}`}
                  ref={overlayRef}
                  onPointerDown={(e) => {
                    if (!overlayRef.current) return;
                    if (!drawArmed) return;
                    const rect = overlayRef.current.getBoundingClientRect();
                    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
                    drawRef.current = {
                      startX: (e.clientX - rect.left) / Math.max(1, rect.width),
                      startY: (e.clientY - rect.top) / Math.max(1, rect.height),
                      rect: { width: rect.width, height: rect.height },
                      alt: e.altKey,
                    };
                    setDraftBox({ id: "draft", type: defaultNewType, instanceId: "new", x: 0, y: 0, w: 0, h: 0 });
                  }}
                >
                  <PdfCanvas doc={doc} page={currentPage} zoom={zoom} />
                  {/* Annotation overlay */}
                  <div className="absolute inset-0" onClick={() => setSelectedId(null)}>
                    {/* Draft box rendered while drawing */}
                    {draftBox && (
                      <div
                        className="absolute border-2 border-dashed border-primary/60 bg-primary/10"
                        style={{ left: `${draftBox.x * 100}%`, top: `${draftBox.y * 100}%`, width: `${draftBox.w * 100}%`, height: `${draftBox.h * 100}%` }}
                      />
                    )}
                    {pageBoxes.map((b) => {
                      const isSelected = b.id === selectedId;
                      return (
                        <div data-testid="box"
                          key={b.id}
                          className={`absolute border-2 border-dashed cursor-move transition-all ${isSelected ? "ring-2 ring-primary ring-offset-2" : ""} ${b.type === "Section" ? "border-annotation-section" : "border-annotation-table"}`}
                          style={{ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` }}
                          onPointerDown={(e) => { e.stopPropagation(); beginDrag(b.id, e, "move"); }}
                          onClick={(e) => { e.stopPropagation(); setSelectedId(b.id); }}
                        >
                          {/* Label chip */}
                          <div className={`absolute -top-6 left-0 px-2 py-1 text-xs font-medium text-white rounded ${b.type === "Section" ? "bg-annotation-section" : "bg-annotation-table"}`}>
                            {b.type} · {b.instanceId}
                          </div>
                          {/* Resize handles */}
                          {["nw","n","ne","e","se","s","sw","w"].map((h) => (
                            <div
                              key={h}
                              onPointerDown={(e) => { e.stopPropagation(); beginDrag(b.id, e, h as any); }}
                              className={`absolute w-3 h-3 bg-primary rounded-full shadow -translate-x-1/2 -translate-y-1/2 ${
                                h === "nw" ? "left-0 top-0 cursor-nwse-resize" :
                                h === "n"  ? "left-1/2 top-0 cursor-ns-resize" :
                                h === "ne" ? "left-full top-0 cursor-nesw-resize" :
                                h === "e"  ? "left-full top-1/2 cursor-ew-resize" :
                                h === "se" ? "left-full top-full cursor-nwse-resize" :
                                h === "s"  ? "left-1/2 top-full cursor-ns-resize" :
                                h === "sw" ? "left-0 top-full cursor-nesw-resize" :
                                             "left-0 top-1/2 cursor-ew-resize"}
                              `}
                            />
                          ))}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground">Loading document…</div>
              )}
            </div>

            {/* Floating HUD (draggable, attach) */}
            <div
              data-testid="hud"
              className="absolute bg-card rounded-lg shadow-lg p-2 flex gap-2 items-center cursor-grab"
              style={hudStyle}
              onPointerDown={(e) => {
                if (hudMode !== "free") return;
                const t = e.target as HTMLElement;
                if (t && (t.closest('button') || t.closest('[role="button"]') || t.closest('[data-interactive="true"]'))) return;
                const sx = e.clientX, sy = e.clientY; const start = { ...hudPos };
                (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
                const move = (ev: PointerEvent) => {
                  const rect = overlayRef.current?.getBoundingClientRect();
                  const el = e.currentTarget as HTMLElement;
                  let nx = start.x + (ev.clientX - sx); let ny = start.y + (ev.clientY - sy);
                  if (rect) {
                    nx = Math.max(8, Math.min(rect.width - el.offsetWidth - 8, nx));
                    ny = Math.max(8, Math.min(rect.height - el.offsetHeight - 8, ny));
                  }
                  setHudPos({ x: nx, y: ny });
                };
                const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
                window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
              }}
            >
              <Popover>
                <PopoverTrigger asChild>
                  <Button data-testid="hud-plus" size="sm" variant="outline" title="Label palette"><Plus className="h-4 w-4" /></Button>
                </PopoverTrigger>
                <PopoverContent data-testid="label-palette" className="w-64">
                  <div className="text-xs font-medium mb-2">Set label</div>
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    {labels.map((l) => (
                      <Button key={l.id} data-testid={`label-item-${l.id.toLowerCase()}`} variant="outline" size="sm" onClick={() => {
                        if (selectedId) setPageBoxes((p)=>p.map(b=>b.id===selectedId?{...b,type:l.id}:b)); else setDefaultNewType(l.id);
                      }}>{l.id}</Button>
                    ))}
                  </div>
                  <Separator className="my-2" />
                  <Button data-testid="label-add" size="sm" onClick={() => setAddOpen(true)}>Add Label</Button>
                </PopoverContent>
              </Popover>
              {/* Add Label Dialog */}
              <Dialog open={addOpen} onOpenChange={setAddOpen}>
                <DialogContent data-testid="label-add-dialog" className="max-w-md">
                  <DialogHeader>
                    <DialogTitle>Add Label</DialogTitle>
                    <DialogDescription>Create a new label type for the palette.</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-3 py-2">
                    <div>
                      <label className="text-sm font-medium">Name</label>
                      <Input data-testid="label-name" value={newName} onChange={(e)=>setNewName(e.target.value)} placeholder="Equation" />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-sm font-medium">Icon</label>
                        <Select value={newIcon} onValueChange={setNewIcon}>
                          <SelectTrigger data-testid="icon-select"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem data-testid="icon-option-Heading" value="Heading">Heading</SelectItem>
                            <SelectItem data-testid="icon-option-Table" value="Table">Table</SelectItem>
                            <SelectItem data-testid="icon-option-Image" value="Image">Image</SelectItem>
                            <SelectItem data-testid="icon-option-Sigma" value="Sigma">Sigma</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <label className="text-sm font-medium">Color</label>
                        <Select value={newColor} onValueChange={setNewColor}>
                          <SelectTrigger data-testid="color-select"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem data-testid="color-option-annotation-section" value="annotation-section">Section</SelectItem>
                            <SelectItem data-testid="color-option-annotation-table" value="annotation-table">Table</SelectItem>
                            <SelectItem data-testid="color-option-annotation-figure" value="annotation-figure">Figure</SelectItem>
                            <SelectItem data-testid="color-option-annotation-equation" value="annotation-equation">Equation</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium">Description</label>
                      <Input value={newDesc} onChange={(e)=>setNewDesc(e.target.value)} placeholder="Short description (optional)" />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={()=>setAddOpen(false)}>Cancel</Button>
                    <Button data-testid="label-save" onClick={()=>{
                      const name = newName.trim();
                      if (!name) return;
                      const res = saveLabel({ id: name, icon: newIcon, color: newColor, description: newDesc });
                      if (res.ok) {
                        setLabels(loadLabels());
                        setAddOpen(false);
                        setNewName(""); setNewIcon("Heading"); setNewColor("annotation-section"); setNewDesc("");
                      }
                    }} disabled={!newName.trim()}>
                      Save
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              <Button data-testid="hud-new" size="sm" variant="outline" title="New (N)" onClick={() => setDrawArmed(true)}>
                <Crosshair className="h-4 w-4" />
              </Button>
              <Button
                data-testid="hud-mode-toggle"
                size="sm"
                variant={hudMode === 'attach' ? 'default' : 'outline'}
                title={hudMode === 'attach' ? 'Attached (H to toggle)' : 'Free (H to toggle)'}
                onClick={() => setHudMode(m => m === 'free' ? 'attach' : 'free')}
              >
                {hudMode === 'attach' ? 'Attached' : 'Free'}
              </Button>
              <Button size="sm" variant="outline" title="Help (?)" onClick={()=>setHelpOpen(true)}>?</Button>
              <div className="text-xs text-muted-foreground">Type:</div>
              <Button size="sm" variant={defaultNewType === "Section" ? "default" : "outline"} onClick={() => {
                setDefaultNewType("Section");
                if (selectedId) setPageBoxes((prev) => prev.map((b) => b.id === selectedId ? { ...b, type: "Section" } : b));
              }}>Sec</Button>
              <Button size="sm" variant={defaultNewType === "Table" ? "default" : "outline"} onClick={() => {
                setDefaultNewType("Table");
                if (selectedId) setPageBoxes((prev) => prev.map((b) => b.id === selectedId ? { ...b, type: "Table" } : b));
              }}>Tbl</Button>
              <Button
                size="sm"
                variant="outline"
                title="Duplicate (D)"
                onClick={() => {
                  if (!selectedId) return;
                  setPageBoxes((prev) => {
                    const src = prev.find((b) => b.id === selectedId);
                    if (!src) return prev;
                    const copy: Box = { ...src, id: `${src.id}-${Math.random().toString(36).slice(2, 6)}`, x: Math.min(0.98 - src.w, src.x + 0.02), y: Math.min(0.98 - src.h, src.y + 0.02) };
                    const next = [...prev, copy];
                    setSelectedId(copy.id);
                    return next;
                  });
                }}
              >
                <Copy className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                title="Delete (Del)"
                onClick={() => {
                  if (!selectedId) return;
                  setPageBoxes((prev) => {
                    const filtered = prev.filter((b) => b.id !== selectedId);
                    setSelectedId(filtered.length ? filtered[filtered.length - 1].id : null);
                    return filtered;
                  });
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" title="Export current page JSON"
                onClick={() => {
                  const exportObj = pageBoxes.map((b) => ({
                    type: b.type,
                    instance_id: b.instanceId,
                    bounding_box: [Number(b.x.toFixed(4)), Number(b.y.toFixed(4)), Number(b.w.toFixed(4)), Number(b.h.toFixed(4))],
                  }));
                  setJsonText(JSON.stringify({ page: currentPage, boxes: exportObj }, null, 2));
                  setJsonOpen(true);
                }}
              >
                <Archive className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Pager: thumbnails + slider */}
          <div className="space-y-3">
            {doc && thumbMode === "bottom" && (
              <ThumbnailStrip
                doc={doc}
                pageCount={totalPages}
                currentPage={currentPage}
                onJump={(n) => setCurrentPage(n)}
                height={140}
                itemWidth={120}
              />
            )}
            <div className="flex items-center gap-4">
              <Button size="sm" variant="outline" onClick={() => setCurrentPage(1)} title="First Page">
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} title="Prev">
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <div className="flex-1 text-center">
                <input type="range" min={1} max={totalPages} value={currentPage} onChange={(e) => setCurrentPage(Number(e.target.value))} className="w-full" />
                <div className="text-sm text-muted-foreground mt-1">Page {currentPage} of {totalPages}</div>
              </div>
              <Button size="sm" variant="outline" onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))} title="Next">
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" onClick={() => setCurrentPage(totalPages)} title="Last Page">
                <ChevronsRight className="h-4 w-4" />
              </Button>
              <Separator orientation="vertical" className="mx-2" />
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>Thumbs</span>
                <Select value={thumbMode} onValueChange={(v) => setThumbMode(v as ThumbMode)}><SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="left">Left rail</SelectItem><SelectItem value="bottom">Bottom filmstrip</SelectItem><SelectItem value="off">Off</SelectItem></SelectContent></Select>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>Zoom</span>
                <input type="range" min={0.5} max={2} step={0.1} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} />
                <span>{Math.round(zoom * 100)}%</span>
              </div>
            </div>
          </div>
        </div>

        {/* Inspector Panel */}
        <div className="w-80 border-l bg-card p-6 flex flex-col">
          <h2 className="text-xl font-bold text-destructive mb-4 text-center">Inspector</h2>

          <div className="space-y-5 flex-1">
            <div>
              <label className="text-sm font-medium mb-2 block flex justify-between items-center">
                <span>Label Type</span>
                <span className="text-xs bg-muted px-2 py-1 rounded">L</span>
              </label>
              <Select
                value={selectedBox?.type ?? defaultNewType}
                onValueChange={(val) => {
                  if (selectedId) setPageBoxes((prev) => prev.map((b) => (b.id === selectedId ? { ...b, type: val as string } : b)));
                  else setDefaultNewType(val as string);
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose label type" />
                </SelectTrigger>
                <SelectContent>
                  {labels.map(l => (
                    <SelectItem key={l.id} value={l.id}>{l.id}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Instance ID</label>
              <Input
                value={selectedBox?.instanceId ?? ""}
                onChange={(e) => {
                  const val = e.target.value;
                  if (!selectedId) return;
                  setPageBoxes((prev) => prev.map((b) => (b.id === selectedId ? { ...b, instanceId: val } : b)));
                }}
                placeholder="Unique identifier"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Gold Standard Result</label>
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => {/* stub LLM generate */}}>
                  <Sparkles className="mr-2 h-4 w-4" /> Generate JSON
                </Button>
                <Button size="sm" variant="outline" onClick={() => setJsonOpen(true)} title="Edit JSON">
                  <Edit className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="flex-1 flex flex-col min-h-0">
              <label className="text-sm font-medium mb-2 block">Notes</label>
              <Textarea className="flex-1 min-h-[100px] resize-none" placeholder="Add your notes here..." />
            </div>
          </div>

          <div className="mt-4 pt-4 border-t">
            <div className="text-xs text-muted-foreground space-y-1 text-center">
              <p><span className="bg-muted px-2 py-1 rounded">N</span>: New Box</p>
              <p><span className="bg-muted px-2 py-1 rounded">Ctrl+D</span>: Duplicate Box</p>
              <p><span className="bg-muted px-2 py-1 rounded">[</span> / <span className="bg-muted px-2 py-1 rounded">]</span>: Navigate</p>
            </div>
          </div>
        </div>
      </div>

      {/* Fullscreen JSON Dialog */}
      <Dialog open={jsonOpen} onOpenChange={setJsonOpen}>
        <DialogContent className="max-w-4xl h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>JSON</DialogTitle>
            <DialogDescription>Export preview or free edit. Esc to close, Cmd/Ctrl+Enter to save.</DialogDescription>
          </DialogHeader>
          <Separator className="my-2" />
          <div className="flex-1 overflow-auto">
            <textarea
              className="w-full h-full font-mono text-sm leading-6 outline-none resize-none bg-muted/30 p-3 rounded"
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
            />
          </div>
          <Separator className="my-2" />
          <DialogFooter className="flex items-center gap-2 justify-end">
            <Button variant="outline" onClick={formatJson}>Format</Button>
            <Button variant="outline" onClick={() => navigator.clipboard.writeText(jsonText)}>Copy</Button>
            <Button onClick={() => setJsonOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Help Overlay */}
      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Shortcuts & Modes</DialogTitle>
            <DialogDescription>Quick reference for annotating.</DialogDescription>
          </DialogHeader>
          <div className="text-sm space-y-2">
            <p><b>N</b>: New (arm Draw mode) · <b>ESC</b>: cancel draw · <b>Shift</b>: constrain 4:3</p>
            <p><b>[</b> / <b>]</b>: page prev/next · <b>D</b>/<b>Ctrl+D</b>: duplicate · <b>Delete</b>: remove</p>
            <p><b>H</b>: toggle HUD attach/free · <b>R</b>: reset HUD position</p>
            <p>Thumbs: Left rail / Bottom filmstrip / Off via selector</p>
          </div>
          <DialogFooter>
            <Button onClick={()=>setHelpOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ClassicLayout;
