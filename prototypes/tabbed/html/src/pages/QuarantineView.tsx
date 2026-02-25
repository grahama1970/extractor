/**
 * QuarantineView — Filtered list of FAIL/WARN PDFs with quality scores.
 *
 * Sortable by severity, domain, score. Click opens ReviewLayout in edit mode.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle, ArrowUpDown, Ban, CheckCircle2,
  Filter, Loader2, RefreshCw, RotateCcw, Search, Trash2, XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { toast } from "@/components/ui/sonner";
import {
  fetchRuns, fetchScores, bulkAction,
  type RunSummary, type RunScores,
} from "@/lib/review";
import { applyCorrections } from "@/lib/datalake";
import { usePersona } from "@/contexts/PersonaContext";

// --- Verdict styling ---

const VERDICT_STYLES: Record<string, { bg: string; border: string; text: string; icon: typeof AlertTriangle }> = {
  FAIL: { bg: "bg-destructive/10", border: "border-destructive/30", text: "text-destructive", icon: XCircle },
  WARN: { bg: "bg-yellow-500/10", border: "border-yellow-500/30", text: "text-yellow-600", icon: AlertTriangle },
  PASS: { bg: "bg-green-500/10", border: "border-green-500/30", text: "text-green-600", icon: CheckCircle2 },
};

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return <Badge variant="outline" className="text-[10px]">N/A</Badge>;
  const style = VERDICT_STYLES[verdict] ?? VERDICT_STYLES.WARN;
  return (
    <Badge variant="outline" className={`text-[10px] ${style.text} ${style.border}`}>
      {verdict}
    </Badge>
  );
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground text-xs">—</span>;
  const pct = Math.round(score * 100);
  const color = score >= 0.88 ? "text-green-600" : score >= 0.65 ? "text-yellow-600" : "text-destructive";
  return <span className={`font-mono text-xs font-semibold ${color}`}>{pct}%</span>;
}

function GradeBadge({ grade }: { grade: string | null }) {
  if (!grade) return null;
  const color = grade.startsWith("A") ? "bg-green-500" : grade === "B" ? "bg-yellow-500" : grade === "C" ? "bg-orange-500" : "bg-destructive";
  return (
    <span className={`inline-block px-1.5 py-0 rounded text-[10px] font-bold text-white ${color}`}>
      {grade}
    </span>
  );
}

// --- Dimension bars ---

const DIM_LABELS: Record<string, string> = {
  content_coverage: "Content",
  section_alignment: "Sections",
  table_fidelity: "Tables",
  figure_fidelity: "Figures",
  equation_fidelity: "Equations",
  ordering_yx: "Ordering",
  data_quality: "Data Quality",
};

function DimensionBars({ scores }: { scores: RunScores | null }) {
  if (!scores) return null;
  return (
    <div className="grid grid-cols-7 gap-1 mt-1">
      {Object.entries(scores.dimensions).map(([key, dim]) => {
        const pct = Math.round(dim.score * 100);
        const color = dim.state === "pass" ? "bg-green-500" :
          dim.state === "warn" ? "bg-yellow-500" :
          dim.state === "not_available" ? "bg-gray-300" : "bg-destructive";
        return (
          <div key={key} className="text-center" title={`${DIM_LABELS[key] ?? key}: ${pct}% (${dim.state})`}>
            <div className="h-1.5 rounded-full bg-muted overflow-hidden">
              <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[8px] text-muted-foreground">{DIM_LABELS[key]?.slice(0, 4) ?? key.slice(0, 4)}</span>
          </div>
        );
      })}
    </div>
  );
}

// --- TV Quarantine — giant verdict counts, nothing else ---

function TvQuarantine({ verdictCounts, total }: { verdictCounts: Record<string, number>; total: number }) {
  const failCount = verdictCounts.FAIL ?? 0;
  const warnCount = verdictCounts.WARN ?? 0;
  const passCount = verdictCounts.PASS ?? 0;

  return (
    <div className="h-full flex flex-col items-center justify-center gap-10 p-8">
      <p className="text-2xl text-muted-foreground font-medium tracking-wide uppercase">Quarantine</p>

      <div className="flex items-center gap-12">
        {/* FAIL — giant red */}
        <div className="text-center">
          <XCircle className="h-12 w-12 text-red-500 mx-auto mb-2" />
          <p className="text-8xl font-black text-red-500 tabular-nums">{failCount}</p>
          <p className="text-xl text-red-400 font-semibold mt-1">FAIL</p>
        </div>

        <div className="w-px h-32 bg-border" />

        {/* WARN — giant yellow */}
        <div className="text-center">
          <AlertTriangle className="h-12 w-12 text-yellow-500 mx-auto mb-2" />
          <p className="text-8xl font-black text-yellow-500 tabular-nums">{warnCount}</p>
          <p className="text-xl text-yellow-400 font-semibold mt-1">WARN</p>
        </div>

        <div className="w-px h-32 bg-border" />

        {/* PASS — giant green */}
        <div className="text-center">
          <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-2" />
          <p className="text-8xl font-black text-green-500 tabular-nums">{passCount}</p>
          <p className="text-xl text-green-400 font-semibold mt-1">PASS</p>
        </div>
      </div>

      <p className="text-lg text-muted-foreground">
        {total} total runs · {failCount + warnCount} quarantined
      </p>
    </div>
  );
}

// --- Main component ---

type SortKey = "score" | "verdict" | "stem" | "domain";

export default function QuarantineView() {
  const navigate = useNavigate();
  const { distance } = usePersona();
  const isTv = distance === "tv";
  const isPhone = distance === "phone";
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [verdictFilter, setVerdictFilter] = useState<string[]>(["FAIL", "WARN"]);
  const [sortBy, setSortBy] = useState<SortKey>("score");
  const [sortDesc, setSortDesc] = useState(false);
  const [expandedScores, setExpandedScores] = useState<Record<string, RunScores>>({});
  const [loadingScores, setLoadingScores] = useState<Set<string>>(new Set());
  const [selectedStems, setSelectedStems] = useState<Set<string>>(new Set());

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchRuns({
        limit: 500,
        verdict: verdictFilter.length > 0 ? verdictFilter : undefined,
        sort_by: sortBy,
        sort_desc: sortDesc,
      });
      setRuns(data.runs);
      setTotal(data.total);
    } catch {
      toast.error("Failed to load quarantined runs");
    } finally {
      setLoading(false);
    }
  }, [verdictFilter, sortBy, sortDesc]);

  useEffect(() => { loadRuns(); }, [loadRuns]);

  const filtered = useMemo(() => {
    if (!search) return runs;
    const q = search.toLowerCase();
    return runs.filter((r) =>
      r.stem.toLowerCase().includes(q) ||
      (r.profile_domain ?? "").toLowerCase().includes(q),
    );
  }, [runs, search]);

  const handleExpandScores = useCallback(async (stem: string) => {
    if (expandedScores[stem]) {
      setExpandedScores((prev) => {
        const next = { ...prev };
        delete next[stem];
        return next;
      });
      return;
    }
    setLoadingScores((prev) => new Set(prev).add(stem));
    try {
      const scores = await fetchScores(stem);
      setExpandedScores((prev) => ({ ...prev, [stem]: scores }));
    } catch {
      toast.error(`No scores for ${stem}`);
    } finally {
      setLoadingScores((prev) => {
        const next = new Set(prev);
        next.delete(stem);
        return next;
      });
    }
  }, [expandedScores]);

  const toggleSelect = useCallback((stem: string) => {
    setSelectedStems((prev) => {
      const next = new Set(prev);
      if (next.has(stem)) next.delete(stem);
      else next.add(stem);
      return next;
    });
  }, []);

  const toggleVerdictFilter = useCallback((v: string) => {
    setVerdictFilter((prev) =>
      prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v],
    );
  }, []);

  const handleSort = useCallback((key: SortKey) => {
    if (sortBy === key) setSortDesc((d) => !d);
    else { setSortBy(key); setSortDesc(key === "score"); }
  }, [sortBy]);

  // Counts by verdict
  const verdictCounts = useMemo(() => {
    const counts: Record<string, number> = { FAIL: 0, WARN: 0, PASS: 0 };
    for (const r of runs) {
      if (r.verdict) counts[r.verdict] = (counts[r.verdict] ?? 0) + 1;
    }
    return counts;
  }, [runs]);

  // TV: war room — giant verdict counts only
  if (isTv) return <TvQuarantine verdictCounts={verdictCounts} total={total} />;

  return (
    <div className="bg-background">
      <div className="max-w-6xl mx-auto p-4 space-y-4">
        {/* Inline header */}
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold">Quarantine Review</h2>
          <div className="flex-1" />
          <span className="text-xs text-muted-foreground">{total} runs</span>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={loadRuns} aria-label="Refresh">
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-3">
          {(["FAIL", "WARN", "PASS"] as const).map((v) => {
            const style = VERDICT_STYLES[v];
            const Icon = style.icon;
            const active = verdictFilter.includes(v);
            return (
              <button
                key={v}
                onClick={() => toggleVerdictFilter(v)}
                className={`p-3 rounded-lg border text-left transition-all ${style.bg} ${style.border} ${
                  active ? "ring-2 ring-offset-1" : "opacity-60"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Icon className={`h-4 w-4 ${style.text}`} />
                  <span className={`text-2xl font-bold ${style.text}`}>{verdictCounts[v]}</span>
                </div>
                <span className="text-xs text-muted-foreground">{v} verdicts</span>
              </button>
            );
          })}
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search by name or domain..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>
          <div className="flex items-center gap-1">
            <Filter className="h-3.5 w-3.5 text-muted-foreground" />
            {(["score", "verdict", "stem", "domain"] as const).map((key) => (
              <Button
                key={key}
                variant={sortBy === key ? "secondary" : "ghost"}
                size="sm"
                className="h-7 text-[10px] gap-1"
                onClick={() => handleSort(key)}
              >
                {key}
                {sortBy === key && <ArrowUpDown className="h-3 w-3" />}
              </Button>
            ))}
          </div>
          {selectedStems.size > 0 && (
            <>
              <Separator orientation="vertical" className="h-5" />
              <Badge variant="outline" className="text-[10px]">{selectedStems.size} selected</Badge>
            </>
          )}
        </div>

        {/* Bulk action bar */}
        {selectedStems.size > 0 && (
          <Card className={`p-3 flex items-center gap-3 border-primary/30 bg-primary/5 ${isPhone ? "flex-wrap" : ""}`}>
            <span className="text-xs font-semibold">{selectedStems.size} selected</span>
            <Separator orientation="vertical" className="h-5" />
            <Button
              variant="outline" size="sm" className="h-7 text-[10px] gap-1"
              onClick={async () => {
                try {
                  await bulkAction({ stems: [...selectedStems], action: "reextract", reason: "Re-extraction from quarantine UI" });
                  toast.success(`Re-extraction requested for ${selectedStems.size} PDFs`);
                  setSelectedStems(new Set());
                } catch { toast.error("Failed to request re-extraction"); }
              }}
            >
              <RotateCcw className="h-3 w-3" />
              Re-extract
            </Button>
            <Button
              variant="outline" size="sm" className="h-7 text-[10px] gap-1 border-destructive/30 text-destructive hover:bg-destructive/10"
              onClick={async () => {
                try {
                  await bulkAction({ stems: [...selectedStems], action: "blacklist", reason: "Blacklisted from quarantine UI" });
                  toast.success(`${selectedStems.size} PDFs blacklisted`);
                  setSelectedStems(new Set());
                  loadRuns();
                } catch { toast.error("Failed to blacklist"); }
              }}
            >
              <Ban className="h-3 w-3" />
              Blacklist
            </Button>
            <Button
              variant="ghost" size="sm" className="h-7 text-[10px] gap-1"
              onClick={async () => {
                try {
                  await bulkAction({ stems: [...selectedStems], action: "dismiss", reason: "Dismissed from quarantine UI" });
                  toast.success(`${selectedStems.size} PDFs dismissed`);
                  setSelectedStems(new Set());
                } catch { toast.error("Failed to dismiss"); }
              }}
            >
              <Trash2 className="h-3 w-3" />
              Dismiss
            </Button>
            <div className="flex-1" />
            <Button
              variant="ghost" size="sm" className="h-7 text-[10px]"
              onClick={() => setSelectedStems(new Set())}
            >
              Clear selection
            </Button>
            <Button
              variant="ghost" size="sm" className="h-7 text-[10px]"
              onClick={() => setSelectedStems(new Set(filtered.map((r) => r.stem)))}
            >
              Select all
            </Button>
          </Card>
        )}

        {/* Run list */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        <div className="space-y-2">
          {filtered.map((run) => {
            const scores = expandedScores[run.stem];
            const isLoadingScores = loadingScores.has(run.stem);
            const isSelected = selectedStems.has(run.stem);

            return (
              <Card
                key={run.stem}
                className={`p-3 transition-all ${isSelected ? "ring-2 ring-primary" : ""}`}
              >
                <div className="flex items-start gap-3">
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleSelect(run.stem)}
                    className="mt-1 rounded"
                  />

                  {/* Main info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => navigate(`/review?stem=${run.stem}&edit=true`)}
                        className="font-medium text-sm truncate hover:underline text-left"
                      >
                        {run.stem}
                      </button>
                      <VerdictBadge verdict={run.verdict} />
                      <GradeBadge grade={run.grade} />
                      <ScoreBadge score={run.overall_score} />
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 text-[10px] text-muted-foreground">
                      {run.page_count != null && <span>{run.page_count}p</span>}
                      {run.profile_domain && <Badge variant="outline" className="text-[9px] px-1 py-0">{run.profile_domain}</Badge>}
                      {run.has_tables && <span>Tables</span>}
                      {run.has_figures && <span>Figures</span>}
                      {run.is_blacklisted && <Badge variant="destructive" className="text-[9px] px-1 py-0">Blacklisted</Badge>}
                    </div>

                    {/* Expanded dimension bars */}
                    {scores && <DimensionBars scores={scores} />}

                    {/* Issues */}
                    {scores && scores.issues.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {scores.issues.map((issue, i) => (
                          <div key={i} className="flex items-start gap-1.5 text-[10px]">
                            <Badge
                              variant="outline"
                              className={`text-[8px] px-1 py-0 flex-shrink-0 ${
                                issue.severity === "CRITICAL" ? "border-destructive text-destructive" :
                                issue.severity === "HIGH" ? "border-orange-500 text-orange-600" :
                                "border-yellow-500 text-yellow-600"
                              }`}
                            >
                              {issue.severity}
                            </Badge>
                            <span className="text-muted-foreground">{issue.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <Button
                      variant="ghost" size="sm" className="h-7 text-[10px]"
                      onClick={() => handleExpandScores(run.stem)}
                      disabled={isLoadingScores}
                    >
                      {isLoadingScores ? <Loader2 className="h-3 w-3 animate-spin" /> : scores ? "Hide" : "Scores"}
                    </Button>
                    <Button
                      variant="outline" size="sm" className="h-7 text-[10px]"
                      onClick={() => navigate(`/review?stem=${run.stem}`)}
                    >
                      View
                    </Button>
                    <Button
                      size="sm" className="h-7 text-[10px]"
                      onClick={() => navigate(`/review?stem=${run.stem}&edit=true`)}
                    >
                      Edit
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>

        {!loading && filtered.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-green-500" />
            <p className="text-sm">No quarantined PDFs match your filters</p>
          </div>
        )}
      </div>
    </div>
  );
}
