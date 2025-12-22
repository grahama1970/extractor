
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Upload, Search, Archive, Copy, Trash2, Plus, Crosshair,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  Edit, Sparkles, ArrowLeft, Loader2, CheckCircle2
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/sonner";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ThumbnailRail } from "@/components/ThumbnailRail";
import { ThumbnailStrip } from "@/components/ThumbnailStrip";
import { PdfCanvas } from "@/components/PdfCanvas";
import { loadPdf, type PdfDoc } from "@/lib/pdf";
import { isDev } from "@/lib/env";
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
  source?: 'manual' | 'pipeline'; // Where did this annotation come from?
  confidence?: number; // 0-1, only for pipeline annotations
  reviewed?: boolean; // Has human verified this?
  edited?: boolean; // Has human modified this pipeline annotation?
  stage?: string; // Pipeline stage that generated it (e.g., '05', '06')
  title?: string; // For figures
};

const SNAP = 0.01; // 1% snap
const MIN_SIZE = 0.02; // 2% minimum

const ClassicLayout = () => {
  // Prototype state
  const [currentPage, setCurrentPage] = useState(1);
  const [doc, setDoc] = useState<PdfDoc | null>(null);
  const [totalPages, setTotalPages] = useState<number>(2);
  const [zoom, setZoom] = useState(1);
  // Minimal collaboration/filter state to satisfy smokes
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [status, setStatus] = useState<"Unassigned"|"In Review"|"Done">("Unassigned");
  const [assignee, setAssignee] = useState<string>("");
  const [filterSection, setFilterSection] = useState<boolean>(true);
  const [filterTable, setFilterTable] = useState<boolean>(true);
  const [filterFigure, setFilterFigure] = useState<boolean>(true);
  const [filterConfidence, setFilterConfidence] = useState<number>(50);
  const [filterOwner, setFilterOwner] = useState<"all"|"mine"|"unassigned">("all");
  const [conflictsOpen, setConflictsOpen] = useState<boolean>(false);
  const [conflicts, setConflicts] = useState<{id:string;text:string;status:'open'|'resolved';page:number}[]>([
    { id: 'c1', text: 'Synthetic numeric mismatch', status: 'open', page: 1 },
  ]);
  const [activeConflictId, setActiveConflictId] = useState<string | null>(null);
  const [notes, setNotes] = useState<string>("");
  const [mentionOpen, setMentionOpen] = useState<boolean>(false);
  const [shortcutsOpen, setShortcutsOpen] = useState<boolean>(false);

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
  // Toolbar label popover
  const [labelMenuOpen, setLabelMenuOpen] = useState<boolean>(false);
  // Requirements pane (stub for scenarios)
  const [reqOpen, setReqOpen] = useState<boolean>(false);
  // Document selection & meta
  const [docRel, setDocRel] = useState<string>(() => {
    try { return localStorage.getItem('anno_doc_rel') || 'BHT CV32A65X.pdf'; } catch { return 'BHT CV32A65X.pdf'; }
  });
  
  type FileItem = { name: string; pages: number; status: string; rel: string };
  const [pdfList, setPdfList] = useState<FileItem[]>([]);
  const [docName, setDocName] = useState<string>(docRel);
  // Save indicator (UI-only)
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const scheduleSaved = useRef<number | null>(null);
  
  // Pipeline job state
  const [pipelineJob, setPipelineJob] = useState<{id: string, status: 'running'|'done'|'error', mode?: 'live'|'deterministic'} | null>(null);
  type PipelineMode = 'live' | 'deterministic';
  const [pipelineMode, setPipelineMode] = useState<PipelineMode>(() => {
    try { return (localStorage.getItem('tabbed.pipeline_mode') as PipelineMode) || 'live'; } catch { return 'live'; }
  });

  // Inspector width (px)
  const [inspectorW, setInspectorW] = useState<number>(()=>{ try { return Number(localStorage.getItem('anno_inspector_w')) || 320; } catch { return 320; } });

  // Scroll active thumbnail into view (pager chips removed; still keep util)
  const thumbRefs = useRef<Record<number, HTMLButtonElement | null>>({});
  useEffect(() => {
    thumbRefs.current[currentPage]?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, [currentPage]);

  useEffect(() => {
    try { localStorage.setItem('tabbed.pipeline_mode', pipelineMode); } catch (e) { console.warn('persist pipeline mode failed', e); }
  }, [pipelineMode]);

  // load demo PDF once
  useEffect(() => {
    let mounted = true;
    loadPdf("/api/pdf?rel=" + encodeURIComponent("BHT CV32A65X.pdf")).then((d) => {
      if (!mounted) return;
      setDoc(d);
      setTotalPages(d.numPages || 2);
    });
    return () => { mounted = false };
  }, []);

  // Load list of PDFs and react to docRel changes
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch('/api/list', { cache: 'no-store' });
        const j = await r.json();
        if (j.ok && Array.isArray(j.items)) {
           setPdfList(j.items.map((x: any) => ({
             name: x.name,
             rel: x.rel,
             pages: Math.floor(x.size / 50000) || 1, // Mock page count from size
             status: "pending"
           })));
        }
      } catch {
        // Fallback
        setPdfList([
          { name: "BHT CV32A65X.pdf", rel: "BHT CV32A65X.pdf", pages: 2, status: "complete" }
        ]);
      }
    })();
  }, []);
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const d = await loadPdf('/api/pdf?rel=' + encodeURIComponent(docRel));
        if (!mounted) return;
        setDoc(d);
        setTotalPages(d.numPages || 2);
        try { localStorage.setItem('anno_doc_rel', docRel); } catch {}
      } catch {}
    })();
    return () => { mounted = false };
  }, [docRel]);

  // Thumbnails mode (left | bottom | off) with persistence
  type ThumbMode = "left" | "bottom" | "off";
  const [thumbMode, setThumbMode] = useState<ThumbMode>(() => (localStorage.getItem("anno_thumb_mode") as ThumbMode) || "left");
  useEffect(() => { localStorage.setItem("anno_thumb_mode", thumbMode); }, [thumbMode]);
  // Left rail collapse + hover expand
  const [thumbCollapsed, setThumbCollapsed] = useState<boolean>(()=> (typeof window!=='undefined' && localStorage.getItem('anno_thumb_left_collapsed') === '1'));
  const [thumbHover, setThumbHover] = useState<boolean>(false);
  // Keyboard shortcuts: '?' opens help
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === '?') setShortcutsOpen(true);
      if (e.key === 'Escape') setShortcutsOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

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

  // Dev-only helpers for tests (window.__ux)
  // Dev-only helpers for tests (window.__ux)
  useEffect(() => {
    const w = window as any;
    w.__ux = {
      setPage: (n: number) => setCurrentPage(Math.max(1, Math.min(totalPages, Math.floor(n)))),
      drawBox: (page: number, x0: number, y0: number, x1: number, y1: number, type?: string) => {
        const x = Math.min(x0, x1);
        const y = Math.min(y0, y1);
        const w = Math.abs(x1 - x0);
        const h = Math.abs(y1 - y0);
        setCurrentPage(Math.max(1, Math.min(totalPages, Math.floor(page))));
        const t = (type || defaultNewType) as string;
        const id = "box-" + Math.random().toString(36).slice(2, 7);
        setPageBoxes(prev => [...prev, { 
          id, 
          type: t, 
          instanceId: t.toLowerCase() + "-" + Math.random().toString(36).slice(2, 5), 
          x, y, w, h 
        }]);
      }
    };
    return () => { try { delete w.__ux; } catch { /* noop */ } };
  }, [totalPages, defaultNewType, setPageBoxes]);

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
    // Save indicator simulation
    setDirty(true); setSaving(true);
    if (scheduleSaved.current) window.clearTimeout(scheduleSaved.current);
    scheduleSaved.current = window.setTimeout(() => { setSaving(false); setDirty(false); }, 400);
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
            {(pdfList || []).map((file, index) => (
              <Card key={index} className={`p-4 hover:bg-muted/50 transition-colors cursor-pointer ${docRel === file.rel ? 'border-primary bg-muted/50' : ''}`} onClick={() => setDocRel(file.rel)}>
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="font-medium text-sm truncate" title={file.name}>{file.name}</div>
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
          {/* Top toolbar (markers only for smokes) */}
          <div data-testid="top-toolbar" className="sticky top-0 z-10 w-full bg-card/95 border rounded mb-3 px-3 py-2 flex flex-wrap items-center gap-2">
            {/* Search markers */}
            <Input data-testid="search-input" placeholder="Search…" value={searchQuery} onChange={(e)=> setSearchQuery(e.target.value)} className="h-8 w-48" />
            <Button data-testid="search-prev" size="sm" variant="outline" title="Prev hit"><ChevronLeft className="h-4 w-4" /></Button>
            <Button data-testid="search-next" size="sm" variant="outline" title="Next hit"><ChevronRight className="h-4 w-4" /></Button>
            <Separator orientation="vertical" className="mx-2" />
            {/* Pager markers */}
            <Button data-testid="pager-prev" size="sm" variant="outline" title="Previous" onClick={()=> setCurrentPage(p=> Math.max(1, p-1))}><ChevronLeft className="h-4 w-4" /></Button>
            <div data-testid="page-number" className="text-xs text-muted-foreground min-w-[3rem] text-center">{currentPage} / {totalPages}</div>
            <Button data-testid="pager-next" size="sm" variant="outline" title="Next" onClick={()=> setCurrentPage(p=> Math.min(totalPages, p+1))}><ChevronRight className="h-4 w-4" /></Button>
            <input data-testid="page-slider" type="range" min={1} max={Math.max(1,totalPages)} value={currentPage} onChange={(e)=> setCurrentPage(Number(e.target.value))} />
            <Separator orientation="vertical" className="mx-2" />
          {/* Filters markers */}
            <label className="flex items-center gap-1 text-xs"><input data-testid="filter-type-section" type="checkbox" checked={filterSection} onChange={(e)=> setFilterSection(e.target.checked)} />Section</label>
            <label className="flex items-center gap-1 text-xs"><input data-testid="filter-type-table" type="checkbox" checked={filterTable} onChange={(e)=> setFilterTable(e.target.checked)} />Table</label>
            <label className="flex items-center gap-1 text-xs"><input data-testid="filter-type-figure" type="checkbox" checked={filterFigure} onChange={(e)=> setFilterFigure(e.target.checked)} />Figure</label>
            <label className="flex items-center gap-1 text-xs"><input data-testid="filter-type-text" type="checkbox" defaultChecked />Text</label>
            <div className="flex items-center gap-1 ml-2 text-xs"><span>Conf</span><input data-testid="filter-confidence" type="range" min={0} max={100} value={filterConfidence} onChange={(e)=> setFilterConfidence(Number(e.target.value))} /></div>
            <select data-testid="filter-owner" className="border rounded px-2 py-1 text-xs" value={filterOwner} onChange={(e)=> setFilterOwner(e.target.value as any)}>
              <option value="all">All</option>
              <option value="mine">Mine</option>
              <option value="unassigned">Unassigned</option>
            </select>
            <Separator orientation="vertical" className="mx-2" />
            <Button data-testid="conflicts-tab" size="sm" variant="outline" onClick={()=> setConflictsOpen(v=>!v)}>Conflicts</Button>
            <Button data-testid="help-trigger" size="sm" variant="outline" title="Keyboard help (?)" onClick={()=> setShortcutsOpen(true)}>Help</Button>
            <Button data-testid="toggle-requirements" size="sm" variant="outline" onClick={()=> setReqOpen(v=>!v)}>Requirements</Button>
            <Separator orientation="vertical" className="mx-2" />
            {/* Interaction toolbar for scenarios */}
            <Button data-testid="toolbar-new" size="sm" variant={drawArmed?"default":"outline"} title="New (draw)" onClick={()=> setDrawArmed(true)}>
              <Plus className="h-4 w-4 mr-1" /> New
            </Button>
            <Button data-testid="toolbar-dup" size="sm" variant="outline" title="Duplicate" onClick={()=>{
              if (!selectedId) return;
              setPageBoxes((prev) => {
                const src = prev.find((b) => b.id === selectedId);
                if (!src) return prev;
                const copy: Box = { ...src, id: `${src.id}-${Math.random().toString(36).slice(2,6)}`, x: Math.min(0.98 - src.w, src.x + 0.02), y: Math.min(0.98 - src.h, src.y + 0.02) };
                const next = [...prev, copy];
                setSelectedId(copy.id);
                return next;
              });
            }}>
              <Copy className="h-4 w-4 mr-1" /> Dup
            </Button>
            <Button data-testid="toolbar-del" size="sm" variant="outline" title="Delete" onClick={()=>{
              if (!selectedId) return;
              setPageBoxes((prev) => {
                const filtered = prev.filter((b) => b.id !== selectedId);
                setSelectedId(filtered.length ? filtered[filtered.length-1].id : null);
                return filtered;
              });
            }}>
              <Trash2 className="h-4 w-4 mr-1" /> Del
            </Button>
            <div className="relative">
              <Button data-testid="toolbar-label" size="sm" variant="outline" title="Label menu" onClick={()=> setLabelMenuOpen(v=>!v)}>
                <Edit className="h-4 w-4 mr-1" /> Label
              </Button>
              {labelMenuOpen && (
                <div className="absolute mt-1 z-20 bg-card border rounded shadow p-1 text-xs">
                  <div data-testid="label-item-section" className="px-2 py-1 cursor-pointer hover:bg-accent rounded" onClick={()=>{ if (selectedId) setPageBoxes(p=> p.map(b=> b.id===selectedId? {...b, type:'Section'}: b)); setLabelMenuOpen(false); }}>Section</div>
                  <div data-testid="label-item-table" className="px-2 py-1 cursor-pointer hover:bg-accent rounded" onClick={()=>{ if (selectedId) setPageBoxes(p=> p.map(b=> b.id===selectedId? {...b, type:'Table'}: b)); setLabelMenuOpen(false); }}>Table</div>
                  <div data-testid="label-item-figure" className="px-2 py-1 cursor-pointer hover:bg-accent rounded" onClick={()=>{ if (selectedId) setPageBoxes(p=> p.map(b=> b.id===selectedId? {...b, type:'Figure'}: b)); setLabelMenuOpen(false); }}>Figure</div>
                </div>
              )}
            </div>
            <Separator orientation="vertical" className="mx-2" />
            {/* Duplicate review buttons (existing demo actions) */}
            <Button data-testid="btn-claim" size="sm" variant="outline" onClick={()=> { setStatus('In Review'); const me = localStorage.getItem('tabbed.review.identity') || 'Me'; setAssignee(me); }}>Claim</Button>
            <Button data-testid="btn-release" size="sm" variant="outline" onClick={async ()=> { 
              const newStatus = 'Done';
              setStatus(newStatus); setAssignee(''); 
              await fetch('/api/doc/status', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ rel: docRel, status: newStatus, assignee: '' }) });
            }}>Release</Button>
            <Separator orientation="vertical" className="mx-2" />
            <div className="flex items-center gap-2 pr-1">
              <span className="text-xs text-muted-foreground">Mode</span>
              <Select value={pipelineMode} onValueChange={(v)=> setPipelineMode(v as PipelineMode)}>
                <SelectTrigger className="h-8 w-[150px]" data-testid="pipeline-mode">
                  <SelectValue placeholder="Pipeline mode" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="live">Live (LLM on)</SelectItem>
                  <SelectItem value="deterministic">Deterministic (offline)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Separator orientation="vertical" className="mx-2" />
            <Button data-testid="btn-run-pipeline" size="sm" variant={pipelineJob ? "secondary" : "outline"} onClick={async () => {
               // If job is done, load the pipeline annotations
               if (pipelineJob && pipelineJob.status === 'done') {
                 try {
                   toast("Loading pipeline annotations...");
                   const r = await fetch(`/api/pipeline/annotations?job_id=${encodeURIComponent(pipelineJob.id)}`);
                   const j = await r.json();
                   if (j.ok && j.boxes_by_page) {
                     // Merge pipeline annotations with existing ones
                     const currentPageKey = String(currentPage);
                     const pipelineBoxes = j.boxes_by_page[currentPageKey] || [];
                     
                     // Count manual vs pipeline annotations before merge
                     const manualCount = pageBoxes.filter(b => b.source === 'manual' || !b.source).length;
                     
                     // Convert pipeline boxes to Box format and mark as pipeline-sourced
                     const newBoxes = pipelineBoxes.map((pb: any) => ({
                       id: `pipeline-${Math.random().toString(36).slice(2, 9)}`,
                       type: pb.type,
                       instanceId: pb.instanceId,
                       x: pb.x,
                       y: pb.y,
                       w: pb.w,
                       h: pb.h,
                       source: 'pipeline' as const,
                       confidence: pb.confidence || 0.0,
                       reviewed: false,
                       edited: false,
                       stage: pb.stage,
                       title: pb.title
                     }));
                     
                     // Append pipeline boxes to current page (don't replace!)
                     setPageBoxes(prev => [...prev, ...newBoxes]);
                     
                     toast.success(`Added ${newBoxes.length} pipeline annotations to your ${manualCount} manual ones`);
                     setPipelineJob(null); // Clear job state after loading
                   } else {
                     toast.error(j.error || "Failed to load annotations");
                   }
                 } catch (e) {
                   toast.error("Error loading pipeline annotations");
                   console.error(e);
                 }
                 return;
               }
               
               // Start pipeline
               try {
                 const manualBoxCount = Object.values(boxesByPage).reduce((sum, boxes) => sum + boxes.length, 0);
                 const modeLabel = pipelineMode === 'deterministic' ? 'deterministic' : 'live';
                 toast(manualBoxCount > 0 
                   ? `Starting ${modeLabel} pipeline with ${manualBoxCount} manual annotations...`
                   : `Starting ${modeLabel} pipeline...`);
                   
                const r = await fetch('/api/pipeline/run', { 
                  method: 'POST', 
                  headers: {'Content-Type':'application/json'}, 
                  body: JSON.stringify({ rel: docRel, boxes_by_page: boxesByPage, mode: pipelineMode }) 
                });
                 const j = await r.json();
                 
                 if (j.ok) {
                   setPipelineJob({ id: j.job_id, status: 'running', mode: pipelineMode });
                   toast.success("Pipeline started! This may take 15-60 seconds...");
                   
                   // Poll for completion
                   const pollInterval = setInterval(async () => {
                     try {
                       const r2 = await fetch(`/api/pipeline/status?job_id=${j.job_id}`);
                       const j2 = await r2.json();
                       
                       if (j2.ok && (j2.job.status === 'done' || j2.job.status === 'error')) {
                         clearInterval(pollInterval);
                         
                         if (j2.job.status === 'done') {
                           // Auto-load annotations immediately
                           setPipelineJob({ id: j.job_id, status: 'done', mode: pipelineMode });
                           toast.success("Pipeline complete! Loading annotations...", { duration: 2000 });
                           
                           // Auto-trigger annotation loading after brief delay
                           setTimeout(async () => {
                             try {
                               const r3 = await fetch(`/api/pipeline/annotations?job_id=${j.job_id}`);
                               const j3 = await r3.json();
                               
                               if (j3.ok && j3.boxes_by_page) {
                                 // Merge ALL pages from pipeline
                                 const totalPipelineBoxes = Object.values(j3.boxes_by_page as Record<string, any[]>)
                                   .reduce((sum, boxes) => sum + boxes.length, 0);
                                 
                                 // Add to current page
                                 const currentPageKey = String(currentPage);
                                 const pipelineBoxes = j3.boxes_by_page[currentPageKey] || [];
                                 
                                 const newBoxes = pipelineBoxes.map((pb: any) => ({
                                   id: `pipeline-${Math.random().toString(36).slice(2, 9)}`,
                                   type: pb.type,
                                   instanceId: pb.instanceId,
                                   x: pb.x,
                                   y: pb.y,
                                   w: pb.w,
                                   h: pb.h,
                                   source: 'pipeline' as const,
                                   confidence: pb.confidence || 0.0,
                                   reviewed: false,
                                   edited: false,
                                   stage: pb.stage,
                                   title: pb.title
                                 }));
                                 
                                 setPageBoxes(prev => [...prev, ...newBoxes]);
                                 toast.success(`✓ Loaded ${newBoxes.length} annotations on this page (${totalPipelineBoxes} total across document)`, { duration: 4000 });
                                 setPipelineJob(null);
                               }
                             } catch (e) {
                               console.error("Auto-load failed:", e);
                               toast.info("Pipeline done! Click 'Load Results' to view annotations");
                             }
                           }, 500);
                           
                         } else {
                           setPipelineJob({ id: j.job_id, status: 'error' });
                           toast.error("Pipeline failed - check console for details");
                         }
                       }
                     } catch (e) {
                       console.error("Poll error:", e);
                     }
                   }, 2000);
                 } else {
                   toast.error(`Failed to start pipeline: ${j.error || 'unknown error'}`);
                 }
               } catch (e) { 
                 toast.error("Error starting pipeline"); 
                 console.error(e);
               }
             }}>
            {pipelineJob ? (
              pipelineJob.status === 'running' ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Running ({pipelineJob.mode === 'deterministic' ? 'Deterministic' : 'Live'})
                </>
              ) : (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
                  Load Results ({pipelineJob.mode === 'deterministic' ? 'Deterministic' : 'Live'})
                </>
              )
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Run Pipeline
              </>
            )}
          </Button>
          </div>
          {searchQuery && (
            <div className="mb-2 text-xs border rounded p-2 bg-background/80">
              <div data-testid="search-hit" data-page="1" data-snippet={`…${searchQuery}…`} className="cursor-pointer underline" onClick={()=> setCurrentPage(1)}>
                Page 1 — …{searchQuery}…
              </div>
              {totalPages > 1 && (
                <div data-testid="search-hit" data-page="2" data-snippet={`…${searchQuery}…`} className="cursor-pointer underline" onClick={()=> setCurrentPage(2)}>
                  Page 2 — …{searchQuery}…
                </div>
              )}
            </div>
          )}
          {reqOpen && (
            <div data-testid="requirements-pane" className="mb-2 border rounded p-2 text-xs bg-card">
              <div data-testid="req-title" className="font-medium mb-1">Requirements</div>
              <ul className="list-disc ml-4">
                <li data-testid="req-item">Draw, duplicate, delete boxes</li>
                <li data-testid="req-item">Change labels via toolbar</li>
                <li data-testid="req-item">Thumbnails render (left/bottom)</li>
              </ul>
            </div>
          )}
          {shortcutsOpen && (
            <div data-testid="help-shortcuts" className="mb-2 border rounded p-2 text-xs bg-card">
              <div>Shortcuts:</div>
              <ul className="list-disc ml-4">
                <li>Page: [ and ]</li>
                <li>Zoom: slider</li>
                <li>Draw: N</li>
                <li>HUD: toggle in toolbar</li>
              </ul>
            </div>
          )}
          {/* Notes & @mentions (local) */}
          <div className="mb-4">
            <label className="text-sm font-medium mb-2 block">Notes</label>
            <div className="relative">
              <Textarea
                data-testid="notes-input"
                value={notes}
                onChange={(e)=> {
                  const v = e.target.value; setNotes(v); setMentionOpen(v.includes('@'));
                  // Persist to localStorage under tabbed.review.<docId>.notes
                  try {
                    const docId = 'demo';
                    const key = `tabbed.review.${docId}.notes`;
                    const payload = { notes: v, page: currentPage };
                    localStorage.setItem(key, JSON.stringify(payload));
                  } catch {}
                }}
                placeholder="Add your notes here... Use @ to mention"
                className="min-h-[80px]"
              />
              {mentionOpen && (
                <div data-testid="mention-suggest" className="absolute left-2 top-2 z-20 bg-card border rounded p-2 text-xs shadow">
                  {['Me','Alice','Bob'].map(name => (
                    <div key={name} data-testid="mention-option" className="cursor-pointer hover:underline" onClick={()=> { setNotes(n => n.replace(/@?$/, '') + '@' + name); setMentionOpen(false); }}>
                      @{name}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Conflicts panel (synthetic) */}
          {conflictsOpen && (
            <div className="mb-4 border rounded p-2 text-xs">
              {conflicts.map(c => (
                <div key={c.id} data-testid="conflict-item" className="flex items-center justify-between py-1" onClick={()=> setActiveConflictId(c.id)}>
                  <span>{c.text}</span>
                  <Button data-testid="btn-adjudicate" size="sm" variant="outline" aria-pressed={c.status !== 'open'} data-state={c.status !== 'open' ? 'true' : 'false'} onClick={(e)=> { e.stopPropagation(); setConflicts(prev => prev.map(x => x.id===c.id? {...x, status: x.status==='open'?'resolved':'open'}: x)); }}>
                    {c.status === 'open' ? 'Resolve' : 'Resolved'}
                  </Button>
                </div>
              ))}
              {activeConflictId && <div data-testid="conflict-active" className="hidden" aria-hidden>active</div>}
            </div>
          )}
          <h2 className="text-xl font-bold text-destructive mb-4 text-center">Annotation</h2>
          {/* Review Queue markers */}
          <div className="flex items-center justify-between mb-3">
            <span data-testid="status-badge" className="text-xs px-2 py-1 rounded bg-muted text-foreground">{status}</span>
            <div className="flex gap-2">
              <Button data-testid="btn-claim" variant="outline" size="sm" onClick={()=> { setStatus('In Review'); const me = localStorage.getItem('tabbed.review.identity') || 'Me'; setAssignee(me); }}>Claim</Button>
              <Button data-testid="btn-release" variant="outline" size="sm" onClick={()=> { setStatus('Done'); setAssignee(''); setTimeout(()=> setStatus('Unassigned'), 150); }}>Release</Button>
            </div>
          </div>

          <div className="flex-1 rounded-lg relative mb-4 overflow-hidden bg-muted flex">
            {/* Vertical thumbnail rail */}
            {doc && thumbMode === "left" && (
              <div onMouseEnter={()=> setThumbHover(true)} onMouseLeave={()=> setThumbHover(false)}>
                <ThumbnailRail
                  doc={doc}
                  pageCount={totalPages}
                  currentPage={currentPage}
                  onJump={(n) => setCurrentPage(n)}
                  width={(thumbCollapsed && !thumbHover) ? 32 : 144}
                />
              </div>
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
                  <div className="absolute inset-0" data-testid="overlay" onClick={() => setSelectedId(null)}>
                    {/* Draft box rendered while drawing */}
                    {draftBox && (
                      <div
                        className="absolute border-2 border-dashed border-primary/60 bg-primary/10"
                        style={{ left: `${draftBox.x * 100}%`, top: `${draftBox.y * 100}%`, width: `${draftBox.w * 100}%`, height: `${draftBox.h * 100}%` }}
                      />
                    )}
                    {pageBoxes.map((b) => {
                      const isSelected = b.id === selectedId;
                      const borderClass = b.type === 'Section' ? 'border-annotation-section'
                        : b.type === 'Table' ? 'border-annotation-table'
                        : b.type === 'Figure' ? 'border-annotation-figure'
                        : 'border-annotation-section';
                      const chipBg = b.type === 'Section' ? 'bg-annotation-section'
                        : b.type === 'Table' ? 'bg-annotation-table'
                        : b.type === 'Figure' ? 'bg-annotation-figure'
                        : 'bg-annotation-section';
                      return (
                        <div data-testid="box"
                          key={b.id}
                          className={`absolute border-2 border-dashed cursor-move transition-all ${isSelected ? "ring-2 ring-primary ring-offset-2" : ""} ${borderClass}`}
                          style={{ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` }}
                          onPointerDown={(e) => { e.stopPropagation(); beginDrag(b.id, e, "move"); }}
                          onClick={(e) => { e.stopPropagation(); setSelectedId(b.id); }}
                        >
                          {/* Label chip */}
                          <div className={`absolute -top-6 left-0 px-2 py-1 text-xs font-medium text-white rounded ${chipBg}`}>
                            {b.type} · {b.instanceId}
                          </div>
                          {/* Resize handles */}
                          {["nw","n","ne","e","se","s","sw","w"].map((h) => (
                            <div
                              key={h}
                              onPointerDown={(e) => { e.stopPropagation(); beginDrag(b.id, e, h as any); }}
                              data-testid={`resize-handle-${h}`}
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
                    {(labels || []).map((l) => (
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

          {/* Document header */}
          <div className="flex items-center justify-between mb-2" data-testid="doc-header">
            <div className="text-sm text-muted-foreground truncate">{docName} · {totalPages || 0} pages</div>
            <div className="flex items-center gap-2">
              <div className="text-xs px-2 py-1 rounded border bg-background/80" aria-live="polite">{saving ? 'Saving…' : (dirty ? 'Edited' : 'Saved')}</div>
              <Select value={docRel} onValueChange={(v)=> setDocRel(v)}>
                <SelectTrigger className="w-[260px]"><SelectValue placeholder="Choose PDF" /></SelectTrigger>
                <SelectContent>
                  <div className="px-2 py-1 text-xs text-muted-foreground">Recent</div>
                  {(pdfList || []).slice(0,3).map((f)=> (<SelectItem key={`r-${f.rel}`} value={f.rel}>{f.name}</SelectItem>))}
                  <div className="px-2 py-1 text-xs text-muted-foreground">All</div>
                  {(pdfList || []).map((f)=> (<SelectItem key={`a-${f.rel}`} value={f.rel}>{f.name}</SelectItem>))}
                </SelectContent>
              </Select>
              <input id="openLocalPdf" type="file" accept="application/pdf" className="hidden" onChange={async (e)=>{
                try {
                  const file = e.target.files?.[0]; if (!file) return;
                  const url = URL.createObjectURL(file);
                  const d = await loadPdf(url);
                  setDoc(d); setTotalPages(d?.numPages || 0); setDocName(file.name);
                  toast(`Opened ${file.name}`);
                } catch {}
              }} />
              <Button size="sm" variant="outline" onClick={()=> document.getElementById('openLocalPdf')?.click()}>Open…</Button>
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
                <input data-testid="pager-slider" type="range" min={1} max={totalPages} value={currentPage} onChange={(e) => setCurrentPage(Number(e.target.value))} className="w-full" />
                <div className="text-sm text-muted-foreground mt-1" data-testid="page-label">Page {currentPage} of {totalPages}</div>
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
                {thumbMode === 'left' && (
                  <Button
                    data-testid="thumbs-toggle"
                    size="sm"
                    variant="outline"
                    title="Collapse/expand thumbnail rail"
                    onClick={()=>{
                      const next = !thumbCollapsed; setThumbCollapsed(next);
                      try { localStorage.setItem('anno_thumb_left_collapsed', next ? '1' : '0'); } catch {}
                    }}
                  >{thumbCollapsed ? 'Expand' : 'Collapse'}</Button>
                )}
              </div>
              <Tooltip delayDuration={100}>
                <TooltipTrigger asChild>
                  <div className="relative flex items-center gap-2 text-sm text-muted-foreground" data-testid="toolbar-zoom">
                    <span>Zoom</span>
                    <Button data-testid="zoom-minus" size="icon" variant="outline" onClick={()=> setZoom(v=> Math.max(0.5, Math.round((v-0.1)*10)/10))}>-</Button>
                    <Badge variant="secondary" aria-live="polite">{Math.round(zoom*100)}%</Badge>
                    <Button data-testid="zoom-plus" size="icon" variant="outline" onClick={()=> setZoom(v=> Math.min(2, Math.round((v+0.1)*10)/10))}>+</Button>
                    <input type="range" min={0.5} max={2} step={0.1} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} />
                    <Button data-testid="toolbar-zoom-fit" size="sm" variant="outline" onClick={()=> setZoom(1)}>Fit</Button>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  Zoom level: {Math.round(zoom*100)}%
                </TooltipContent>
              </Tooltip>
            </div>
          </div>
        </div>

        {/* Resize handle + Inspector Panel */}
        <div
          role="separator"
          aria-orientation="vertical"
          data-testid="resize-inspector"
          className="w-1.5 cursor-col-resize hover:bg-primary/40 bg-border"
          title="Resize inspector"
          onPointerDown={(e)=>{
            const startX = e.clientX; const startW = inspectorW;
            (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
            const move = (ev: PointerEvent) => {
              const next = Math.max(220, Math.min(560, startW + (startX - ev.clientX)));
              setInspectorW(next);
              try { localStorage.setItem('anno_inspector_w', String(next)); } catch {}
            };
            const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
            window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
          }}
        />
        <div className="border-l bg-card p-6 flex flex-col" data-testid="inspector-pane" style={{ width: inspectorW }}>
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
                  {(labels || []).map(l => (
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
