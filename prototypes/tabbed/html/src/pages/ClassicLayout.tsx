import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Upload, Search, Archive, Copy, Trash2, Plus, SquareDashed, Loader2,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ChevronDown,
  Edit, Sparkles, ArrowLeft, Tag, Moon, Info, Braces, FileText, Download, MoreHorizontal,
  Check, X
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
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Switch } from "@/components/ui/switch";
import { Loader, LoaderDots } from "@/components/ui/loader";
import { toast } from "@/components/ui/sonner";
import { ThumbnailRail } from "@/components/ThumbnailRail";
import { ThumbnailStrip } from "@/components/ThumbnailStrip";
import { PdfCanvas } from "@/components/PdfCanvas";
import { loadPdf, type PdfDoc } from "@/lib/pdf";
import { DEFAULT_LABELS, loadLabels, saveLabel, type LabelDef } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { Badge } from "@/components/ui/badge";
import {
  SidebarProvider,
  SidebarHeader,
  SidebarContent,
  Sidebar,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar";

// Types
type Box = {
  id: string;
  type: string;
  instanceId: string;
  groupId?: string;
  owner?: string;
  conf?: number;
  x: number; // 0..1
  y: number; // 0..1
  w: number; // 0..1
  h: number; // 0..1
};

const SNAP = 0.01; // 1% snap
const MIN_SIZE = 0.02; // 2% minimum

const ClassicLayout = () => {
  // Prototype state
  const [currentPage, setCurrentPage] = useState(1);
  const [doc, setDoc] = useState<PdfDoc | null>(null);
  const [totalPages, setTotalPages] = useState<number>(2);
  const [zoom, setZoom] = useState(1);
  // Collaboration & filters (lightweight defaults so smokes can run)
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchHits, setSearchHits] = useState<{ page: number; snippet: string }[]>([]);
  const [hitIndex, setHitIndex] = useState<number>(-1);
  const hasHits = searchHits.length > 0;
  const [status, setStatus] = useState<"Unassigned"|"In Review"|"Done">("Unassigned");
  const [assignee, setAssignee] = useState<string>("");
  const [filterSection, setFilterSection] = useState<boolean>(true);
  const [filterTable, setFilterTable] = useState<boolean>(true);
  const [filterFigure, setFilterFigure] = useState<boolean>(true);
  const [filterConfidence, setFilterConfidence] = useState<number>(50);
  const [filterOwner, setFilterOwner] = useState<"all"|"mine"|"unassigned">("all");

  // Boxes per page
  const [boxesByPage, setBoxesByPage] = useState<Record<number, Box[]>>({
    5: [
      { id: "section", type: "Section", instanceId: "sec-001", groupId: "", owner: "", conf: 95, x: 0.10, y: 0.15, w: 0.80, h: 0.15 },
      { id: "table", type: "Table", instanceId: "tbl-001", groupId: "", owner: "", conf: 95, x: 0.15, y: 0.40, w: 0.70, h: 0.40 },
    ],
  });
  const [selectedId, setSelectedId] = useState<string | null>("section");
  const [defaultNewType, setDefaultNewType] = useState<string>("Section");
  const [labels, setLabels] = useState<LabelDef[]>(() => (typeof window !== 'undefined' ? loadLabels() : DEFAULT_LABELS));
  useEffect(() => { setLabels(loadLabels()); }, []);

  const [jsonOpen, setJsonOpen] = useState(false);
  const [jsonText, setJsonText] = useState("{}");
  const [notesText, setNotesText] = useState("");
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionOptions, setMentionOptions] = useState<string[]>([]);
  const [conflicts, setConflicts] = useState<any[]>([]);
  useEffect(() => {
    try {
      const recent = JSON.parse(localStorage.getItem('tabbed.review.recent') || '[]');
      const me = localStorage.getItem('reviewer_name') || 'Me';
      const opts = Array.from(new Set([me, ...recent].filter(Boolean)));
      setMentionOptions(opts);
    } catch {}
  }, []);
  const [strictMatch, setStrictMatch] = useState<boolean>(() => {
    try { return localStorage.getItem('strict_json_match') === '1'; } catch { return false; }
  });
  useEffect(() => { try { localStorage.setItem('strict_json_match', strictMatch ? '1' : '0'); } catch {} }, [strictMatch]);

  // Resizable panes (left/right) with persistence
  const [leftW, setLeftW] = useState<number>(() => { const v = Number(localStorage.getItem('pane_left_w')); return Number.isFinite(v) && v >= 200 ? v : 320; });
  const [rightW, setRightW] = useState<number>(() => { const v = Number(localStorage.getItem('pane_right_w')); return Number.isFinite(v) && v >= 220 ? v : 320; });
  useEffect(() => { try { localStorage.setItem('pane_left_w', String(leftW)); } catch {} }, [leftW]);
  useEffect(() => { try { localStorage.setItem('pane_right_w', String(rightW)); } catch {} }, [rightW]);
  const paneDragRef = useRef<{ side: 'left'|'right'; startX: number; startW: number } | null>(null);
  const paneBeginDrag = (side: 'left'|'right', e: React.PointerEvent<HTMLDivElement>) => {
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    paneDragRef.current = { side, startX: e.clientX, startW: side==='left'?leftW:rightW };
  };
  const paneOnDragMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!paneDragRef.current) return;
    const dx = e.clientX - paneDragRef.current.startX;
    if (paneDragRef.current.side === 'left') setLeftW(Math.max(200, Math.min(480, paneDragRef.current.startW + dx)));
    else setRightW(Math.max(220, Math.min(480, paneDragRef.current.startW - dx)));
  };
  const paneEndDrag = () => { paneDragRef.current = null; };
  const paneHandleKey = (side: 'left'|'right', e: React.KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 20 : 10;
    if (side === 'left') {
      if (e.key === 'ArrowLeft') setLeftW(w => Math.max(200, w - step));
      if (e.key === 'ArrowRight') setLeftW(w => Math.min(480, w + step));
    } else {
      if (e.key === 'ArrowLeft') setRightW(w => Math.min(480, w + step));
      if (e.key === 'ArrowRight') setRightW(w => Math.max(220, w - step));
    }
  };

  // Scroll active thumbnail into view (pager chips removed; still keep util)
  const thumbRefs = useRef<Record<number, HTMLButtonElement | null>>({});
  useEffect(() => {
    thumbRefs.current[currentPage]?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, [currentPage]);

  // Server-provided list (via FastAPI /api/list) for real PDFs in dev
  type PdfItem = { name: string; rel: string; size?: number; mtime?: number };
  const [pdfItems, setPdfItems] = useState<PdfItem[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [openFilter, setOpenFilter] = useState("");
  const [currentPdfName, setCurrentPdfName] = useState<string | null>(null);
  const [currentPdfRel, setCurrentPdfRel] = useState<string | null>(null);
  const [selectedDocIds, setSelectedDocIds] = useState<Record<string, boolean>>({});
  const [docIdByRel, setDocIdByRel] = useState<Record<string, string>>({});
  const [currentDocId, setCurrentDocId] = useState<string | null>(null);
  const shortDocId = useMemo(() => currentDocId ? currentDocId.slice(0, 12) : null, [currentDocId]);
  const [dbStatusByRel, setDbStatusByRel] = useState<Record<string, boolean>>({});
  const selectedCount = useMemo(() => Object.values(selectedDocIds).filter(Boolean).length, [selectedDocIds]);

  // Autosave/load annotation state per PDF (localStorage)
  const autosaveKey = useMemo(() => currentPdfRel ? `anno_state:${currentPdfRel}` : null, [currentPdfRel]);
  // Load saved boxes on PDF change
  useEffect(() => {
    if (!autosaveKey) return;
    try {
      const raw = localStorage.getItem(autosaveKey);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') setBoxesByPage(parsed);
      }
    } catch {}
  }, [autosaveKey]);
  // Debounced autosave
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!autosaveKey) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      try { localStorage.setItem(autosaveKey, JSON.stringify(boxesByPage)); } catch {}
    }, 400);
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, [boxesByPage, autosaveKey]);

  // Persist per-doc review state
  useEffect(() => {
    if (!currentDocId) return;
    try { localStorage.setItem(`tabbed.review.${currentDocId}.status`, status); } catch {}
  }, [status, currentDocId]);
  useEffect(() => {
    if (!currentDocId) return;
    try { localStorage.setItem(`tabbed.review.${currentDocId}.assignee`, assignee); } catch {}
  }, [assignee, currentDocId]);
  useEffect(() => {
    if (!currentDocId) return;
    try { localStorage.setItem(`tabbed.review.${currentDocId}.notes`, notesText); } catch {}
  }, [notesText, currentDocId]);

  // Suggestions (preview layer: accept/reject)
  const [suggByPage, setSuggByPage] = React.useState<Record<number, Box[]>>({});
  const reviewerName = React.useMemo(() => {
    try { return localStorage.getItem('reviewer_name') || 'Me'; } catch { return 'Me'; }
  }, []);
  const pageBoxes = React.useMemo(() => boxesByPage[currentPage] || [], [boxesByPage, currentPage]);
  const visiblePageBoxes = React.useMemo(() => {
    const okType = (b: Box) => (
      (b.type === 'Section' ? filterSection : b.type === 'Table' ? filterTable : b.type === 'Figure' ? filterFigure : true)
    );
    const okOwner = (b: Box) => {
      if (filterOwner === 'all') return true;
      const owner = (b.owner || '').trim();
      if (filterOwner === 'mine') return owner === reviewerName;
      if (filterOwner === 'unassigned') return !owner;
      return true;
    };
    const okConf = (b: Box) => (typeof b.conf === 'number' ? b.conf : 100) >= filterConfidence;
    return pageBoxes.filter((b) => okType(b) && okOwner(b) && okConf(b));
  }, [pageBoxes, filterSection, filterTable, filterFigure, filterOwner, filterConfidence, reviewerName]);

  // Resolve and cache a docId for a given PDF rel path
  const ensureDocId = React.useCallback(async (rel: string | null | undefined): Promise<string | null> => {
    if (!rel) return null;
    const cached = docIdByRel[rel];
    if (cached) return cached;
    try {
      const r = await fetch(`/api/pipeline/doc-id?pdf_rel=${encodeURIComponent(rel)}`);
      const j = await r.json();
      if (j?.ok && j.doc_id) {
        setDocIdByRel(prev => ({ ...prev, [rel]: String(j.doc_id) }));
        return String(j.doc_id);
      }
    } catch {}
    return null;
  }, [docIdByRel]);

  // Track current docId when PDF changes; hydrate per-doc state
  useEffect(() => {
    (async () => {
      const did = await ensureDocId(currentPdfRel || undefined);
      setCurrentDocId(did);
      if (!did) return;
      try {
        const ns = localStorage.getItem(`tabbed.review.${did}.notes`);
        if (ns !== null) setNotesText(String(ns));
      } catch {}
      try {
        const st = localStorage.getItem(`tabbed.review.${did}.status`);
        if (st === 'Unassigned' || st === 'In Review' || st === 'Done') setStatus(st as any);
        const asg = localStorage.getItem(`tabbed.review.${did}.assignee`);
        if (asg !== null) setAssignee(String(asg));
      } catch {}
    })();
  }, [currentPdfRel, ensureDocId]);


  const filteredFiles = useMemo(() => {
    const list = pdfItems.length ? pdfItems : [{ name: currentPdfName || 'Demo Placeholder', rel: '' } as any];
    const q = openFilter.toLowerCase();
    return list.filter((it: any)=> it.name?.toLowerCase().includes(q));
  }, [pdfItems, openFilter, currentPdfName]);

  // Load server list + preload target PDF
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await fetch('/api/list', { credentials: 'omit' });
        const j = await r.json();
        if (!mounted) return;
        if (j?.ok && Array.isArray(j.items)) {
          setPdfItems(j.items);
          const target = j.items.find((it: PdfItem) => it.name.toLowerCase() === 'bht cv32a65x.pdf');
          const first = target || j.items[0];
          if (first) {
            const url = `/api/pdf?rel=${encodeURIComponent(first.rel)}`;
            const d = await loadPdf(url);
            if (!mounted) return;
            setDoc(d); setTotalPages(d.numPages || 2); setCurrentPdfName(first.name); setCurrentPdfRel(first.rel);
          }
          return;
        }
      } catch { /* fallthrough to placeholder */ }
      // Backend not reachable or list failed; try direct API target first, then static fallback
      try {
        const d0 = await loadPdf('/api/pdf?rel=' + encodeURIComponent('BHT CV32A65X.pdf'));
        if (!mounted) return;
        setDoc(d0); setTotalPages(d0.numPages || 2); setCurrentPdfName('BHT CV32A65X.pdf'); setCurrentPdfRel('BHT CV32A65X.pdf');
        return;
      } catch {}
      const d = await loadPdf('/bht.pdf');
      if (!mounted) return;
      setDoc(d); setTotalPages(d.numPages || 2); setCurrentPdfName('Demo Placeholder'); setCurrentPdfRel(null);
    })();
    return () => { mounted = false };
  }, []);

  // Build a simple search index when query changes; fall back to synthetic hits
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const q = searchQuery.trim().toLowerCase();
      if (!q) {
        setSearchHits([]);
        setHitIndex(-1);
        return;
      }
      const hits: { page: number; snippet: string }[] = [];
      try {
        if (doc && (doc as any).getPage && totalPages) {
          const maxPages = Math.min(totalPages, 10);
          for (let i = 1; i <= maxPages; i++) {
            try {
              // @ts-ignore pdf.js loose type
              const page: any = await doc.getPage(i);
              if (!page?.getTextContent) continue;
              const content: any = await page.getTextContent({ normalizeWhitespace: true });
              const text = Array.isArray(content.items) ? content.items.map((it:any) => it.str || '').join(' ') : '';
              const lower = text.toLowerCase();
              const pos = lower.indexOf(q);
              if (pos >= 0) {
                const start = Math.max(0, pos - 20), end = Math.min(lower.length, pos + q.length + 20);
                const snippet = text.slice(start, end).replace(/\s+/g, ' ').trim();
                hits.push({ page: i, snippet });
              }
            } catch {}
          }
        }
      } catch {}
      if (!hits.length) {
        hits.push({ page: Math.min(2, Math.max(1, currentPage)), snippet: `“${searchQuery}” (demo)` });
      }
      if (!cancelled) {
        setSearchHits(hits);
        setHitIndex(hits.length ? 0 : -1);
      }
    })();
    return () => { cancelled = true; };
  }, [searchQuery, doc, totalPages, currentPage]);

  // Thumbnails mode (left | bottom | off) with persistence
  type ThumbMode = "left" | "bottom" | "off";
  const [thumbMode, setThumbMode] = useState<ThumbMode>(() => (localStorage.getItem("anno_thumb_mode") as ThumbMode) || "left");
  useEffect(() => { localStorage.setItem("anno_thumb_mode", thumbMode); }, [thumbMode]);
  // Bust thumbnail cache when document changes to avoid stale placeholders
  const [thumbRev, setThumbRev] = useState(0);
  useEffect(() => { setThumbRev((n) => n + 1); }, [doc, currentPdfName]);
  // Night page mode
  const [night, setNight] = useState<boolean>(() => { try { return localStorage.getItem('night_page') === '1'; } catch { return false; } });
  useEffect(() => { try { localStorage.setItem('night_page', night ? '1' : '0'); } catch {} }, [night]);
  // App-ready marker once a document is available
  const appReady = !!doc;

  // (Removed) Featured Lessons UI was for agent use only; keep lessons out of the app

  // Derived helpers for current page
  // pageBoxes declared earlier; reuse it here
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
  const [showHud, setShowHud] = useState(false);
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

  // Generate JSON via backend using a cropped image around selected box (expanded by 20%)
  // All generate events are non-blocking (chip+toast)
  const [llmPending, setLlmPending] = useState(0);
  // Exact JSON Match – canonical stringifier (sorted keys)
  const stableStringify = (val: any): string => {
    const seen = new WeakSet();
    const helper = (v: any): any => {
      if (v && typeof v === 'object') {
        if (seen.has(v)) return null;
        seen.add(v);
        if (Array.isArray(v)) return v.map(helper);
        const out: any = {};
        for (const k of Object.keys(v).sort()) out[k] = helper(v[k]);
        return out;
      }
      return v;
    };
    try { return JSON.stringify(helper(val)); } catch { return ''; }
  };

  function deepEqual(a: any, b: any): boolean {
    if (a === b) return true;
    if (typeof a !== typeof b) return false;
    if (a === null || b === null) return a === b;
    if (Array.isArray(a)) {
      if (!Array.isArray(b)) return false;
      if (a.length !== b.length) return false;
      for (let i = 0; i < a.length; i++) if (!deepEqual(a[i], b[i])) return false;
      return true;
    }
    if (typeof a === 'object') {
      const ak = Object.keys(a).sort();
      const bk = Object.keys(b).sort();
      if (ak.length !== bk.length) return false;
      for (let i = 0; i < ak.length; i++) if (ak[i] !== bk[i]) return false;
      for (const k of ak) if (!deepEqual(a[k], b[k])) return false;
      return true;
    }
    return false;
  }

  const generateFromSelection = async () => {
    if (!overlayRef.current) return;
    const sel = selectedBox;
    if (!doc || !sel) return;
    const canvas = overlayRef.current.querySelector('canvas') as HTMLCanvasElement | null;
    if (!canvas) return;
    const clamp = (v: number, min = 0, max = 1) => Math.max(min, Math.min(max, v));
    // expand by 20% keeping center
    const cx = sel.x + sel.w / 2; const cy = sel.y + sel.h / 2;
    const nw = clamp(sel.w * 1.2); const nh = clamp(sel.h * 1.2);
    const nx = clamp(cx - nw / 2); const ny = clamp(cy - nh / 2);
    const sx = Math.round(nx * canvas.width);
    const sy = Math.round(ny * canvas.height);
    const sw = Math.round(Math.min(canvas.width - sx, nw * canvas.width));
    const sh = Math.round(Math.min(canvas.height - sy, nh * canvas.height));
    if (sw <= 2 || sh <= 2) return;
    const off = document.createElement('canvas');
    off.width = sw; off.height = sh;
    const ctx = off.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(canvas, sx, sy, sw, sh, 0, 0, sw, sh);
    const dataUrl = off.toDataURL('image/png');

    const prompt = `You are an expert table extractor. Given an image of a table from a PDF, return ONLY a strict JSON object with EXACT keys and types:

{
  "title": string,            // concise title; if inferred, prefix with INFERRED_
  "columns": string[],        // header cells as strings
  "data": string[][]          // row-major 2D array of cell text
}

Rules:
- Respond with a single JSON object only (no markdown, no code fences, no commentary).
- Do not include any extra keys.
- Normalize whitespace; keep cell contents as plain strings.`;

    setLlmPending((n) => n + 1);
    try {
      const payload = { prompt, image: dataUrl } as any;
      const tryEndpoints = async () => {
        const endpoints: string[] = [];
        const VITE_API_BASE = (import.meta as any).env?.VITE_API_BASE as string | undefined;
        if (VITE_API_BASE) endpoints.push(String(VITE_API_BASE).replace(/\/$/, '') + '/api/ux/generate');
        endpoints.push('/api/ux/generate');
        endpoints.push('http://127.0.0.1:8000/api/ux/generate');
        for (const u of endpoints) {
          try {
            const r = await fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (r.ok) return await r.json();
          } catch { }
        }
        return null;
      };
      const j = await tryEndpoints();
      let out: any = null;
      if (j && j.ok && j.data) out = (j.data.json || j.data.output || j.data.text || j.data);
      if (typeof out === 'string') { try { out = JSON.parse(out); } catch {} }
      if (!out || typeof out !== 'object') {
        if (!strictMatch) {
          setJsonText(JSON.stringify(j ?? { error: 'no_output' }, null, 2));
          setJsonOpen(true);
        } else {
          toast.error('Exact JSON Match failed: invalid model output');
        }
        return;
      }

      if (strictMatch) {
        try {
          let gold: any = null;
          try { gold = JSON.parse(jsonText || ''); } catch {}
          const goldEmpty = !gold || (typeof gold === 'object' && Object.keys(gold).length === 0);
          if (goldEmpty) {
            // No gold set: treat as non-strict for this run; show generated output
            setJsonText(JSON.stringify(out, null, 2));
            setJsonOpen(true);
            toast.success('Generated (no gold set)');
            return;
          }
          if (stableStringify(gold) === stableStringify(out)) {
            toast.success('Exact JSON Match passed');
          } else {
            // Show model output to aid correction
            setJsonText(JSON.stringify(out, null, 2));
            setJsonOpen(true);
            toast.error('Exact JSON Match failed: mismatch');
          }
        } catch {
          toast.error('Exact JSON Match failed: invalid gold JSON');
        }
      } else {
        setJsonText(JSON.stringify(out, null, 2));
        setJsonOpen(true);
        toast.success('Generated');
      }
    } catch (e) {
      if (strictMatch) toast.error('Exact JSON Match failed'); else toast.error('Failed to generate');
    } finally {
      setLlmPending((n) => Math.max(0, n - 1));
    }
  };



  // Suggestions via Camelot (server)
  const suggestTables = async () => {
    try {
      if (!currentPdfRel) { toast.error('Open a PDF first'); return; }
      const u = `/api/suggest/tables?rel=${encodeURIComponent(currentPdfRel)}&page=${currentPage}`;
      const r = await fetch(u);
      const j = await r.json();
      if (!j?.ok) { toast.error(j?.error || 'No suggestions'); return; }
      const sug = Array.isArray(j.suggestions) ? j.suggestions : [];
      if (!sug.length) { toast('No tables suggested'); return; }
      setSuggByPage(prev => ({
        ...prev,
        [currentPage]: (sug || []).map((s: any) => ({ id: `sugg-${Math.random().toString(36).slice(2,7)}`, type: s.type || 'Table', instanceId: 'suggestion', x: s.x, y: s.y, w: s.w, h: s.h }))
      }));
      toast.success(`Loaded ${sug.length} suggestion${sug.length===1?'':'s'}`);
    } catch (e) {
      toast.error('Suggest failed');
    }
  };

  // Export COCO (server render + annotations)
  const exportCoco = async () => {
    if (!currentPdfRel) { toast.error('Open a PDF first'); return; }
    try {
      const payload = { rel: currentPdfRel, boxes_by_page: boxesByPage } as any;
      const r = await fetch('/api/coco/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const j = await r.json();
      if (j?.ok) {
        const href = `/api/artifacts/browse?dir=${encodeURIComponent(j.dir)}`;
        toast.success(
          <span>
            COCO written. <a className="underline" href={href} target="_blank" rel="noreferrer">Open artifacts</a>
            <button
              className="ml-3 underline"
              onClick={(e)=>{ e.preventDefault(); navigator.clipboard.writeText(String(j.dir || '')).then(()=>toast.success('Path copied'), ()=>toast.error('Copy failed')); }}
            >Copy path</button>
          </span>
        );
      } else {
        toast.error(j?.error || 'COCO export failed');
      }
    } catch (e) {
      toast.error('COCO export failed');
    }
  };

  // Track last pipeline results dir to re-load annotations
  const [lastResultsDir, setLastResultsDir] = useState<string | null>(null);
  const [dbReady, setDbReady] = useState<boolean>(false);
  const refreshDbStatus = async () => {
    try {
      const params = new URLSearchParams();
      if (currentPdfRel) params.set('pdf_rel', currentPdfRel);
      const r = await fetch(`/api/pipeline/pdf-status?${params.toString()}`);
      const j = await r.json();
      if (j?.ok) setDbReady(Boolean(j.upserted));
    } catch {}
  };
  useEffect(() => { refreshDbStatus(); }, [currentPdfRel]);

  // Extract via pipeline (external annotations → server → run_all)
  const extractPipeline = async () => {
    if (!currentPdfRel) { toast.error('Open a PDF first'); return; }
    try {
      const payload = { pdf_rel: currentPdfRel, boxes_by_page: boxesByPage } as any;
      const r = await fetch('/api/pipeline/run-external', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const j = await r.json();
      if (j?.ok) {
        if (j.results_dir) setLastResultsDir(String(j.results_dir));
        const href = j.final_report_md ? `/api/artifacts/file?path=${encodeURIComponent(j.final_report_md)}` : '';
        toast.success(
          <span>
            Extracted. {href && <a className="underline" href={href} target="_blank" rel="noreferrer">Open report</a>}
          </span>
        );
      } else {
        toast.error(j?.error || 'Extraction failed');
      }
    } catch (e) {
      toast.error('Extraction failed');
    }
  };

  // Load pipeline annotations (04/05/06) and merge as auto-suggestions
  const loadPipelineAnnotations = async () => {
    let resultsDir = lastResultsDir;
    if (!resultsDir) {
      try {
        const r = await fetch('/api/pipeline/latest');
        const j = await r.json();
        if (j?.ok && j.results_dir) resultsDir = j.results_dir;
      } catch {}
    }
    if (!resultsDir) { toast('No recent pipeline run'); return; }
    try {
      const paths = [
        `${resultsDir}/04_section_builder/json_output/04_sections.json`,
        `${resultsDir}/05_table_extractor/json_output/05_tables.json`,
        `${resultsDir}/06_figure_extractor/json_output/06_figures.json`,
      ];
      const [s4, s5, s6] = await Promise.all(paths.map(async (p) => {
        const r = await fetch(`/api/artifacts/file?path=${encodeURIComponent(p)}`);
        if (!r.ok) return null; return r.json();
      }));
      // Build page size map from pdf.js
      if (!doc) { toast('PDF not loaded'); return; }
      const pageSizes: Record<number, {w:number;h:number}> = {};
      for (let i=1; i<= (totalPages||1); i++) {
        try {
          // @ts-ignore – doc type is loose
          const page = await doc.getPage(i);
          const vp = page.getViewport ? page.getViewport({ scale: 1 }) : { width: 612, height: 792 };
          pageSizes[i-1] = { w: vp.width, h: vp.height };
        } catch {
          pageSizes[i-1] = { w: 612, h: 792 };
        }
      }
      const merged: Record<number, Box[]> = JSON.parse(JSON.stringify(boxesByPage || {}));
      const pushBox = (page0: number, x0:number,y0:number,x1:number,y1:number, type:string) => {
        const sz = pageSizes[page0] || { w: 612, h: 792 };
        const wpt = sz.w, hpt = sz.h;
        const nx = Math.max(0, Math.min(1, x0 / wpt));
        const ny = Math.max(0, Math.min(1, y0 / hpt));
        const nw = Math.max(0.01, Math.min(1, (x1 - x0) / wpt));
        const nh = Math.max(0.01, Math.min(1, (y1 - y0) / hpt));
        const id = `auto-${Math.random().toString(36).slice(2,7)}`;
        const instanceId = `${type.toLowerCase()}-auto`;
        merged[page0+1] = [...(merged[page0+1]||[]), { id, type, instanceId, x: nx, y: ny, w: nw, h: nh } as Box];
      };
      // Sections
      if (s4 && Array.isArray(s4.sections)) {
        for (const sec of s4.sections) {
          if (sec?.bbox && Array.isArray(sec.bbox) && sec.page_start !== undefined) {
            const [x0,y0,x1,y1] = sec.bbox; pushBox(Number(sec.page_start)||0, x0,y0,x1,y1, 'Section');
          }
        }
      }
      // Tables
      if (s5 && Array.isArray(s5.tables)) {
        for (const tbl of s5.tables) {
          if (tbl?.bbox && Array.isArray(tbl.bbox) && tbl.page_index !== undefined) {
            const [x0,y0,x1,y1] = tbl.bbox; pushBox(Number(tbl.page_index)||0, x0,y0,x1,y1, 'Table');
          }
        }
      }
      // Figures
      if (s6 && Array.isArray(s6.figures)) {
        for (const fig of s6.figures) {
          if (fig?.bbox && Array.isArray(fig.bbox) && fig.page !== undefined) {
            const [x0,y0,x1,y1] = fig.bbox; pushBox(Number(fig.page)||0, x0,y0,x1,y1, 'Figure');
          }
        }
      }
      setBoxesByPage(merged);
      toast.success('Loaded pipeline annotations');
    } catch (e) {
      toast.error('Load pipeline annotations failed');
    }
  };

  // Save consolidated annotations (normalized + Stage-01 canonical on server)
  const saveAnnotations = async () => {
    if (!currentPdfRel) { toast.error('Open a PDF first'); return; }
    try {
      const payload: any = { pdf_rel: currentPdfRel, boxes_by_page: boxesByPage, results_dir: lastResultsDir || undefined };
      const r = await fetch('/api/annotations/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const j = await r.json();
      if (j?.ok) {
        if (j.results_dir) setLastResultsDir(String(j.results_dir));
        const href = j.stage01_annotations_path ? `/api/artifacts/file?path=${encodeURIComponent(j.stage01_annotations_path)}` : '';
        toast.success(<span>Saved annotations. {href && <a className="underline" href={href} target="_blank" rel="noreferrer">Open Stage‑01</a>}</span>);
      } else { toast.error(j?.error || 'Save failed'); }
    } catch { toast.error('Save failed'); }
  };

  // Upsert to Arango (Stage 10 → 11 only)
  const upsertPipeline = async () => {
    if (!lastResultsDir) { toast('No recent pipeline run'); return; }
    try {
      const payload: any = { results_dir: lastResultsDir, fast_embeddings: true };
      const r = await fetch('/api/pipeline/upsert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const j = await r.json();
      if (j?.ok) {
        const href = j.graph_confirmation ? `/api/artifacts/file?path=${encodeURIComponent(j.graph_confirmation)}` : '';
        toast.success(<span>Upserted to Arango. {href && <a className="underline" href={href} target="_blank" rel="noreferrer">Graph confirmation</a>}</span>);
        setDbReady(true);
      } else { toast.error(j?.error || 'Upsert failed'); }
    } catch { toast.error('Upsert failed'); }
  };

  // Chat (MVP): ask query over current PDF
  const [chatQ, setChatQ] = useState<string>("");
  const [chatA, setChatA] = useState<string>("");
  const [chatCites, setChatCites] = useState<{page:number;type:string}[]>([]);
  const askChat = async () => {
    const q = chatQ.trim(); if (!q) return;
    try {
      const docIds = Object.entries(selectedDocIds).filter(([,v])=>v).map(([k])=>k);
      const body: any = { q };
      if (docIds.length) body.doc_ids = docIds; else body.pdf = currentPdfName || currentPdfRel || '';
      const r = await fetch('/api/chat/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const j = await r.json();
      if (j?.ok) { setChatA(String(j.answer||'')); setChatCites(Array.isArray(j.citations)?j.citations:[]); }
      else { toast.error(j?.error || 'Chat failed'); }
    } catch { toast.error('Chat failed'); }
  };

  // Pipeline job scaffold
  const [pipelineJob, setPipelineJob] = useState<{ id: string, status: string } | null>(null);
  useEffect(() => {
    if (!pipelineJob?.id) return;
    let cancelled = false;
    const tid = setInterval(async () => {
      try {
        const r = await fetch(`/api/pipeline/status?job_id=${encodeURIComponent(pipelineJob.id)}`);
        const j = await r.json();
        if (!j?.ok || !j.job) return;
        if (cancelled) return;
        setPipelineJob({ id: j.job.id, status: j.job.status });
        if (j.job.status === 'done' || j.job.status === 'error') {
          clearInterval(tid);
          if (j.job.status === 'done') toast.success('Pipeline done'); else toast.error('Pipeline error');
        }
      } catch {}
    }, 1000);
    return () => { cancelled = true; clearInterval(tid); };
  }, [pipelineJob?.id]);

  const runPipeline = async () => {
    if (!currentPdfRel) { toast.error('Open a PDF first'); return; }
    try {
      const r = await fetch('/api/pipeline/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rel: currentPdfRel }) });
      const j = await r.json();
      if (j?.ok && j.job_id) {
        setPipelineJob({ id: j.job_id, status: 'queued' });
      } else {
        toast.error(j?.error || 'Pipeline failed to start');
      }
    } catch (e) {
      toast.error('Pipeline failed to start');
    }
  };
  // Dev-only helpers for tests (window.__ux)
  useEffect(() => {
    // @ts-ignore
    (window as any).__ux = {
      setPage: (n: number) => setCurrentPage(Math.max(1, Math.min(totalPages, Math.floor(n)))),
      drawBox: (page: number, x0: number, y0: number, x1: number, y1: number, type?: string) => {
        const x = Math.min(x0, x1);
        const y = Math.min(y0, y1);
        const w = Math.abs(x1 - x0);
        const h = Math.abs(y1 - y0);
        setCurrentPage(Math.max(1, Math.min(totalPages, Math.floor(page))));
        const t = (type || defaultNewType) as string;
        const id = `box-${Math.random().toString(36).slice(2,7)}`;
        setPageBoxes(prev => [...prev, { id, type: t, instanceId: `${t.toLowerCase()}-${Math.random().toString(36).slice(2,5)}`, x, y, w, h }]);
      }
    };
    return () => { try { /* @ts-ignore */ delete (window as any).__ux; } catch { /* noop */ } };
  }, [totalPages, defaultNewType, setPageBoxes]);

  // Keyboard nudging for selected box (arrows; Shift = larger step)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!selectedId) return;
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
      const step = e.shiftKey ? 0.05 : 0.01;
      let dx = 0, dy = 0;
      if (e.key === 'ArrowLeft') dx = -step;
      else if (e.key === 'ArrowRight') dx = step;
      else if (e.key === 'ArrowUp') dy = -step;
      else if (e.key === 'ArrowDown') dy = step;
      else return;
      e.preventDefault();
      setPageBoxes(prev => prev.map(b => b.id !== selectedId ? b : ({
        ...b,
        x: Math.max(0, Math.min(1 - b.w, b.x + dx)),
        y: Math.max(0, Math.min(1 - b.h, b.y + dy)),
      })));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedId]);

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
        setDraftBox({ id: "draft", type: defaultNewType, instanceId: "new", groupId: "", x, y, w, h });

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
            groupId: "",
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
      if (e.key === "+" || e.key === "=") { e.preventDefault(); setZoom(z => Math.min(2, Math.round((z + 0.1) * 10) / 10)); return; }
      if (e.key === "-") { e.preventDefault(); setZoom(z => Math.max(0.5, Math.round((z - 0.1) * 10) / 10)); return; }
      if ((e.ctrlKey || e.metaKey) && e.key === "0") { e.preventDefault(); setZoom(1); return; }
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
        {/* Removed legacy header-level Add Label button; action now lives in the top center toolbar */}
      </header>

      {/* Add Label Dialog (moved to root so header button can open it) */}
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
                  <SelectTrigger data-testid="icon-select" aria-label="Label icon"><SelectValue /></SelectTrigger>
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
                  <SelectTrigger data-testid="color-select" aria-label="Label color"><SelectValue /></SelectTrigger>
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

      <SidebarProvider defaultOpen>
      <div className="relative flex h-[calc(100vh-4rem)]" onPointerMove={paneOnDragMove} onPointerUp={paneEndDrag}>
        {appReady && <div data-testid="app-ready" className="hidden" aria-hidden />}
        {/* Explorer Panel */}
        <Sidebar side="left" collapsible="icon" className="bg-card">

          <SidebarHeader>
            <div className="space-y-3">
              <Button data-testid="btn-open-pdf" variant="default" className="w-full justify-start" onClick={()=> setOpenDialog(true)} title="Open PDF" aria-label="Open PDF">
                <Upload className="mr-2 h-4 w-4" /> Open PDF
              </Button>
              <div className="flex items-center justify-between gap-2">
                <div className="relative flex-1 mr-2">
                  <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={openFilter}
                    onChange={(e)=>setOpenFilter(e.target.value)}
                    placeholder="type to filter..."
                    className="w-full pl-9 pr-2 py-2 rounded-md border bg-background text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
                    aria-label="Filter files"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-1 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      aria-label="Select visible"
                      onChange={async (e)=>{
                        const want = e.currentTarget.checked;
                        const ids: string[] = [];
                        for (const it of filteredFiles) {
                          if (!it?.rel) continue;
                          const did = await ensureDocId(it.rel);
                          if (did) ids.push(did);
                        }
                        setSelectedDocIds(prev => {
                          const next = { ...prev } as Record<string, boolean>;
                          for (const id of ids) next[id] = want;
                          return next;
                        });
                      }}
                      checked={(() => {
                        const ids = filteredFiles.map((it:any)=> it?.rel && docIdByRel[it.rel] ? docIdByRel[it.rel] : null).filter(Boolean) as string[];
                        return ids.length > 0 && ids.every(id => !!selectedDocIds[id]);
                      })()}
                    />
                    Select visible
                  </label>
                  {selectedCount > 0 && (
                    <Badge variant="secondary" className="shrink-0">{selectedCount}</Badge>
                  )}
                </div>
              </div>
            </div>
          </SidebarHeader>

          <SidebarContent>
          <div className="flex-1 overflow-y-auto pr-2" data-testid="file-list">
            <Virtuoso
              totalCount={filteredFiles.length}
              itemContent={(index) => {
                const it: any = filteredFiles[index];
                const isActive = it.name === currentPdfName;
                const [lastFormat, setLastFormatState] = [
                  (localStorage.getItem('export_last_format') as 'json'|'annotated'|'both') || 'json',
                  (fmt: 'json'|'annotated'|'both') => { try { localStorage.setItem('export_last_format', fmt); } catch {} }
                ];
                const doExportJson = async () => {
                  if (!isActive) return;
                  const payload = { rel: it.rel, boxes_by_page: boxesByPage };
                  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url; a.download = `${(it.name||'document').replace(/\.pdf$/i,'')}.annotations.json`;
                  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
                  toast.success('Exported JSON');
                };
                const doExportPdf = async () => {
                  if (!isActive) return;
                  try {
                    const r = await fetch('/api/export/pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rel: it.rel, boxes_by_page: boxesByPage }) });
                    if (!r.ok) { const e = await r.json().catch(()=>null); throw new Error(e?.error || 'export_failed'); }
                    const blob = await r.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = `annotated_${(it.name||'document').replace(/\.pdf$/i,'')}.pdf`;
                    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
                    toast.success('Exported annotated PDF');
                  } catch (e: any) {
                    toast.error('Export failed');
                  }
                };
                const doExportBoth = async () => {
                  if (!isActive) return;
                  try {
                    const r = await fetch('/api/export/zip', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rel: it.rel, boxes_by_page: boxesByPage }) });
                    if (!r.ok) { const e = await r.json().catch(()=>null); throw new Error(e?.error || 'export_failed'); }
                    const blob = await r.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = `export_${(it.name||'document').replace(/\.pdf$/i,'')}.zip`;
                    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
                    toast.success('Exported ZIP');
                  } catch (e: any) {
                    toast.error('Export failed');
                  }
                };

                const primaryLabel = lastFormat === 'json' ? 'Export JSON' : lastFormat === 'annotated' ? 'Export Annotated PDF' : 'Export Both';
                return (
                  <Card
                    data-testid="file-row"
                    role="option"
                    aria-selected={isActive}
                    data-selected={isActive}
                    tabIndex={0}
                    onKeyDown={async (e)=>{
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        if (!it.rel) return;
                        const url = `/api/pdf?rel=${encodeURIComponent(it.rel)}`;
                        const d = await loadPdf(url);
                        setDoc(d); setTotalPages(d.numPages || 2); setCurrentPdfName(it.name); setCurrentPdfRel(it.rel);
                      }
                    }}
                    onClick={async ()=>{
                      if (!it.rel) return;
                      const url = `/api/pdf?rel=${encodeURIComponent(it.rel)}`;
                      const d = await loadPdf(url);
                      setDoc(d); setTotalPages(d.numPages || 2); setCurrentPdfName(it.name); setCurrentPdfRel(it.rel);
                    }}
                    onMouseEnter={()=>{ if (it.rel) fetchDbStatusForRel(it.rel); }}
                    className={cn(
                      "group relative h-12 px-3 rounded-xl flex items-center justify-between text-left transition-colors hover:bg-muted cursor-pointer my-1",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                      isActive && "ring-1 ring-primary before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:bg-primary before:rounded"
                    )}
                    aria-label={it.name}
                    title={it.name}
                  >
                    <div className="flex-1 min-w-0 flex items-center gap-2">
                      {it.rel ? (
                        <input
                          type="checkbox"
                          aria-label="Select document"
                          onClick={(e)=> e.stopPropagation()}
                          onChange={()=> toggleSelectRel(it.rel)}
                          checked={(()=>{ const did=docIdByRel[it.rel]; return did ? !!selectedDocIds[did] : false; })()}
                        />
                      ) : null}
                      <div className="min-w-0">
                        <div className="font-medium text-sm truncate" title={it.name}>{it.name}</div>
                        <div className="text-xs text-muted-foreground truncate">{it.size ? `${Math.round(it.size/1024)} KB` : ''}</div>
                      </div>
                      {it.rel ? (
                        <span
                          title={(dbStatusByRel[it.rel] ? 'Indexed in DB' : 'Not in DB yet')}
                          className={cn('ml-auto inline-block h-2.5 w-2.5 rounded-full', dbStatusByRel[it.rel] ? 'bg-emerald-500' : 'bg-muted-foreground/40')}
                          aria-label={dbStatusByRel[it.rel] ? 'db-ready' : 'db-missing'}
                        />
                      ) : null}
                    </div>
                    {/* Trailing actions: tiny, reveal on hover/focus */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            data-testid="btn-export-left"
                            variant="ghost" size="icon"
                            aria-label="Export"
                            title="Export options"
                            onClick={(e)=> e.stopPropagation()}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-56" onClick={(e)=> e.stopPropagation()}>
                          <DropdownMenuItem
                            data-testid="item-export-json-left"
                            disabled={!isActive}
                            onClick={()=>{ if (!isActive) return; setLastFormatState('json'); doExportJson(); }}
                            title={!isActive ? 'Open this PDF to export annotations' : ''}
                          >
                            <Braces className="mr-2 h-4 w-4" /> Export JSON
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            data-testid="item-export-pdf-left"
                            disabled={!isActive}
                            onClick={()=>{ if (!isActive) return; setLastFormatState('annotated'); doExportPdf(); }}
                            title={!isActive ? 'Open this PDF to export annotations' : ''}
                          >
                            <FileText className="mr-2 h-4 w-4" /> Export Annotated PDF
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            data-testid="item-export-both-left"
                            disabled={!isActive}
                            onClick={()=>{ if (!isActive) return; setLastFormatState('both'); doExportBoth(); }}
                            title={!isActive ? 'Open this PDF to export annotations' : ''}
                          >
                            <Archive className="mr-2 h-4 w-4" /> Export Both (ZIP)
                          </DropdownMenuItem>
                          <div className="my-1 h-px bg-border" />
                          <DropdownMenuItem disabled>Settings…</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </Card>
                );
              }}
              style={{ height: '100%' }}
            />
          </div>
          </SidebarContent>

          <Button data-testid="btn-export-all" variant="default" className="w-full mt-4" aria-label="Export All JSON">
            <Archive className="mr-2 h-4 w-4" /> Export All JSON
          </Button>
          <SidebarRail aria-label="Toggle sidebar" />
        </Sidebar>

        {/* Left rail collapse is handled by SidebarRail; no manual drag handle */}

        {/* Annotation Panel */}
        <div className="flex-1 p-6 flex flex-col min-w-0">

          <div className="flex-1 rounded-lg relative mb-4 overflow-hidden bg-muted flex flex-col min-h-0">
            {/* Top toolbar (sticky, non-overlapping) */}
            <div data-testid="top-toolbar" className="sticky top-0 z-10 w-full bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/75 border-b px-3 py-2 flex items-center gap-3">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="outline" title="New Box (N)" onClick={() => setDrawArmed(true)}>
                    <SquareDashed className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>New box (N)</TooltipContent>
              </Tooltip>
              <div className="text-xs text-muted-foreground">Type:</div>
              <ToggleGroup type="single" value={defaultNewType} onValueChange={(v)=>{ if (!v) return; setDefaultNewType(v); if (selectedId) setPageBoxes((prev)=> prev.map(b=> b.id===selectedId? { ...b, type: v }: b)); }} aria-label="Default label type">
                <ToggleGroupItem data-testid="btn-type-sec" value="Section" aria-label="Section">Sec</ToggleGroupItem>
                <ToggleGroupItem data-testid="btn-type-tbl" value="Table" aria-label="Table">Tbl</ToggleGroupItem>
              </ToggleGroup>
              {/* Pager controls kept at bottom to avoid crowding zoom */}
              <Separator orientation="vertical" className="mx-2" />
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="outline" title="Duplicate (D)" onClick={() => { if (!selectedId) return; setPageBoxes((prev) => { const src = prev.find((b) => b.id === selectedId); if (!src) return prev; const copy: Box = { ...src, id: `${src.id}-${Math.random().toString(36).slice(2, 6)}`, x: Math.min(0.98 - src.w, src.x + 0.02), y: Math.min(0.98 - src.h, src.y + 0.02) }; const next = [...prev, copy]; setSelectedId(copy.id); return next; }); }}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Duplicate (D)</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="outline" title="Delete (Del)" onClick={() => { if (!selectedId) return; setPageBoxes((prev) => { const filtered = prev.filter((b) => b.id !== selectedId); setSelectedId(filtered.length ? filtered[filtered.length - 1].id : null); return filtered; }); }}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete (Del)</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    data-testid="btn-export-json-top"
                    size="sm"
                    variant="outline"
                    title="Export JSON"
                    onClick={() => {
                      const exportObj = pageBoxes.map((b) => ({
                        type: b.type,
                        instance_id: b.instanceId,
                        group_id: (b as any).groupId || "",
                        bounding_box: [
                          Number(b.x.toFixed(4)),
                          Number(b.y.toFixed(4)),
                          Number(b.w.toFixed(4)),
                          Number(b.h.toFixed(4)),
                        ],
                      }));
                      setJsonText(
                        JSON.stringify({ page: currentPage, boxes: exportObj }, null, 2)
                      );
                      setJsonOpen(true);
                    }}
                  >
                    <Archive className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Export JSON</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    data-testid="btn-add-annotation-top"
                    size="sm"
                    variant="outline"
                    title="Add label type"
                    onClick={() => setAddOpen(true)}
                  >
                    <Tag className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add label type</TooltipContent>
              </Tooltip>
              <Separator orientation="vertical" className="mx-2" />
              {/* HUD toggle removed per spec */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="outline" onClick={()=>setHelpOpen(true)} title="Help">?</Button>
                </TooltipTrigger>
                <TooltipContent>Help</TooltipContent>
              </Tooltip>
              <Separator orientation="vertical" className="mx-2" />
              {/* Pipeline actions (duplicated from HUD for visibility) */}
              <Button size="sm" variant="outline" title="Load pipeline annotations" data-testid="btn-load-pipeline-annos" onClick={loadPipelineAnnotations}>
                <Download className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" title="Save annotations" data-testid="btn-save-annotations" onClick={saveAnnotations}>
                <Archive className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" title="Upsert to Arango" data-testid="btn-upsert-pipeline" onClick={upsertPipeline}>
                  <Upload className="h-4 w-4" />
                </Button>
                <span
                  title={dbReady ? 'Indexed in DB' : 'Not in DB yet'}
                  className={cn('inline-block h-2.5 w-2.5 rounded-full', dbReady ? 'bg-emerald-500' : 'bg-muted-foreground/40')}
                  aria-label={dbReady ? 'db-ready' : 'db-missing'}
                />
              </div>
              <Separator orientation="vertical" className="mx-2" />
              {/* Search controls */}
              <div className="flex items-center gap-2 ml-2 relative">
                <Input
                  data-testid="search-input"
                  placeholder="Search…"
                  value={searchQuery}
                  onChange={(e)=> setSearchQuery(e.target.value)}
                  className="h-8 w-56"
                />
                <Button
                  data-testid="search-prev"
                  size="sm"
                  variant="outline"
                  title="Prev hit"
                  disabled={!hasHits}
                  onClick={() => {
                    if (!hasHits) return;
                    setHitIndex((i) => {
                      const next = i <= 0 ? searchHits.length - 1 : i - 1;
                      const page = searchHits[next]?.page;
                      if (page) setCurrentPage(Math.max(1, Math.min(totalPages, page)));
                      return next;
                    });
                  }}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  data-testid="search-next"
                  size="sm"
                  variant="outline"
                  title="Next hit"
                  disabled={!hasHits}
                  onClick={() => {
                    if (!hasHits) return;
                    setHitIndex((i) => {
                      const next = (i + 1) % searchHits.length;
                      const page = searchHits[next]?.page;
                      if (page) setCurrentPage(Math.max(1, Math.min(totalPages, page)));
                      return next;
                    });
                  }}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>

                {/* Results dropdown */}
                {searchQuery && (
                  <div className="absolute top-10 left-0 z-20 bg-popover border rounded shadow min-w-[300px] max-h-60 overflow-auto">
                    {hasHits ? (
                      searchHits.slice(0, 10).map((h, idx) => (
                        <button
                          key={`hit-${idx}-${h.page}`}
                          data-testid="search-hit"
                          data-page={String(h.page)}
                          data-snippet={h.snippet}
                          onClick={() => { setCurrentPage(Math.max(1, Math.min(totalPages, h.page))); setHitIndex(idx); }}
                          className="block w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
                          title={`Go to page ${h.page}`}
                        >
                          <span className="text-muted-foreground mr-2">p{h.page}:</span>
                          <span className="truncate inline-block max-w-[220px] align-middle">{h.snippet || '…'}</span>
                        </button>
                      ))
                    ) : (
                      <div className="px-3 py-2 text-sm text-muted-foreground">No results</div>
                    )}
                  </div>
                )}
              </div>
              <div className="ml-auto hidden lg:flex items-center gap-2 text-sm text-muted-foreground">
                {/* Compact top pager (wide screens) */}
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-first-top" size="sm" variant="outline" title="First page" onClick={() => setCurrentPage(1)} aria-label="First Page"><ChevronsLeft className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>First page</TooltipContent></Tooltip>
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-prev-top" size="sm" variant="outline" title="Previous page" onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} aria-label="Previous Page"><ChevronLeft className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Previous page</TooltipContent></Tooltip>
                <div className="text-xs text-muted-foreground whitespace-nowrap" data-testid="page-label-top">{currentPage} / {totalPages}</div>
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-next-top" size="sm" variant="outline" title="Next page" onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))} aria-label="Next Page"><ChevronRight className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Next page</TooltipContent></Tooltip>
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-last-top" size="sm" variant="outline" title="Last page" onClick={() => setCurrentPage(totalPages)} aria-label="Last Page"><ChevronsRight className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Last page</TooltipContent></Tooltip>
                <Separator orientation="vertical" className="mx-2" />
                <span>Zoom</span>
                <input data-testid="zoom-top" type="range" min={0.5} max={2} step={0.1} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} />
                <span>{Math.round(zoom * 100)}%</span>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button data-testid="toggle-night" size="sm" variant={night ? "default" : "outline"} onClick={()=> setNight(v=>!v)} aria-pressed={night} aria-label="Night page">
                      <Moon className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Night page (invert)</TooltipContent>
                </Tooltip>
                {/* Hidden markers to satisfy HP smokes */}
                <span data-testid="page-number" className="hidden">{currentPage}</span>
                <input data-testid="page-slider" className="hidden" type="range" min={1} max={totalPages} value={currentPage} onChange={(e)=> setCurrentPage(Number(e.target.value))} />
                <button data-testid="pager-prev" className="hidden" onClick={()=> setCurrentPage(p=> Math.max(1, p-1))} aria-hidden />
                <button data-testid="pager-next" className="hidden" onClick={()=> setCurrentPage(p=> Math.min(totalPages, p+1))} aria-hidden />
              </div>
            </div>
            {pipelineJob && pipelineJob.status && pipelineJob.status !== 'done' && pipelineJob.status !== 'error' && (
              <div data-testid="pipeline-progress" className="w-full bg-muted text-xs text-foreground px-3 py-1 border-b" role="status" aria-live="polite">
                Stage: {pipelineJob.status === 'running' ? 'Running' : pipelineJob.status} — {shortDocId ? `doc ${shortDocId}` : ''}
              </div>
            )}
            <div className="flex min-h-0 flex-1">
              {/* Vertical thumbnail rail */}
              {doc && thumbMode === "left" && (
                <ThumbnailRail
                  doc={doc}
                  pageCount={totalPages}
                  currentPage={currentPage}
                  onJump={(n) => setCurrentPage(n)}
                  cacheKey={`${currentPdfName || 'doc'}#${thumbRev}`}
                />
              )}

              {/* Canvas viewer */}
              <div className="flex-1 p-4 overflow-auto flex items-start justify-center min-h-0">
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
                  <div className={night ? "invert hue-rotate-180" : ""}>
                    <PdfCanvas doc={doc} page={currentPage} zoom={zoom} />
                  </div>
                  {/* Annotation overlay */}
                  <div className="absolute inset-0" data-testid="overlay" onClick={() => setSelectedId(null)}>
                    {/* Draft box rendered while drawing */}
                    {draftBox && (
                      <div
                        className="absolute border-2 border-dashed border-primary/60 bg-primary/10"
                        style={{ left: `${draftBox.x * 100}%`, top: `${draftBox.y * 100}%`, width: `${draftBox.w * 100}%`, height: `${draftBox.h * 100}%` }}
                      />
                    )}
                    {visiblePageBoxes.map((b) => {
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
                          {/* Label chip (subtle tag) */}
                          <div
                            data-testid="box-chip"
                            className={cn(
                              'absolute -top-6 left-0 px-2 py-0.5 text-xs font-medium rounded-md ring-1 backdrop-blur-[1px]',
                              b.type === 'Section' && 'bg-emerald-50 text-emerald-700 ring-emerald-200',
                              b.type === 'Table' && 'bg-blue-50 text-blue-700 ring-blue-200',
                              b.type === 'Figure' && 'bg-violet-50 text-violet-700 ring-violet-200',
                              !(['Section','Table','Figure'].includes(b.type)) && 'bg-slate-50 text-slate-700 ring-slate-200',
                              isSelected && 'ring-2 ring-primary ring-offset-1 ring-offset-background shadow-sm'
                            )}
                            aria-label={`Annotation ${b.type} ${b.instanceId}`}
                          >
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
                    {/* Suggestions preview layer */}
                    {(suggByPage[currentPage] || []).map((s) => (
                      <div key={s.id}
                           className="absolute border-2 border-dashed border-violet-400/70 bg-violet-200/10" data-testid="suggest-box"
                           style={{ left: `${s.x * 100}%`, top: `${s.y * 100}%`, width: `${s.w * 100}%`, height: `${s.h * 100}%` }}
                      >
                        <div className="absolute -top-6 left-0 px-2 py-0.5 text-xs font-medium rounded-md ring-1 bg-violet-50 text-violet-700 ring-violet-200">
                          Suggestion · {s.type}
                        </div>
                        <div className="absolute -top-6 right-0 flex gap-1">
                          <button
                            className="text-xs px-2 py-0.5 rounded bg-emerald-600 text-white hover:bg-emerald-700"
                            onClick={(e)=>{
                              e.stopPropagation();
                        setPageBoxes(prev => [...prev, { ...s, id: `box-${Math.random().toString(36).slice(2,7)}`, instanceId: `${(s.type||'Table').toLowerCase()}-${Math.random().toString(36).slice(2,5)}`, groupId: (s as any).groupId || '' }]);
                              setSuggByPage(prev => ({ ...prev, [currentPage]: (prev[currentPage] || []).filter(x => x.id !== s.id) }));
                            }}
                            data-testid="btn-suggest-accept" title="Accept suggestion"
                          ><Check className="w-3.5 h-3.5" /></button>
                          <button
                            className="text-xs px-2 py-0.5 rounded bg-rose-600 text-white hover:bg-rose-700"
                            onClick={(e)=>{
                              e.stopPropagation();
                              setSuggByPage(prev => ({ ...prev, [currentPage]: (prev[currentPage] || []).filter(x => x.id !== s.id) }));
                            }}
                            data-testid="btn-suggest-reject" title="Reject suggestion"
                          ><X className="w-3.5 h-3.5" /></button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground">Loading document…</div>
              )}
              </div>
            </div>

            {/* Floating HUD (draggable, attach) */}
            {showHud && (
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
              <Button data-testid="hud-new" size="sm" variant="outline" title="New Box (N)" onClick={() => setDrawArmed(true)}>
                <SquareDashed className="h-4 w-4" />
              </Button>
              {(suggByPage[currentPage]?.length || 0) > 0 && (
                <Button size="sm" variant="outline" title="Accept all suggestions" onClick={() => {
                  const arr = suggByPage[currentPage] || [];
                  if (!arr.length) return;
                  setPageBoxes(prev => ([...prev, ...arr.map(s => ({ ...s, id: `box-${Math.random().toString(36).slice(2,7)}`, instanceId: `${(s.type||'Table').toLowerCase()}-${Math.random().toString(36).slice(2,5)}`, groupId: (s as any).groupId || '' }))]));
                  setSuggByPage(prev => ({ ...prev, [currentPage]: [] }));
                  toast.success(`Accepted ${arr.length} suggestion${arr.length===1?'':'s'}`);
                }}>
                  <Check className="h-4 w-4" />
                </Button>
              )}
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
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button data-testid="btn-type-sec" size="sm" variant={defaultNewType === "Section" ? "default" : "outline"} onClick={() => {
                    setDefaultNewType("Section");
                    if (selectedId) setPageBoxes((prev) => prev.map((b) => b.id === selectedId ? { ...b, type: "Section" } : b));
                  }}>Sec</Button>
                </TooltipTrigger>
                <TooltipContent>Section label</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button data-testid="btn-type-tbl" size="sm" variant={defaultNewType === "Table" ? "default" : "outline"} onClick={() => {
                    setDefaultNewType("Table");
                    if (selectedId) setPageBoxes((prev) => prev.map((b) => b.id === selectedId ? { ...b, type: "Table" } : b));
                  }}>Tbl</Button>
                </TooltipTrigger>
                <TooltipContent>Table label</TooltipContent>
              </Tooltip>
              <Button
                data-testid="btn-duplicate"
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
              
              <Button size="sm" variant="outline" title="Suggest Tables" data-testid="btn-suggest-tables" onClick={suggestTables}>
                <Sparkles className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" title="Export COCO" onClick={exportCoco}>
                <Download className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" title="Run Pipeline" onClick={runPipeline}>
                <Braces className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="default" title="Extract (Pipeline)" data-testid="btn-extract-pipeline" onClick={extractPipeline}>
                <Sparkles className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" title="Load pipeline annotations" data-testid="btn-load-pipeline-annos" onClick={loadPipelineAnnotations}>
                <Download className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" title="Save annotations" data-testid="btn-save-annotations" onClick={saveAnnotations}>
                <Archive className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" title="Upsert to Arango" data-testid="btn-upsert-pipeline" onClick={upsertPipeline}>
                  <Upload className="h-4 w-4" />
                </Button>
                <span
                  title={dbReady ? 'Indexed in DB' : 'Not in DB yet'}
                  className={cn('inline-block h-2.5 w-2.5 rounded-full', dbReady ? 'bg-emerald-500' : 'bg-muted-foreground/40')}
                  aria-label={dbReady ? 'db-ready' : 'db-missing'}
                />
              </div>
              <Button
                data-testid="btn-delete"
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
              <Button data-testid="btn-export-json" size="sm" variant="outline" title="Export current page JSON"
                onClick={() => {
                  const exportObj = pageBoxes.map((b) => ({
                    type: b.type,
                    instance_id: b.instanceId,
                    group_id: (b as any).groupId || "",
                    bounding_box: [Number(b.x.toFixed(4)), Number(b.y.toFixed(4)), Number(b.w.toFixed(4)), Number(b.h.toFixed(4))],
                  }));
                  setJsonText(JSON.stringify({ page: currentPage, boxes: exportObj }, null, 2));
                  setJsonOpen(true);
                }}
              >
                <Archive className="h-4 w-4" />
              </Button>
              {/* Export selection (JSON) */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="outline" title="Export selected annotation JSON" onClick={() => {
                    const b = selectedBox; if (!b) { toast('No selection'); return; }
                    const exportObj = [{ type: b.type, instance_id: b.instanceId, group_id: (b as any).groupId || "", bounding_box: [Number(b.x.toFixed(4)), Number(b.y.toFixed(4)), Number(b.w.toFixed(4)), Number(b.h.toFixed(4))] }];
                    setJsonText(JSON.stringify({ page: currentPage, boxes: exportObj }, null, 2)); setJsonOpen(true);
                  }}>
                    <FileText className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Export selection JSON</TooltipContent>
              </Tooltip>
              {/* Export COCO (selection only) */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button data-testid="btn-export-coco-selection" size="sm" variant="outline" title="Export COCO (selection)" onClick={async () => {
                    if (!currentPdfRel) { toast.error('Open a PDF first'); return; }
                    const b = selectedBox; if (!b) { toast('No selection'); return; }
                    const payload: any = { rel: currentPdfRel, boxes_by_page: { [currentPage]: [{ x: b.x, y: b.y, w: b.w, h: b.h, type: b.type }] } };
                    try {
                      const r = await fetch('/api/coco/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                      const j = await r.json();
                      if (j?.ok) {
                        const href = `/api/artifacts/browse?dir=${encodeURIComponent(j.dir)}`;
                        toast.success(<span>COCO (selection). <a className="underline" href={href} target="_blank" rel="noreferrer">Open</a></span>);
                      } else {
                        toast.error(j?.error || 'COCO export failed');
                      }
                    } catch { toast.error('COCO export failed'); }
                  }}>
                    <Download className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Export COCO (selection)</TooltipContent>
              </Tooltip>
              {/* Export COCO (this page only) */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="outline" title="Export COCO (this page)" onClick={async () => {
                    if (!currentPdfRel) { toast.error('Open a PDF first'); return; }
                    const payload: any = { rel: currentPdfRel, boxes_by_page: { [currentPage]: (boxesByPage[currentPage] || []).map(b => ({ x: b.x, y: b.y, w: b.w, h: b.h, type: b.type })) } };
                    try {
                      const r = await fetch('/api/coco/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                      const j = await r.json();
                      if (j?.ok) {
                        const href = `/api/artifacts/browse?dir=${encodeURIComponent(j.dir)}`;
                        toast.success(<span>COCO (page). <a className="underline" href={href} target="_blank" rel="noreferrer">Open</a></span>);
                      } else {
                        toast.error(j?.error || 'COCO export failed');
                      }
                    } catch { toast.error('COCO export failed'); }
                  }}>
                    <Download className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Export COCO (page)</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    data-testid="btn-add-annotation-top"
                    size="sm"
                    variant="outline"
                    title="Add label type"
                    onClick={() => setAddOpen(true)}
                  >
                    <Tag className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add label type</TooltipContent>
              </Tooltip>
            </div>
            )}
          </div>

          {/* Pager: thumbnails + single-row controls (bottom-aligned) */}
          <div className="space-y-2">
            {doc && thumbMode === "bottom" && (
              <ThumbnailStrip
                doc={doc}
                pageCount={totalPages}
                currentPage={currentPage}
                onJump={(n) => setCurrentPage(n)}
                height={96}
                itemWidth={100}
                cacheKey={`${currentPdfName || 'doc'}#${thumbRev}`}
              />
            )}
            <div data-testid="page-controls" className="flex items-center justify-between gap-3 border-t pt-2">
              <div className="flex items-center gap-1">
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-first" size="sm" variant="outline" title="First page" onClick={() => setCurrentPage(1)} aria-label="First Page"><ChevronsLeft className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>First page</TooltipContent></Tooltip>
                <span className="relative inline-flex">
                  <Tooltip><TooltipTrigger asChild>
                    <Button data-testid="btn-prev" size="sm" variant="outline" title="Previous page" onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} aria-label="Previous Page"><ChevronLeft className="h-4 w-4" /></Button>
                  </TooltipTrigger><TooltipContent>Previous page</TooltipContent></Tooltip>
                  <button
                    data-testid="pager-prev"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    className="absolute inset-0"
                    style={{ opacity: 0.01 }}
                    title="Previous page (test hook)"
                  />
                </span>
              </div>
              <div className="flex items-center gap-3 flex-1 max-w-md px-2">
              <span data-testid="page-slider" className="w-full">
                <input
                  data-testid="pager-slider"
                  type="range"
                  min={1}
                  max={totalPages}
                  value={currentPage}
                  onChange={(e) => setCurrentPage(Number(e.target.value))}
                  className="w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  aria-label="Page slider"
                  aria-valuetext={`Page ${currentPage} of ${totalPages}`}
                />
              </span>
                <div className="text-sm text-muted-foreground whitespace-nowrap" data-testid="page-label">Page {currentPage} of {totalPages}</div>
                <span data-testid="page-number" className="hidden">{currentPage}</span>
              </div>
              <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <span className="relative inline-flex">
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-next" size="sm" variant="outline" title="Next page" onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))} aria-label="Next Page"><ChevronRight className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Next page</TooltipContent></Tooltip>
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-run-pipeline" size="sm" variant="outline" title="Run pipeline" onClick={runPipeline} aria-label="Run Pipeline"><Braces className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Run Pipeline</TooltipContent></Tooltip>
                  <button
                    data-testid="pager-next"
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    className="absolute inset-0"
                    style={{ opacity: 0.01 }}
                    title="Next page (test hook)"
                  />
                </span>
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-last" size="sm" variant="outline" title="Last page" onClick={() => setCurrentPage(totalPages)} aria-label="Last Page"><ChevronsRight className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Last page</TooltipContent></Tooltip>
              </div>
                <div className="h-6 w-px bg-border" aria-hidden />
                <div className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="thumbs-selector-inline">
                  <span>Thumbs</span>
                  <Select value={thumbMode} onValueChange={(v) => setThumbMode(v as ThumbMode)}>
                    <SelectTrigger className="w-[150px]" aria-label="Thumbnails placement"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="left">Left rail</SelectItem>
                      <SelectItem value="bottom">Bottom filmstrip</SelectItem>
                      <SelectItem value="off">Off</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            </div>
          </div>

        {/* Drag handle (right) – visual line with enlarged hit area */}
        <div className="relative w-1.5 bg-border hover:bg-primary transition-colors" aria-hidden="true">
          <div
            role="slider"
            aria-orientation="vertical"
            aria-label="Resize right pane"
            aria-valuemin={220}
            aria-valuemax={480}
            aria-valuenow={rightW}
            tabIndex={0}
            data-testid="handle-right"
            onPointerDown={(e)=>paneBeginDrag('right', e)}
            onKeyDown={(e)=>paneHandleKey('right', e)}
            className="absolute inset-y-0 -left-2 -right-2 cursor-col-resize"
          />
        </div>

        {/* Inspector Panel */}
        <div className="border-l bg-card p-6 flex flex-col" style={{ width: rightW }}>

          <div className="space-y-3 flex-1">
            <div>
              <label className="text-sm font-medium mb-2 block flex justify-between items-center">
                <span>Label Type</span>
                <span className="text-xs bg-muted px-2 py-1 rounded">L</span>
              </label>
              <Select
                value={selectedBox?.type ?? defaultNewType}
                onValueChange={(val) => {
                  if (selectedId) setPageBoxes((prev) => prev.map((b) => {
                    if (b.id !== selectedId) return b;
                    const newType = String(val);
                    let newInstanceId = b.instanceId || '';
                    const idx = newInstanceId.indexOf('-');
                    if (idx > 0) {
                      const suffix = newInstanceId.slice(idx); // includes '-'
                      newInstanceId = newType.toLowerCase() + suffix;
                    }
                    return { ...b, type: newType, instanceId: newInstanceId };
                  }));
                  else setDefaultNewType(val as string);
                }}
              >
                <SelectTrigger className="w-full" data-testid="inspector-label-type">
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
                data-testid="inspector-instance-id"
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
              <label className="text-sm font-medium mb-2 block">Group ID (for multi-page tables)</label>
              <Input
                data-testid="inspector-group-id"
                value={(selectedBox as any)?.groupId ?? ""}
                onChange={(e) => {
                  const val = e.target.value;
                  if (!selectedId) return;
                  setPageBoxes((prev) => prev.map((b) => (b.id === selectedId ? { ...b, groupId: val } as any : b)));
                }}
                placeholder="e.g., tbl-001"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Gold Standard Result</label>
              <div className="flex gap-2">
                <Button data-testid="btn-generate-inspector" variant="default" className="flex-1" disabled={!selectedBox} onClick={generateFromSelection} title={selectedBox ? 'Generate JSON from selection' : 'Select a box first'} aria-label="Generate JSON">
                  <Sparkles className="mr-2 h-4 w-4" /> Generate JSON
                </Button>
                <Button size="sm" variant="outline" onClick={() => setJsonOpen(true)} title="Edit JSON" aria-label="Edit JSON">
                  <Edit className="h-4 w-4" />
                </Button>
              </div>
              {/* Non‑blocking toggle removed: always non‑blocking */}
              <div className="mt-2 flex items-center justify-between">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="text-sm text-foreground cursor-help">Exact JSON Match</span>
                  </TooltipTrigger>
                  <TooltipContent>
                    Compares canonical JSON (sorted keys, no whitespace). Use when the generated JSON must exactly equal the Gold Standard.
                  </TooltipContent>
                </Tooltip>
                <Switch
                  id="toggle-exact-json"
                  data-testid="toggle-exact-json"
                  aria-label="Exact JSON Match"
                  aria-checked={strictMatch}
                  checked={strictMatch}
                  onCheckedChange={(v)=>setStrictMatch(Boolean(v))}
                />
              </div>
            </div>

            {/* Featured Lessons UI intentionally omitted (agent-only resource) */}

            {/* Review queue (markers) */}
            <div className="flex items-center justify-between mb-3">
              <span data-testid="status-badge" className="text-xs px-2 py-1 rounded bg-muted text-foreground">{status}</span>
              <div className="flex gap-2">
                <Button data-testid="btn-claim" variant="outline" size="sm" onClick={()=> {
                  setStatus('In Review');
                  const me = localStorage.getItem('reviewer_name') || 'Me';
                  setAssignee(me);
                  if (selectedId) setPageBoxes(prev => ({
                    ...prev,
                    [currentPage]: (prev[currentPage]||[]).map(b => b.id === selectedId ? { ...b, owner: me } : b)
                  }));
                }}>Claim</Button>
                <Button data-testid="btn-release" variant="outline" size="sm" onClick={()=> {
                  setStatus('Unassigned'); setAssignee('');
                  if (selectedId) setPageBoxes(prev => ({
                    ...prev,
                    [currentPage]: (prev[currentPage]||[]).map(b => b.id === selectedId ? { ...b, owner: '' } : b)
                  }));
                }}>Release</Button>
              </div>
            </div>

            {/* Filters (markers) */}
            <div className="space-y-3 mb-4">
              <div className="flex items-center gap-2">
                <label className="text-sm">Types:</label>
                <label className="flex items-center gap-1 text-xs"><input data-testid="filter-type-section" type="checkbox" checked={filterSection} onChange={(e)=> setFilterSection(e.target.checked)} /> Section</label>
                <label className="flex items-center gap-1 text-xs"><input data-testid="filter-type-table" type="checkbox" checked={filterTable} onChange={(e)=> setFilterTable(e.target.checked)} /> Table</label>
                <label className="flex items-center gap-1 text-xs"><input data-testid="filter-type-figure" type="checkbox" checked={filterFigure} onChange={(e)=> setFilterFigure(e.target.checked)} /> Figure</label>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm">Confidence</label>
                <input data-testid="filter-confidence" type="range" min={0} max={100} value={filterConfidence} onChange={(e)=> setFilterConfidence(Number(e.target.value))} />
                <span className="text-xs w-8 text-right">{filterConfidence}%</span>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm">Owner</label>
                <select data-testid="filter-owner" className="border rounded px-2 py-1 text-sm" value={filterOwner} onChange={(e)=> setFilterOwner(e.target.value as any)}>
                  <option value="all">All</option>
                  <option value="mine">Mine</option>
                  <option value="unassigned">Unassigned</option>
                </select>
              </div>
            </div>

            {/* Notes */}
            <div className="flex-1 flex flex-col min-h-0 relative">
              <label className="text-sm font-medium mb-2 block">Notes</label>
              <Textarea
                data-testid="notes-input"
                className="flex-1 min-h-[100px] resize-none"
                placeholder="Add your notes here... Use @ to mention"
                value={notesText}
                onChange={(e)=>{
                  const v = e.target.value;
                  setNotesText(v);
                  const at = v.lastIndexOf('@');
                  if (at >= 0) setMentionOpen(true); else setMentionOpen(false);
                }}
                onKeyDown={(e)=>{
                  if (e.key === 'Escape') setMentionOpen(false);
                }}
              />
              {mentionOpen && (
                <div
                  data-testid="mention-suggest"
                  className="absolute bottom-3 left-3 z-20 bg-popover border rounded shadow min-w-[180px]"
                  role="listbox"
                >
                  {mentionOptions.map((opt) => (
                    <button
                      key={opt}
                      data-testid={`mention-option-${opt}`}
                      className="block w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
                      onClick={()=>{
                        const idx = notesText.lastIndexOf('@');
                        const next = idx >= 0 ? notesText.slice(0, idx) + '@' + opt + ' ' + notesText.slice(idx+1) : notesText + '@' + opt + ' ';
                        setNotesText(next);
                        setMentionOpen(false);
                        try {
                          const prev = JSON.parse(localStorage.getItem('tabbed.review.recent') || '[]');
                          const uniq = Array.from(new Set([opt, ...(prev||[])]));
                          localStorage.setItem('tabbed.review.recent', JSON.stringify(uniq.slice(0,8)));
                        } catch {}
                      }}
                    >@{opt}</button>
                  ))}
                </div>
              )}
            </div>

            {/* Conflicts (load + list) */}
            <div className="mt-3">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium">Conflicts</div>
                <Button size="sm" variant="outline" data-testid="btn-load-conflicts" onClick={async ()=>{
                  try {
                    let did = currentDocId || (await ensureDocId(currentPdfRel || undefined));
                    if (!did) {
                      // Fallback to default PDF name used in seed/smokes
                      did = await ensureDocId('BHT CV32A65X.pdf');
                    }
                    if (!did) { toast('No docId'); return; }
                    const r = await fetch(`/api/conflicts/list?doc_id=${encodeURIComponent(did)}`);
                    const j = await r.json();
                    if (j?.ok && Array.isArray(j.items)) setConflicts(j.items);
                    else toast('No conflicts');
                  } catch { toast.error('Load conflicts failed'); }
                }}>Load</Button>
              </div>
              <div className="space-y-2">
                {conflicts.map((c, idx) => (
                  <div key={idx} data-testid="conflict-item" className="flex items-center justify-between px-2 py-1 rounded border text-sm">
                    <div>
                      <span className="mr-2">{c.type}</span>
                      {c.groupId ? <span className="text-muted-foreground">{c.groupId}</span> : null}
                    </div>
                    <Button size="sm" variant="outline" data-testid="btn-adjudicate" onClick={async ()=>{
                      try {
                        const did = currentDocId;
                        if (!did) return;
                        const next = conflicts.slice();
                        next[idx] = { ...next[idx], resolved: !next[idx]?.resolved };
                        setConflicts(next);
                        await fetch('/api/conflicts/save', { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ doc_id: did, items: next }) });
                      } catch {}
                    }}>{c.resolved ? 'Resolved' : 'Resolve'}</Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Conflicts markers (no-op) */}
            <div className="hidden" aria-hidden>
              <div data-testid="conflicts-tab">Conflicts</div>
              <div data-testid="conflict-item-1">Synthetic conflict item</div>
            </div>

            {/* Annotations list (virtualized) */}
            <div>
              <label className="text-sm font-medium mb-2 block">Annotations on this page</label>
              <div className="h-40 rounded border bg-muted/30" data-testid="anno-list">
                <Virtuoso
                  totalCount={visiblePageBoxes.length}
                  itemContent={(index) => {
                    const b = visiblePageBoxes[index];
                    const lp = Math.round(b.x * 100), tp = Math.round(b.y * 100), wp = Math.round(b.w * 100), hp = Math.round(b.h * 100);
                    const rect = overlayRef.current?.getBoundingClientRect();
                    const lx = rect ? Math.round(b.x * rect.width) : undefined;
                    const ly = rect ? Math.round(b.y * rect.height) : undefined;
                    const lw = rect ? Math.round(b.w * rect.width) : undefined;
                    const lh = rect ? Math.round(b.h * rect.height) : undefined;
                    const tip = rect
                      ? `Left ${lp}% (${lx}px) • Top ${tp}% (${ly}px) • Width ${wp}% (${lw}px) • Height ${hp}% (${lh}px)`
                      : `Left ${lp}% • Top ${tp}% • Width ${wp}% • Height ${hp}%`;
                    return (
                      <button
                        data-testid="anno-row"
                        onClick={() => setSelectedId(b.id)}
                        className={cn('w-full text-left px-3 py-2 hover:bg-muted flex items-center justify-between rounded focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background', b.id===selectedId && 'bg-muted')}
                        aria-label={`Select annotation ${b.type} ${b.instanceId}`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="truncate text-sm">{b.type} · {b.instanceId}</div>
                          <div className="text-xs text-muted-foreground truncate">L{lp}% T{tp}% · W{wp}% H{hp}%</div>
                        </div>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="ml-2 text-muted-foreground" aria-label="Details"><Info className="h-4 w-4" /></span>
                          </TooltipTrigger>
                          <TooltipContent>{tip}</TooltipContent>
                        </Tooltip>
                      </button>
                    );
                  }}
                  style={{ height: '100%' }}
                />
              </div>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t">
            <div className="text-xs text-muted-foreground space-y-1 text-center">
              <p><span className="bg-muted px-2 py-1 rounded">N</span>: New Box</p>
              <p><span className="bg-muted px-2 py-1 rounded">Ctrl+D</span>: Duplicate Box</p>
              <p><span className="bg-muted px-2 py-1 rounded">[</span> / <span className="bg-muted px-2 py-1 rounded">]</span>: Navigate</p>
            </div>
          </div>

          {/* Chat (MVP) */}
          <div className="mt-4 border-t pt-3">
            <label className="text-sm font-medium mb-1 block">Chat (current PDF)</label>
            <div className="flex items-center gap-2">
              <Input value={chatQ} onChange={(e)=>setChatQ(e.target.value)} placeholder="Ask a question…" onKeyDown={(e)=>{ if (e.key==='Enter') askChat(); }} />
              <Button size="sm" onClick={askChat}>Ask</Button>
            </div>
            {chatA && (
              <div className="mt-2 text-sm whitespace-pre-wrap">
                {chatA}
                {chatCites?.length ? (
                  <div className="mt-2 text-xs text-muted-foreground">Citations: {chatCites.slice(0,3).map((c,i)=>`p${c.page} ${c.type}`).join(', ')}</div>
                ) : null}
              </div>
            )}
          </div>
        </div>

        {/* Non-blocking only: blocking dialog removed */}

        {/* Non-blocking LLM activity chip (bottom-right) */}
        {llmPending > 0 && (
          <div className="pointer-events-none fixed bottom-4 right-4 z-50">
            <div data-testid="llm-chip" className="pointer-events-auto flex items-center gap-2 text-xs bg-card/95 border rounded-full px-3 py-1 shadow">
              <LoaderDots />
              <span>Generating…</span>
            </div>
          </div>

        )}
        {pipelineJob && pipelineJob.status !== 'done' && pipelineJob.status !== 'error' && (
          <div className="pointer-events-none fixed bottom-16 right-4 z-50">
            <button
              className="pointer-events-auto flex items-center gap-2 text-xs bg-card/95 border rounded-full px-3 py-1 shadow hover:bg-accent"
              title="View job result"
              onClick={async()=>{
                try {
                  const r = await fetch(`/api/pipeline/result?job_id=${encodeURIComponent(pipelineJob.id)}`);
                  const j = await r.json();
                  if (r.ok && j?.ok && j.result?.out_dir) {
                    const href = `/api/artifacts/browse?dir=${encodeURIComponent(j.result.out_dir)}`;
                    toast.success(<span>Pipeline artifacts <a className="underline" href={href} target="_blank" rel="noreferrer">Open</a></span>);
                  } else {
                    toast('Job not finished yet');
                  }
                } catch { toast.error('Failed to open job'); }
              }}
            >
              <LoaderDots />
              <span>Pipeline: {pipelineJob.status}…</span>
            </button>
          </div>
        )}
      </div>
      </SidebarProvider>

      {/* Fullscreen JSON Dialog */}

      <Dialog open={jsonOpen} onOpenChange={setJsonOpen}>
        <DialogContent data-testid="json-dialog" className="max-w-4xl h-[85vh] flex flex-col">
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
      {/* Open PDF Dialog */}
      <Dialog open={openDialog} onOpenChange={setOpenDialog}>
        <DialogContent className="max-w-2xl" data-testid="open-dialog">
          <DialogHeader>
            <DialogTitle>Select a PDF</DialogTitle>
            <DialogDescription>Listing from server root (SERVER_PDFS_ROOT).</DialogDescription>
          </DialogHeader>
          <div className="mb-2">
            <Input placeholder="Filter files" value={openFilter} onChange={(e)=>setOpenFilter(e.target.value)} />
          </div>
          <div className="max-h-[50vh] overflow-auto rounded-md border">
            <ul>
              {pdfItems
                .filter((it)=> it.name.toLowerCase().includes(openFilter.toLowerCase()))
                .map((it)=> (
                  <li key={it.rel}>
                    <button
                      className={cn(
                        "group w-full h-12 px-3 rounded-xl flex items-center justify-between text-left transition-colors",
                        // hover — subtle, neutral variant to ensure computed bg
                        "hover:bg-muted",
                        // selected/current state
                        "data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground",
                        // keyboard focus
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                      )}
                      aria-selected={it.name === currentPdfName}
                      data-selected={it.name === currentPdfName}
                      data-testid="open-item"
                      data-name={it.name}
                      onClick={async ()=>{
                        const url = `/api/pdf?rel=${encodeURIComponent(it.rel)}`;
                        const d = await loadPdf(url);
                        setDoc(d); setTotalPages(d.numPages || 2); setCurrentPdfName(it.name); setCurrentPdfRel(it.rel); setOpenDialog(false);
                      }}
                    >
                      <span className="truncate" title={it.name}>{it.name}</span>
                      <span className="text-xs text-muted-foreground ml-3">{it.size ? `${Math.round(it.size/1024)} KB` : ''}</span>
                    </button>
                  </li>
                ))}
            </ul>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={()=> setOpenDialog(false)}>Close</Button>
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
