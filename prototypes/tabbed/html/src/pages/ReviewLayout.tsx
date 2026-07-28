import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  CheckCircle2, AlertTriangle, Eye, EyeOff, Save, Search,
  Filter, Loader2, FileText, Table2, Image as ImageIcon,
  MessageSquare, ZoomIn, ZoomOut, Pencil, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/sonner";
import {
  fetchRuns, fetchAnnotations, fetchScores, fetchCorrections, pagePngUrl, saveCorrections,
  type Box, type RunSummary, type RunAnnotations, type AgentNote, type RunScores, type CorrectionEntry,
} from "@/lib/review";
import BboxEditor from "@/components/BboxEditor";
import { usePersona } from "@/contexts/PersonaContext";

// --- Color map (matches render_annotated_pdf.py) ---
const TYPE_COLORS: Record<string, string> = {
  SectionHeader: "rgba(242, 115, 26, 0.6)",
  Text: "rgba(100, 100, 100, 0.5)",
  Table: "rgba(26, 153, 242, 0.6)",
  Figure: "rgba(26, 204, 102, 0.6)",
  Equation: "rgba(153, 26, 242, 0.6)",
  ListItem: "rgba(230, 26, 102, 0.5)",
  Caption: "rgba(204, 128, 26, 0.5)",
  Footnote: "rgba(102, 102, 102, 0.4)",
};

const TYPE_STROKE: Record<string, string> = {
  SectionHeader: "#f2731a",
  Text: "#999",
  Table: "#1a99f2",
  Figure: "#1acc66",
  Equation: "#991af2",
  ListItem: "#e61a66",
  Caption: "#cc801a",
  Footnote: "#666",
};

function boxColor(type: string): string {
  return TYPE_COLORS[type] ?? "rgba(242, 26, 26, 0.4)";
}

function boxStroke(type: string): string {
  return TYPE_STROKE[type] ?? "#f21a1a";
}

// --- Run Browser (left panel) ---
function RunBrowser({
  onSelect,
  selectedStem,
}: {
  onSelect: (run: RunSummary) => void;
  selectedStem: string | null;
}) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showBlacklistedOnly, setShowBlacklistedOnly] = useState(false);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchRuns({
        limit: 200,
        blacklisted_only: showBlacklistedOnly,
      });
      setRuns(data.runs);
      setTotal(data.total);
    } catch (err) {
      toast.error("Failed to load runs");
    } finally {
      setLoading(false);
    }
  }, [showBlacklistedOnly]);

  useEffect(() => { loadRuns(); }, [loadRuns]);

  const filtered = useMemo(() => {
    if (!search) return runs;
    const q = search.toLowerCase();
    return runs.filter((r) => r.stem.toLowerCase().includes(q));
  }, [runs, search]);

  return (
    <aside className="w-72 flex-shrink-0 border-r bg-muted/30 flex flex-col h-full overflow-hidden">
      <div className="p-3 border-b space-y-2">
        <h2 className="text-sm font-semibold">Extraction Runs</h2>
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-3.5 w-3.5 text-muted-foreground" aria-hidden />
          <Input
            placeholder="Filter by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-8 text-xs"
            aria-label="Filter runs"
          />
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={showBlacklistedOnly}
            onChange={(e) => setShowBlacklistedOnly(e.target.checked)}
            className="rounded"
          />
          Failures only
        </label>
        <p className="text-xs text-muted-foreground">{total} runs total, {filtered.length} shown</p>
      </div>
      <div className="flex-1 overflow-y-auto" role="list" aria-label="Run list">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}
        {filtered.map((run) => (
          <button
            key={run.stem}
            role="listitem"
            onClick={() => onSelect(run)}
            className={`w-full text-left px-3 py-2 border-b text-xs hover:bg-accent/50 transition-colors ${
              selectedStem === run.stem ? "bg-accent border-l-2 border-l-primary" : ""
            }`}
            aria-current={selectedStem === run.stem ? "true" : undefined}
          >
            <div className="flex items-center gap-1.5">
              <span className="font-medium font-mono truncate flex-1">{run.stem}</span>
              {run.is_blacklisted && (
                <AlertTriangle className="h-3 w-3 text-destructive flex-shrink-0" aria-label="Blacklisted" />
              )}
            </div>
            <div className="flex items-center gap-2 mt-0.5 text-muted-foreground">
              {run.page_count != null && <span className="font-mono">{run.page_count}p</span>}
              {run.has_blocks && <FileText className="h-3 w-3" aria-label="Has blocks" />}
              {run.has_tables && <Table2 className="h-3 w-3" aria-label="Has tables" />}
              {run.has_figures && <ImageIcon className="h-3 w-3" aria-label="Has figures" />}
              {run.profile_domain && (
                <Badge variant="outline" className="text-[10px] px-1 py-0">{run.profile_domain}</Badge>
              )}
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
}

// --- Page Canvas with overlay boxes ---
function AnnotatedPage({
  stem,
  pageNum,
  boxes,
  zoom,
  selectedBoxId,
  onSelectBox,
  visibleTypes,
}: {
  stem: string;
  pageNum: number;
  boxes: Box[];
  zoom: number;
  selectedBoxId: string | null;
  onSelectBox: (id: string | null) => void;
  visibleTypes: Set<string>;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null);

  const src = pagePngUrl(stem, pageNum, Math.round(144 * zoom));

  const handleImgLoad = useCallback(() => {
    if (imgRef.current) {
      setImgSize({
        w: imgRef.current.naturalWidth,
        h: imgRef.current.naturalHeight,
      });
    }
  }, []);

  const filteredBoxes = useMemo(
    () => boxes.filter((b) => visibleTypes.has(b.type)),
    [boxes, visibleTypes],
  );

  return (
    <div ref={containerRef} className="relative inline-block">
      <img
        ref={imgRef}
        src={src}
        onLoad={handleImgLoad}
        alt={`Page ${pageNum}`}
        className="block bg-white shadow-md"
        draggable={false}
      />
      {imgSize && filteredBoxes.map((box) => {
        const left = box.x * imgSize.w;
        const top = box.y * imgSize.h;
        const width = box.w * imgSize.w;
        const height = box.h * imgSize.h;
        const isSelected = box.id === selectedBoxId;
        return (
          <button
            key={box.id}
            onClick={(e) => {
              e.stopPropagation();
              onSelectBox(isSelected ? null : box.id);
            }}
            className="absolute border-2 cursor-pointer transition-shadow"
            style={{
              left, top, width, height,
              backgroundColor: boxColor(box.type),
              borderColor: isSelected ? "#fff" : boxStroke(box.type),
              boxShadow: isSelected ? `0 0 0 2px ${boxStroke(box.type)}, 0 0 8px rgba(0,0,0,0.3)` : "none",
              zIndex: isSelected ? 10 : 1,
            }}
            aria-label={`${box.type} ${box.title ?? box.text_preview ?? box.id}`}
          >
            {(box.type !== "Text" || isSelected) && (
              <span
                className="absolute -top-4 right-0 text-[9px] font-semibold px-1 rounded-sm text-white whitespace-nowrap"
                style={{ backgroundColor: boxStroke(box.type) }}
              >
                {box.type}{box.stage ? ` (S${box.stage})` : ""}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// --- Severity styling ---
const SEVERITY_STYLES: Record<string, { bg: string; border: string; icon: typeof AlertTriangle }> = {
  error: { bg: "bg-destructive/10", border: "border-destructive/30", icon: AlertTriangle },
  warning: { bg: "bg-yellow-500/10", border: "border-yellow-500/30", icon: AlertTriangle },
  info: { bg: "bg-blue-500/10", border: "border-blue-500/30", icon: MessageSquare },
};

// --- Agent Notes panel ---
function AgentNotesPanel({ agentNotes }: { agentNotes: AgentNote[] }) {
  if (agentNotes.length === 0) return null;

  const errorCount = agentNotes.filter((n) => n.severity === "error").length;
  const warnCount = agentNotes.filter((n) => n.severity === "warning").length;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">Agent Notes</h3>
        {errorCount > 0 && (
          <Badge variant="destructive" className="text-[10px] px-1 py-0">{errorCount} error{errorCount !== 1 ? "s" : ""}</Badge>
        )}
        {warnCount > 0 && (
          <Badge variant="outline" className="text-[10px] px-1 py-0 border-amber-700 text-amber-700">{warnCount} warn</Badge>
        )}
      </div>
      <div className="space-y-1.5 max-h-60 overflow-y-auto" role="list" aria-label="Agent diagnostic notes">
        {agentNotes.map((note, i) => {
          const style = SEVERITY_STYLES[note.severity] ?? SEVERITY_STYLES.info;
          const Icon = style.icon;
          return (
            <div
              key={i}
              role="listitem"
              className={`p-2 rounded border text-[11px] ${style.bg} ${style.border}`}
            >
              <div className="flex items-start gap-1.5">
                <Icon className={`h-3 w-3 mt-0.5 flex-shrink-0 ${
                  note.severity === "error" ? "text-destructive" :
                  note.severity === "warning" ? "text-yellow-600" : "text-blue-500"
                }`} />
                <div className="min-w-0">
                  <span className="font-medium text-muted-foreground">{note.source}:</span>{" "}
                  <span>{note.message}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --- Correction History ---
function CorrectionHistory({ corrections }: { corrections: CorrectionEntry[] }) {
  if (corrections.length === 0) return null;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Correction History ({corrections.length})</h3>
      <div className="space-y-1.5 max-h-48 overflow-y-auto">
        {corrections.map((c, i) => {
          const ts = c.timestamp ? new Date(c.timestamp).toLocaleString() : "unknown";
          const action = c.action ?? "correction";
          const boxCount = c.boxes?.length ?? 0;
          return (
            <div key={i} className="p-2 rounded border bg-muted/30 text-[10px]">
              <div className="flex items-center gap-1.5">
                <Badge variant="outline" className="text-[8px] px-1 py-0">{action}</Badge>
                <span className="text-muted-foreground">{ts}</span>
              </div>
              {c.notes && <p className="mt-0.5 text-muted-foreground">{c.notes}</p>}
              {c.reason && <p className="mt-0.5 text-muted-foreground">{c.reason}</p>}
              {boxCount > 0 && <span className="text-muted-foreground">{boxCount} bbox(es) on p.{c.page ?? "?"}</span>}
              {c.reviewer && <span className="ml-1 text-muted-foreground">by {c.reviewer}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --- Inspector (right panel) ---
function Inspector({
  box,
  agentNotes,
  notes,
  onNotesChange,
  onSave,
  saving,
}: {
  box: Box | null;
  agentNotes: AgentNote[];
  notes: string;
  onNotesChange: (v: string) => void;
  onSave: () => void;
  saving: boolean;
}) {
  return (
    <aside className="w-72 flex-shrink-0 border-l bg-muted/30 p-3 space-y-3 overflow-y-auto">
      {/* Agent notes — always visible when a run is loaded */}
      <AgentNotesPanel agentNotes={agentNotes} />

      {agentNotes.length > 0 && box && <Separator />}

      {/* Box inspector */}
      {!box && agentNotes.length === 0 && (
        <p className="text-xs text-muted-foreground">Select an annotation to inspect</p>
      )}
      {!box && agentNotes.length > 0 && (
        <p className="text-xs text-muted-foreground mt-2">Select an annotation for details</p>
      )}
      {box && (
        <>
          <h3 className="text-sm font-semibold">Inspector</h3>
          <Separator />
          <dl className="space-y-1.5 text-xs">
            <div>
              <dt className="text-muted-foreground">Type</dt>
              <dd>
                <Badge style={{ backgroundColor: boxStroke(box.type), color: "#fff" }}>
                  {box.type}
                </Badge>
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">ID</dt>
              <dd className="font-mono truncate">{box.id}</dd>
            </div>
            {box.stage && (
              <div>
                <dt className="text-muted-foreground">Pipeline Stage</dt>
                <dd className="font-mono">S{box.stage}</dd>
              </div>
            )}
            {box.confidence != null && (
              <div>
                <dt className="text-muted-foreground">Confidence</dt>
                <dd className="font-mono">{(box.confidence * 100).toFixed(0)}%</dd>
              </div>
            )}
            {box.title && (
              <div>
                <dt className="text-muted-foreground">Title</dt>
                <dd>{box.title}</dd>
              </div>
            )}
            {box.text_preview && (
              <div>
                <dt className="text-muted-foreground">Text Preview</dt>
                <dd className="max-h-20 overflow-y-auto text-[11px] bg-background p-1 rounded">
                  {box.text_preview}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-muted-foreground">Position</dt>
              <dd className="font-mono text-[10px]">
                x={box.x.toFixed(3)} y={box.y.toFixed(3)} w={box.w.toFixed(3)} h={box.h.toFixed(3)}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Source</dt>
              <dd className="flex items-center gap-1">
                {box.source}
                {box.reviewed && <CheckCircle2 className="h-3 w-3 text-green-500" />}
              </dd>
            </div>
          </dl>
          <Separator />
          <div>
            <label htmlFor="inspector-notes" className="text-xs text-muted-foreground">
              Notes
            </label>
            <Textarea
              id="inspector-notes"
              value={notes}
              onChange={(e) => onNotesChange(e.target.value)}
              placeholder="Add review notes..."
              className="text-xs h-20 mt-1"
            />
          </div>
          <Button
            size="sm"
            onClick={onSave}
            disabled={saving}
            className="w-full"
            aria-label="Save corrections"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Save className="h-3.5 w-3.5 mr-1" />}
            Save Corrections
          </Button>
        </>
      )}
    </aside>
  );
}

// --- Scores Panel ---
function ScoresPanel({ scores }: { scores: RunScores | null }) {
  if (!scores) return null;
  const { overall, dimensions, issues } = scores;
  const gradeColor = overall.grade?.startsWith("A") ? "text-green-700" : overall.grade === "B" ? "text-amber-700" : "text-red-600";
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Quality Scores</h3>
      <div className="flex items-center gap-2">
        <span className={`text-lg font-bold ${gradeColor}`}>{overall.grade}</span>
        <span className="text-sm font-mono font-semibold">{Math.round(overall.score * 100)}%</span>
        <Badge variant={overall.verdict === "PASS" ? "outline" : "destructive"} className="text-[10px]">
          {overall.verdict}
        </Badge>
      </div>
      <div className="space-y-1">
        {Object.entries(dimensions).map(([key, dim]) => {
          const pct = Math.round(dim.score * 100);
          const color = dim.state === "pass" ? "bg-green-500" :
            dim.state === "warn" ? "bg-yellow-500" :
            dim.state === "not_available" ? "bg-gray-300" : "bg-destructive";
          return (
            <div key={key} className="text-[10px]">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{key.replace(/_/g, " ")}</span>
                <span className="font-mono">{pct}%</span>
              </div>
              <div className="h-1 rounded-full bg-muted overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      {issues.length > 0 && (
        <>
          <Separator />
          <h4 className="text-[10px] font-semibold text-muted-foreground">Issues ({issues.length})</h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {issues.map((issue, i) => (
              <div key={i} className="text-[10px] p-1 rounded bg-muted/50">
                <span className={`font-semibold ${
                  issue.severity === "CRITICAL" ? "text-destructive" :
                  issue.severity === "HIGH" ? "text-orange-600" : "text-yellow-600"
                }`}>{issue.severity}</span>
                {" "}<span className="text-muted-foreground">{issue.message}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// --- Main Layout ---
const ReviewLayout = () => {
  const [searchParams] = useSearchParams();
  const initialStem = searchParams.get("stem");
  const initialEdit = searchParams.get("edit") === "true";
  const { distance } = usePersona();
  const isTv = distance === "tv";
  const isPhone = distance === "phone";

  const [selectedRun, setSelectedRun] = useState<RunSummary | null>(null);
  const [annotations, setAnnotations] = useState<RunAnnotations | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [selectedBoxId, setSelectedBoxId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [editMode, setEditMode] = useState(initialEdit);
  const [scores, setScores] = useState<RunScores | null>(null);
  const [corrections, setCorrections] = useState<CorrectionEntry[]>([]);
  const [visibleTypes, setVisibleTypes] = useState<Set<string>>(
    new Set(["SectionHeader", "Table", "Figure", "Equation", "ListItem", "Caption", "Text"]),
  );

  const totalPages = annotations?.page_count ?? 0;
  const pageBoxes = useMemo(() => {
    if (!annotations) return [];
    return annotations.boxes_by_page[String(currentPage)] ?? [];
  }, [annotations, currentPage]);

  const selectedBox = useMemo(
    () => pageBoxes.find((b) => b.id === selectedBoxId) ?? null,
    [pageBoxes, selectedBoxId],
  );

  const handleSelectRun = useCallback(async (run: RunSummary) => {
    setSelectedRun(run);
    setLoading(true);
    setCurrentPage(1);
    setSelectedBoxId(null);
    setNotes("");
    setScores(null);
    setCorrections([]);
    try {
      const data = await fetchAnnotations(run.stem);
      setAnnotations(data);
      // Fetch scores and corrections in background
      fetchScores(run.stem).then(setScores).catch(() => {});
      fetchCorrections(run.stem).then((d) => setCorrections(d.corrections)).catch(() => {});
    } catch (err) {
      toast.error("Failed to load annotations");
      setAnnotations(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-select stem from URL query params
  useEffect(() => {
    if (initialStem) {
      handleSelectRun({ stem: initialStem } as RunSummary);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialStem]);

  const handleSave = useCallback(async () => {
    if (!selectedRun || !annotations) return;
    setSaving(true);
    try {
      await saveCorrections(
        selectedRun.stem,
        currentPage,
        pageBoxes,
        notes,
      );
      toast.success("Corrections saved");
      // Refresh correction history
      fetchCorrections(selectedRun.stem).then((d) => setCorrections(d.corrections)).catch(() => {});
    } catch (err) {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  }, [selectedRun, annotations, currentPage, pageBoxes, notes]);

  const toggleType = useCallback((type: string) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  const typeFilters = useMemo(() => {
    const counts = annotations?.type_counts ?? {};
    return Object.entries(counts).sort(([, a], [, b]) => b - a);
  }, [annotations]);

  return (
    <div className="flex flex-1 h-full bg-background text-foreground overflow-hidden">
      {/* Left: Run browser — hidden on TV and phone */}
      {!isTv && !isPhone && (
        <RunBrowser onSelect={handleSelectRun} selectedStem={selectedRun?.stem ?? null} />
      )}

      {/* Center: PDF canvas */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Toolbar */}
        <header className="flex items-center gap-2 px-3 py-2 border-b bg-card">
          <h1 className="text-sm font-semibold truncate flex-1">
            {selectedRun ? selectedRun.stem : "PDF Review"}
            {selectedRun?.is_blacklisted && (
              <Badge variant="destructive" className="ml-2 text-[10px]">BLACKLISTED</Badge>
            )}
          </h1>
          {/* Type filters */}
          {typeFilters.length > 0 && (
            <div className="flex items-center gap-1">
              <Filter className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              {typeFilters.map(([type, count]) => (
                <Tooltip key={type}>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => toggleType(type)}
                      className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] border transition-opacity ${
                        visibleTypes.has(type) ? "opacity-100" : "opacity-40"
                      }`}
                      style={{ borderColor: boxStroke(type) }}
                      aria-label={`Toggle ${type} (${count})`}
                      aria-pressed={visibleTypes.has(type)}
                    >
                      {visibleTypes.has(type) ? (
                        <Eye className="h-3 w-3" />
                      ) : (
                        <EyeOff className="h-3 w-3" />
                      )}
                      <span>{type}</span>
                      <span className="text-muted-foreground">{count}</span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>{visibleTypes.has(type) ? "Hide" : "Show"} {type} annotations</TooltipContent>
                </Tooltip>
              ))}
            </div>
          )}
          <Separator orientation="vertical" className="h-5" />
          {/* Edit mode toggle */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={editMode ? "default" : "ghost"}
                size="sm" className="h-7 text-[10px] gap-1"
                onClick={() => setEditMode((e) => !e)}
                aria-label="Toggle edit mode"
              >
                {editMode ? <X className="h-3 w-3" /> : <Pencil className="h-3 w-3" />}
                {editMode ? "Exit Edit" : "Edit"}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{editMode ? "Exit bbox editor" : "Edit bounding boxes"}</TooltipContent>
          </Tooltip>
          <Separator orientation="vertical" className="h-5" />
          {/* Zoom */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost" size="icon" className="h-7 w-7"
                onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
                aria-label="Zoom out"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Zoom out</TooltipContent>
          </Tooltip>
          <span className="text-xs text-muted-foreground w-10 text-center">{Math.round(zoom * 100)}%</span>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost" size="icon" className="h-7 w-7"
                onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
                aria-label="Zoom in"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Zoom in</TooltipContent>
          </Tooltip>
          <Separator orientation="vertical" className="h-5" />
          {/* Pager */}
          <nav className="flex items-center gap-1" aria-label="Page navigation">
            <Button
              variant="ghost" size="icon" className="h-7 w-7"
              onClick={() => setCurrentPage(1)} disabled={currentPage <= 1}
              aria-label="First page"
            >
              <ChevronsLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost" size="icon" className="h-7 w-7"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} disabled={currentPage <= 1}
              aria-label="Previous page"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <span className="text-xs min-w-[60px] text-center">
              {currentPage} / {totalPages}
            </span>
            <Button
              variant="ghost" size="icon" className="h-7 w-7"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))} disabled={currentPage >= totalPages}
              aria-label="Next page"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost" size="icon" className="h-7 w-7"
              onClick={() => setCurrentPage(totalPages)} disabled={currentPage >= totalPages}
              aria-label="Last page"
            >
              <ChevronsRight className="h-3.5 w-3.5" />
            </Button>
          </nav>
        </header>

        {/* Canvas area */}
        <div
          className="flex-1 overflow-auto bg-muted/50 flex items-start justify-center p-4"
          onClick={() => setSelectedBoxId(null)}
          role="region"
          aria-label="PDF canvas"
        >
          {loading && (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}
          {!loading && !selectedRun && (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
              <FileText className="h-12 w-12" />
              <p className="text-sm">Select a run from the sidebar to review</p>
            </div>
          )}
          {!loading && selectedRun && annotations && !editMode && (
            <AnnotatedPage
              stem={selectedRun.stem}
              pageNum={currentPage}
              boxes={pageBoxes}
              zoom={zoom}
              selectedBoxId={selectedBoxId}
              onSelectBox={setSelectedBoxId}
              visibleTypes={visibleTypes}
            />
          )}
          {!loading && selectedRun && annotations && editMode && (
            <div className="w-full p-2">
              <BboxEditor
                stem={selectedRun.stem}
                pageNum={currentPage}
                imgSrc={pagePngUrl(selectedRun.stem, currentPage, Math.round(144 * zoom))}
                existingBoxes={pageBoxes}
                onSave={async (anns) => {
                  const boxes: Box[] = anns
                    .filter((a) => a.action !== "delete")
                    .map((a) => ({
                      id: a.id, type: a.type, instanceId: "",
                      x: a.x, y: a.y, w: a.w, h: a.h,
                      source: a.action === "add" ? "manual" as const : "pipeline" as const,
                      reviewed: true, edited: a.action === "add",
                    }));
                  try {
                    await saveCorrections(selectedRun.stem, currentPage, boxes, notes);
                    toast.success("Corrections saved");
                    fetchCorrections(selectedRun.stem).then((d) => setCorrections(d.corrections)).catch(() => {});
                  } catch { toast.error("Failed to save"); }
                }}
              />
            </div>
          )}
        </div>

        {/* Bottom status bar */}
        <footer className="flex items-center gap-3 px-3 py-1.5 border-t bg-card text-xs text-muted-foreground">
          {annotations && (
            <>
              <span>{Object.values(annotations.type_counts).reduce((a, b) => a + b, 0)} annotations</span>
              <span>Page {currentPage}: {pageBoxes.length} boxes</span>
              {annotations.agent_notes.length > 0 && (
                <span className={annotations.agent_notes.some((n) => n.severity === "error") ? "text-destructive" : "text-yellow-600"}>
                  {annotations.agent_notes.length} agent note{annotations.agent_notes.length !== 1 ? "s" : ""}
                </span>
              )}
              {selectedBox && (
                <span className="text-foreground">
                  Selected: {selectedBox.type} — {selectedBox.id}
                </span>
              )}
            </>
          )}
        </footer>
      </main>

      {/* Right: Inspector + Agent Notes + Scores — hidden on TV and phone */}
      {!isTv && !isPhone && (
        <Inspector
          box={selectedBox}
          agentNotes={annotations?.agent_notes ?? []}
          notes={notes}
          onNotesChange={setNotes}
          onSave={handleSave}
          saving={saving}
        />
      )}
      {!isTv && !isPhone && (scores || corrections.length > 0) && (
        <aside className="w-60 flex-shrink-0 border-l bg-muted/30 p-3 overflow-y-auto space-y-3">
          <ScoresPanel scores={scores} />
          {scores && corrections.length > 0 && <Separator />}
          <CorrectionHistory corrections={corrections} />
        </aside>
      )}
    </div>
  );
};

export default ReviewLayout;
