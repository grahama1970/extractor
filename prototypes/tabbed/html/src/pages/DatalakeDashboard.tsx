/**
 * DatalakeDashboard — Visual representation of the datalake.
 *
 * Stats cards, quality histogram, domain table, convergence trend chart,
 * persona verdict cards.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Database, Loader2, RefreshCw, Send, Eye, RotateCcw, MessageSquare,
  CheckCircle2, AlertTriangle, XCircle, TrendingUp, ChevronDown, ChevronUp,
  Bot, Sparkles,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "@/components/ui/sonner";
import {
  fetchDatalakeStats, fetchVerdicts, fetchConvergence, fetchDimensionFailures,
  fetchQuarantine, fetchDocumentDetail, submitFeedback, fetchRecentFeedback,
  type DatalakeStats, type VerdictBreakdown, type ConvergenceData, type DimensionFailure,
  type QuarantineEntry, type DocumentDetail, type FeedbackEntry, type FeedbackAction,
} from "@/lib/datalake";
import { usePersona } from "@/contexts/PersonaContext";
import { topDimensions } from "@/lib/persona-config";
import { useAgentAnswer, type AnswerPayload, type AgentStatus } from "@/hooks/useAgentAnswer";
import AnswerCanvas from "@/components/AnswerCanvas";

// --- Stat Card ---

function StatCard({
  label, value, subtext, icon: Icon, color,
}: {
  label: string;
  value: string | number;
  subtext?: string;
  icon: typeof Database;
  color: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className={`text-2xl font-bold ${color}`}>{value}</p>
          {subtext && <p className="text-[10px] text-muted-foreground mt-0.5">{subtext}</p>}
        </div>
        <Icon className={`h-5 w-5 ${color} opacity-50`} />
      </div>
    </Card>
  );
}

// --- Score Histogram ---

function ScoreHistogram({ histogram }: { histogram: number[] }) {
  const max = Math.max(...histogram, 1);
  const labels = ["0-10", "10-20", "20-30", "30-40", "40-50", "50-60", "60-70", "70-80", "80-90", "90-100"];

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">Score Distribution</h3>
      <div className="flex items-end gap-1 h-32">
        {histogram.map((count, i) => {
          const height = (count / max) * 100;
          const color = i >= 8 ? "bg-green-500" : i >= 6 ? "bg-yellow-500" : i >= 4 ? "bg-orange-500" : "bg-destructive";
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-0.5" title={`${labels[i]}%: ${count} docs`}>
              <span className="text-[8px] text-muted-foreground">{count || ""}</span>
              <div className="w-full rounded-t" style={{ height: `${Math.max(height, 2)}%` }}>
                <div className={`w-full h-full rounded-t ${color}`} />
              </div>
              <span className="text-[7px] text-muted-foreground">{(i + 1) * 10}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// --- Domain Table ---

function DomainTable({ domains }: { domains: Record<string, number> }) {
  const sorted = Object.entries(domains).sort(([, a], [, b]) => b - a);
  const total = sorted.reduce((sum, [, c]) => sum + c, 0);

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-2">Domain Distribution</h3>
      <div className="space-y-1.5 max-h-48 overflow-y-auto">
        {sorted.map(([domain, count]) => {
          const pct = total > 0 ? (count / total) * 100 : 0;
          return (
            <div key={domain} className="flex items-center gap-2 text-xs">
              <span className="w-24 truncate font-medium">{domain}</span>
              <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                <div className="h-full rounded-full bg-primary/60" style={{ width: `${pct}%` }} />
              </div>
              <span className="text-muted-foreground w-8 text-right">{count}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// --- Grade Cards ---

function GradeCards({ grades }: { grades: Record<string, number> }) {
  const order = ["A+", "A", "B", "C", "F"];
  const colors: Record<string, string> = {
    "A+": "bg-green-500", "A": "bg-green-400", "B": "bg-yellow-500", "C": "bg-orange-500", "F": "bg-destructive",
  };

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-2">Grade Distribution</h3>
      <div className="flex items-end gap-2 h-24">
        {order.map((grade) => {
          const count = grades[grade] ?? 0;
          const total = Object.values(grades).reduce((a, b) => a + b, 0) || 1;
          const pct = (count / total) * 100;
          return (
            <div key={grade} className="flex-1 flex flex-col items-center gap-1">
              <span className="text-xs font-bold">{count}</span>
              <div className="w-full rounded-t overflow-hidden" style={{ height: `${Math.max(pct, 4)}%` }}>
                <div className={`w-full h-full rounded-t ${colors[grade] ?? "bg-gray-400"}`} />
              </div>
              <span className="text-[10px] font-semibold">{grade}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// --- Convergence Chart (simple SVG) ---

function ConvergenceChart({ entries }: { entries: ConvergenceData["entries"] }) {
  if (entries.length < 2) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-2">Convergence Trend</h3>
        <p className="text-xs text-muted-foreground">Not enough data points yet</p>
      </Card>
    );
  }

  const scores = entries
    .map((e) => e.overall_score ?? e.pass_count)
    .filter((s): s is number => s != null);

  if (scores.length < 2) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-2">Convergence Trend</h3>
        <p className="text-xs text-muted-foreground">No score data in convergence log</p>
      </Card>
    );
  }

  const w = 400, h = 120, pad = 20;
  const minS = Math.min(...scores) * 0.95;
  const maxS = Math.max(...scores) * 1.02;
  const range = maxS - minS || 1;

  const points = scores.map((s, i) => {
    const x = pad + (i / (scores.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((s - minS) / range) * (h - 2 * pad);
    return `${x},${y}`;
  });

  const latest = scores[scores.length - 1];
  const trend = scores.length >= 3 ?
    (scores[scores.length - 1] - scores[scores.length - 3]) > 0 ? "improving" : "stable/declining" :
    "unknown";

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold">Convergence Trend</h3>
        <div className="flex items-center gap-1 text-xs">
          <TrendingUp className="h-3 w-3" />
          <span className="text-muted-foreground">{trend}</span>
          <span className="font-mono font-semibold">{typeof latest === "number" ? (latest * 100).toFixed(1) + "%" : latest}</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 150 }}>
        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map((frac) => {
          const y = h - pad - frac * (h - 2 * pad);
          const label = (minS + frac * range).toFixed(2);
          return (
            <g key={frac}>
              <line x1={pad} y1={y} x2={w - pad} y2={y} stroke="#e5e7eb" strokeDasharray="4" />
              <text x={pad - 4} y={y + 3} fontSize="8" fill="#9ca3af" textAnchor="end">{label}</text>
            </g>
          );
        })}
        {/* Line */}
        <polyline
          fill="none"
          stroke="#3b82f6"
          strokeWidth="2"
          points={points.join(" ")}
        />
        {/* Points */}
        {points.map((p, i) => {
          const [x, y] = p.split(",").map(Number);
          return <circle key={i} cx={x} cy={y} r="2.5" fill="#3b82f6" />;
        })}
      </svg>
      <p className="text-[9px] text-muted-foreground mt-1">{scores.length} data points</p>
    </Card>
  );
}

// --- Verdict Cards (with dimension averages) ---

function VerdictCards({ verdicts }: { verdicts: VerdictBreakdown }) {
  const order: Array<{ key: string; icon: typeof CheckCircle2; color: string }> = [
    { key: "PASS", icon: CheckCircle2, color: "text-green-600" },
    { key: "WARN", icon: AlertTriangle, color: "text-yellow-600" },
    { key: "FAIL", icon: XCircle, color: "text-destructive" },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {order.map(({ key, icon: Icon, color }) => {
        const data = verdicts[key];
        if (!data) return null;
        return (
          <Card key={key} className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Icon className={`h-4 w-4 ${color}`} />
              <span className={`text-lg font-bold ${color}`}>{data.count}</span>
              <span className="text-xs text-muted-foreground">{key}</span>
            </div>
            {Object.keys(data.dimension_averages).length > 0 && (
              <div className="space-y-1">
                {Object.entries(data.dimension_averages)
                  .sort(([, a], [, b]) => a - b)
                  .map(([dim, avg]) => (
                    <div key={dim} className="flex items-center gap-1 text-[10px]">
                      <span className="w-20 truncate text-muted-foreground">{dim.replace(/_/g, " ")}</span>
                      <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full ${avg >= 0.8 ? "bg-green-500" : avg >= 0.6 ? "bg-yellow-500" : "bg-destructive"}`}
                          style={{ width: `${avg * 100}%` }}
                        />
                      </div>
                      <span className="font-mono w-8 text-right">{Math.round(avg * 100)}%</span>
                    </div>
                  ))}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

// --- Dimension Failures (remediation priority) ---

function DimensionFailures({ failures }: { failures: DimensionFailure[] }) {
  if (!failures.length) return null;
  const max = failures[0]?.fail_count || 1;

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-2">Remediation Priority</h3>
      <p className="text-[10px] text-muted-foreground mb-3">Dimensions causing FAIL verdicts (score &lt; 0.65)</p>
      <div className="space-y-2">
        {failures.map(({ dimension, fail_count }) => {
          const pct = (fail_count / max) * 100;
          return (
            <div key={dimension} className="flex items-center gap-2 text-xs">
              <span className="w-28 truncate font-medium">{dimension.replace(/_/g, " ")}</span>
              <div className="flex-1 h-3 rounded-full bg-muted overflow-hidden">
                <div className="h-full rounded-full bg-destructive/70" style={{ width: `${pct}%` }} />
              </div>
              <span className="text-muted-foreground w-10 text-right font-mono">{fail_count}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// --- Recent Trend Banner ---

function TrendBanner({ stats }: { stats: DatalakeStats }) {
  const recentPass = stats.recent_pass_rate_pct ?? 0;
  const overallPass = stats.pass_rate_pct ?? 0;
  const target = stats.target_pass_rate_pct ?? 95;
  const gap = target - recentPass;
  const improving = recentPass > overallPass;

  return (
    <Card className="p-3 border-l-4 border-l-primary">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-muted-foreground">Recent 100: </span>
            <span className={`font-bold ${recentPass >= 95 ? "text-green-600" : recentPass >= 80 ? "text-yellow-600" : "text-destructive"}`}>
              {recentPass}% PASS
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Overall: </span>
            <span className="font-semibold">{overallPass}% PASS</span>
          </div>
          <div>
            <span className="text-muted-foreground">Target: </span>
            <span className="font-semibold">{target}%</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {improving ? (
            <TrendingUp className="h-3.5 w-3.5 text-green-500" />
          ) : (
            <TrendingUp className="h-3.5 w-3.5 text-muted-foreground rotate-90" />
          )}
          <span className={gap <= 0 ? "text-green-600 font-bold" : "text-muted-foreground"}>
            {gap <= 0 ? "Target reached!" : `${gap.toFixed(1)}% to target`}
          </span>
        </div>
      </div>
    </Card>
  );
}

// --- Quarantine Review Panel (Nico Collaboration) ---

function QuarantineCard({
  entry,
  onFeedback,
  onAskEmbry,
}: {
  entry: QuarantineEntry;
  onFeedback: (stem: string, action: FeedbackAction, notes: string, dims?: string[]) => void;
  onAskEmbry?: (stem: string, dims: string[]) => void;
}) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");

  const handleExpand = async () => {
    if (expanded) { setExpanded(false); return; }
    setExpanded(true);
    if (!detail) {
      setLoadingDetail(true);
      try {
        const d = await fetchDocumentDetail(entry.pdf_stem);
        setDetail(d);
      } catch { /* ignore */ }
      setLoadingDetail(false);
    }
  };

  const failDims = entry.failing_dimensions ?? [];
  const worstDim = entry.worst_dimension ?? failDims[0]?.dim;
  const scoreColor = entry.overall_score >= 0.65 ? "text-yellow-600" : "text-destructive";

  return (
    <Card className="p-3">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <button onClick={handleExpand} className="font-medium text-sm truncate hover:underline text-left">
              {entry.pdf_stem}
            </button>
            <Badge variant="outline" className="text-[10px] border-destructive text-destructive">
              {entry.reconciled_decision || "FAIL"}
            </Badge>
            <span className={`font-mono text-xs font-semibold ${scoreColor}`}>
              {Math.round(entry.overall_score * 100)}%
            </span>
            <span className="text-[10px] text-muted-foreground">{entry.grade}</span>
          </div>

          {/* Worst dimension + failing dims summary */}
          <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
            {worstDim && (
              <span className="text-destructive font-medium">
                worst: {worstDim.replace(/_/g, " ")} ({entry.worst_score != null ? Math.round(entry.worst_score * 100) + "%" : "?"})
              </span>
            )}
            {failDims.length > 1 && (
              <span>+{failDims.length - 1} more failing</span>
            )}
            <span>M:{entry.margaret_verdict} J:{entry.jennifer_verdict}</span>
          </div>

          {/* Pipeline stage comparison (expanded) */}
          {expanded && (
            <div className="mt-3 space-y-2">
              {loadingDetail ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" /> Loading document detail...
                </div>
              ) : detail ? (
                <>
                  {/* Assessment dimensions */}
                  {detail.assessment && (
                    <div className="space-y-1">
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase">Dimension Scores</p>
                      <div className="grid grid-cols-4 gap-1">
                        {Object.entries((detail.assessment as any).dimensions ?? {}).map(([dim, data]: [string, any]) => {
                          const score = typeof data === "object" ? data.score : data;
                          const state = typeof data === "object" ? data.state : "unknown";
                          const pct = typeof score === "number" ? Math.round(score * 100) : null;
                          const color = state === "pass" ? "text-green-600" : state === "warn" ? "text-yellow-600" :
                            state === "not_available" ? "text-gray-400" : "text-destructive";
                          return (
                            <div key={dim} className="text-[10px]">
                              <span className="text-muted-foreground">{dim.replace(/_/g, " ")}: </span>
                              <span className={`font-mono font-semibold ${color}`}>{pct != null ? `${pct}%` : state}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Memory chunks count */}
                  <div className="flex items-center gap-4 text-[10px]">
                    <span>
                      <span className="text-muted-foreground">Content in /memory: </span>
                      <span className="font-semibold">{detail.content_chunks} chunks</span>
                    </span>
                    {detail.feedback.length > 0 && (
                      <span>
                        <span className="text-muted-foreground">Previous feedback: </span>
                        <span className="font-semibold">{detail.feedback.length} notes</span>
                      </span>
                    )}
                  </div>

                  {/* Previous feedback */}
                  {detail.feedback.length > 0 && (
                    <div className="space-y-1 border-l-2 border-primary/30 pl-2">
                      {detail.feedback.slice(0, 3).map((fb, i) => (
                        <div key={i} className="text-[10px]">
                          <span className="font-medium">{fb.reviewer}</span>
                          <span className="text-muted-foreground"> ({fb.action}): </span>
                          <span>{fb.notes}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Inline feedback form */}
                  <div className="flex items-center gap-2 mt-1">
                    <Input
                      placeholder="Add note for this PDF..."
                      value={feedbackText}
                      onChange={(e) => setFeedbackText(e.target.value)}
                      className="h-7 text-xs flex-1"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && feedbackText.trim()) {
                          onFeedback(entry.pdf_stem, "note", feedbackText, failDims.map(d => d.dim));
                          setFeedbackText("");
                        }
                      }}
                    />
                    <Button
                      variant="ghost" size="sm" className="h-7 text-[10px] gap-1"
                      onClick={() => {
                        if (feedbackText.trim()) {
                          onFeedback(entry.pdf_stem, "note", feedbackText, failDims.map(d => d.dim));
                          setFeedbackText("");
                        }
                      }}
                    >
                      <Send className="h-3 w-3" /> Note
                    </Button>
                    <Button
                      variant="outline" size="sm" className="h-7 text-[10px] gap-1"
                      onClick={() => onFeedback(entry.pdf_stem, "reextract", feedbackText || "Re-extract requested", failDims.map(d => d.dim))}
                    >
                      <RotateCcw className="h-3 w-3" /> Re-extract
                    </Button>
                    {onAskEmbry && (
                      <Button
                        variant="secondary" size="sm" className="h-7 text-[10px] gap-1"
                        onClick={() => onAskEmbry(entry.pdf_stem, failDims.map(d => d.dim))}
                      >
                        <Bot className="h-3 w-3" /> Ask Embry
                      </Button>
                    )}
                  </div>
                </>
              ) : (
                <p className="text-[10px] text-muted-foreground">No detail available</p>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={handleExpand}>
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </Button>
          <Button
            variant="outline" size="sm" className="h-7 text-[10px]"
            onClick={() => navigate(`/review?stem=${entry.pdf_stem}`)}
          >
            <Eye className="h-3 w-3 mr-1" /> View
          </Button>
        </div>
      </div>
    </Card>
  );
}

function QuarantineReviewPanel({
  quarantine,
  loading,
  onFeedback,
  onAskEmbry,
}: {
  quarantine: QuarantineEntry[];
  loading: boolean;
  onFeedback: (stem: string, action: FeedbackAction, notes: string, dims?: string[]) => void;
  onAskEmbry?: (stem: string, dims: string[]) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const display = showAll ? quarantine : quarantine.slice(0, 8);

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <XCircle className="h-4 w-4 text-destructive" />
          <h3 className="text-sm font-semibold">Quarantine Review</h3>
          <Badge variant="outline" className="text-[10px]">{quarantine.length} FAIL PDFs</Badge>
        </div>
        <Link to="/quarantine">
          <Button variant="ghost" size="sm" className="h-7 text-[10px]">Full View</Button>
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : quarantine.length === 0 ? (
        <div className="text-center py-6 text-muted-foreground text-xs">
          <CheckCircle2 className="h-6 w-6 mx-auto mb-1 text-green-500" />
          No quarantined PDFs
        </div>
      ) : (
        <div className="space-y-2">
          {display.map((entry) => (
            <QuarantineCard key={entry.pdf_stem} entry={entry} onFeedback={onFeedback} onAskEmbry={onAskEmbry} />
          ))}
          {quarantine.length > 8 && (
            <Button
              variant="ghost" size="sm" className="w-full text-xs"
              onClick={() => setShowAll(!showAll)}
            >
              {showAll ? "Show less" : `Show all ${quarantine.length} quarantined PDFs`}
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}

// --- Recent Feedback Activity ---

function FeedbackActivity({ feedback }: { feedback: FeedbackEntry[] }) {
  if (!feedback.length) return null;

  const actionColors: Record<string, string> = {
    note: "text-blue-500",
    reextract: "text-orange-500",
    escalate: "text-destructive",
    approve: "text-green-500",
    dismiss: "text-muted-foreground",
  };

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-3">
        <MessageSquare className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">Recent Feedback</h3>
      </div>
      <div className="space-y-2 max-h-48 overflow-y-auto">
        {feedback.map((fb, i) => (
          <div key={i} className="flex items-start gap-2 text-[10px]">
            <Badge variant="outline" className={`text-[8px] ${actionColors[fb.action] ?? ""}`}>
              {fb.action}
            </Badge>
            <div className="flex-1 min-w-0">
              <span className="font-medium">{fb.reviewer}</span>
              <span className="text-muted-foreground"> on </span>
              <span className="font-medium truncate">{fb.stem}</span>
              {fb.notes && <p className="text-muted-foreground mt-0.5">{fb.notes}</p>}
            </div>
            <span className="text-muted-foreground flex-shrink-0">
              {fb.timestamp ? new Date(fb.timestamp * 1000).toLocaleTimeString() : ""}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// --- Embry Chat (Nico→Embry conversation via /ask-stream) ---

type ChatMessage = {
  role: "user" | "embry";
  text: string;
  answer?: AnswerPayload;
  timestamp: number;
};

function EmbryChat({
  contextStem,
  contextDims,
}: {
  contextStem?: string;
  contextDims?: string[];
}) {
  const { answer, status, error, transcript, ask, clear } = useAgentAnswer("embry");
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevAnswerRef = useRef<AnswerPayload | null>(null);

  // Append Embry's answer to history when it arrives
  useEffect(() => {
    if (answer && answer !== prevAnswerRef.current) {
      prevAnswerRef.current = answer;
      setHistory((h) => [
        ...h,
        {
          role: "embry",
          text: answer.summary || answer.title || (answer.type === "text" ? answer.content : ""),
          answer,
          timestamp: Date.now(),
        },
      ]);
    }
  }, [answer]);

  // Auto-scroll on new messages
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [history, status]);

  const handleSend = useCallback((query: string) => {
    if (!query.trim()) return;
    setHistory((h) => [...h, { role: "user", text: query, timestamp: Date.now() }]);
    ask(query);
    setInput("");
  }, [ask]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  }, [input, handleSend]);

  // Pre-built contextual questions for quarantined PDFs
  const contextQuestions = useMemo(() => {
    if (!contextStem) return [];
    const stem = contextStem;
    const questions = [
      `What does /memory know about ${stem}?`,
      `Show me the extraction quality for ${stem} as a radar chart`,
      `Why did ${stem} fail? What dimensions are below threshold?`,
    ];
    if (contextDims?.length) {
      const worst = contextDims[0];
      questions.push(`Debug the ${worst.replace(/_/g, " ")} issue for ${stem}`);
    }
    questions.push(`/project-state`);
    return questions;
  }, [contextStem, contextDims]);

  const isThinking = status === "thinking" || status === "rendering";

  return (
    <Card className="p-4 flex flex-col" style={{ maxHeight: 480 }}>
      <div className="flex items-center gap-2 mb-3">
        <Bot className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">Ask Embry</h3>
        <Badge variant="outline" className="text-[10px]">
          {status === "idle" ? "ready" : status}
        </Badge>
        {contextStem && (
          <Badge variant="secondary" className="text-[10px] truncate max-w-32">
            {contextStem}
          </Badge>
        )}
        {history.length > 0 && (
          <Button variant="ghost" size="sm" className="h-5 text-[9px] ml-auto" onClick={() => { clear(); setHistory([]); }}>
            Clear
          </Button>
        )}
      </div>

      {/* Quick question chips */}
      {contextQuestions.length > 0 && history.length === 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {contextQuestions.map((q, i) => (
            <button
              key={i}
              className="text-[10px] px-2 py-0.5 rounded-full bg-muted hover:bg-muted-foreground/20 text-muted-foreground transition-colors truncate max-w-64"
              onClick={() => handleSend(q)}
              disabled={isThinking}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Conversation thread */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-2 min-h-0 mb-2" style={{ maxHeight: 300 }}>
        {history.map((msg, i) => (
          <div key={i} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-lg px-3 py-1.5 text-xs ${
              msg.role === "user"
                ? "bg-primary text-primary-foreground"
                : "bg-muted"
            }`}>
              {msg.role === "embry" && msg.answer?.type === "html" ? (
                <div>
                  {msg.answer.title && <p className="font-semibold text-[11px] mb-1">{msg.answer.title}</p>}
                  <iframe
                    srcDoc={msg.answer.content}
                    className="w-full border-0 rounded"
                    style={{ height: 200 }}
                    sandbox="allow-scripts allow-same-origin"
                    title={msg.answer.title || "Embry response"}
                  />
                  {msg.answer.summary && (
                    <p className="text-[10px] text-muted-foreground mt-1">{msg.answer.summary}</p>
                  )}
                </div>
              ) : msg.role === "embry" && msg.answer?.type === "table" ? (
                <div>
                  {msg.answer.title && <p className="font-semibold text-[11px] mb-1">{msg.answer.title}</p>}
                  <pre className="text-[9px] overflow-x-auto max-h-32 whitespace-pre-wrap">
                    {(() => {
                      try {
                        const rows = JSON.parse(msg.answer.content);
                        if (Array.isArray(rows) && rows.length > 0) {
                          const cols = Object.keys(rows[0]);
                          return cols.join(" | ") + "\n" + rows.slice(0, 10).map(
                            (r: Record<string, unknown>) => cols.map((c) => String(r[c] ?? "")).join(" | ")
                          ).join("\n");
                        }
                      } catch { /* */ }
                      return msg.answer!.content;
                    })()}
                  </pre>
                  {msg.answer.summary && (
                    <p className="text-[10px] text-muted-foreground mt-1">{msg.answer.summary}</p>
                  )}
                </div>
              ) : (
                <div>
                  {msg.role === "embry" && msg.answer?.title && (
                    <p className="font-semibold text-[11px] mb-0.5">{msg.answer.title}</p>
                  )}
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                  {msg.role === "embry" && msg.answer?.source && (
                    <p className="text-[9px] text-muted-foreground mt-0.5">{msg.answer.source}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        {isThinking && (
          <div className="flex gap-2 justify-start">
            <div className="bg-muted rounded-lg px-3 py-1.5 text-xs flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span className="text-muted-foreground">
                {status === "thinking" ? "Thinking..." : "Rendering..."}
              </span>
              {transcript && <span className="text-[9px] text-muted-foreground/60 truncate max-w-32">{transcript}</span>}
            </div>
          </div>
        )}
        {error && (
          <div className="text-[10px] text-destructive bg-destructive/10 rounded px-2 py-1">{error}</div>
        )}
      </div>

      {/* Input form */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <Input
          placeholder={contextStem ? `Ask Embry about ${contextStem}...` : "Ask Embry anything..."}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="h-7 text-xs flex-1"
          disabled={isThinking}
        />
        <Button type="submit" variant="default" size="sm" className="h-7 text-[10px] gap-1" disabled={isThinking || !input.trim()}>
          <Sparkles className="h-3 w-3" /> Ask
        </Button>
      </form>
    </Card>
  );
}

// --- TV War Room (10ft) — giant color-coded numbers, nothing else ---

function TvDashboard({ stats, verdicts }: { stats: DatalakeStats; verdicts: VerdictBreakdown | null }) {
  const passRate = stats.total_docs > 0 ? Math.round(((stats.verdicts.PASS ?? 0) / stats.total_docs) * 100) : 0;
  const failCount = stats.verdicts.FAIL ?? 0;
  const warnCount = stats.verdicts.WARN ?? 0;
  const scoreColor = stats.avg_score >= 0.88 ? "text-green-500" : stats.avg_score >= 0.65 ? "text-yellow-500" : "text-red-500";
  const passColor = passRate >= 95 ? "text-green-500" : passRate >= 80 ? "text-yellow-500" : "text-red-500";

  return (
    <div className="h-full flex flex-col items-center justify-center gap-8 p-8">
      {/* Row 1: Score + PASS rate — the two numbers that matter */}
      <div className="grid grid-cols-2 gap-12 w-full max-w-4xl">
        <div className="text-center">
          <p className="text-xl text-muted-foreground font-medium tracking-wide uppercase">Score</p>
          <p className={`text-8xl font-black tabular-nums ${scoreColor}`}>
            {Math.round(stats.avg_score * 100)}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-xl text-muted-foreground font-medium tracking-wide uppercase">PASS Rate</p>
          <p className={`text-8xl font-black tabular-nums ${passColor}`}>
            {passRate}%
          </p>
          <p className="text-lg text-muted-foreground mt-1">{stats.verdicts.PASS ?? 0} of {stats.total_docs}</p>
        </div>
      </div>

      {/* Row 2: Verdict traffic light — FAIL / WARN / PASS counts */}
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-3">
          <XCircle className="h-8 w-8 text-red-500" />
          <span className="text-5xl font-black text-red-500 tabular-nums">{failCount}</span>
          <span className="text-xl text-red-400 font-semibold">FAIL</span>
        </div>
        <div className="w-px h-12 bg-border" />
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-8 w-8 text-yellow-500" />
          <span className="text-5xl font-black text-yellow-500 tabular-nums">{warnCount}</span>
          <span className="text-xl text-yellow-400 font-semibold">WARN</span>
        </div>
        <div className="w-px h-12 bg-border" />
        <div className="flex items-center gap-3">
          <CheckCircle2 className="h-8 w-8 text-green-500" />
          <span className="text-5xl font-black text-green-500 tabular-nums">{stats.verdicts.PASS ?? 0}</span>
          <span className="text-xl text-green-400 font-semibold">PASS</span>
        </div>
      </div>

      {/* Row 3: Corpus size — subtle */}
      <p className="text-lg text-muted-foreground">
        {stats.total_docs.toLocaleString()} documents in corpus
      </p>
    </div>
  );
}

// --- Phone Dashboard — 2x2 grid ---

function PhoneDashboard({ stats, loadAll, loading }: { stats: DatalakeStats; loadAll: () => void; loading: boolean }) {
  return (
    <div className="p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Datalake Dashboard</h2>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={loadAll} aria-label="Refresh">
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <StatCard label="Documents" value={stats.total_docs} icon={Database} color="text-primary" />
        <StatCard
          label="Score"
          value={`${Math.round(stats.avg_score * 100)}%`}
          icon={TrendingUp}
          color={stats.avg_score >= 0.88 ? "text-green-600" : stats.avg_score >= 0.65 ? "text-yellow-600" : "text-destructive"}
        />
        <StatCard
          label="PASS"
          value={`${stats.total_docs > 0 ? Math.round(((stats.verdicts.PASS ?? 0) / stats.total_docs) * 100) : 0}%`}
          subtext={`${stats.verdicts.PASS ?? 0} of ${stats.total_docs}`}
          icon={CheckCircle2}
          color="text-green-600"
        />
        <StatCard
          label="Quarantined"
          value={(stats.verdicts.FAIL ?? 0) + (stats.verdicts.WARN ?? 0)}
          subtext={`${stats.verdicts.FAIL ?? 0} F, ${stats.verdicts.WARN ?? 0} W`}
          icon={AlertTriangle}
          color="text-yellow-600"
        />
      </div>
      <ScoreHistogram histogram={stats.score_histogram} />
      <GradeCards grades={stats.grades} />
    </div>
  );
}

// --- Main component ---

export default function DatalakeDashboard() {
  const { persona, distance } = usePersona();
  const top3 = topDimensions(persona);
  const [stats, setStats] = useState<DatalakeStats | null>(null);
  const [verdicts, setVerdicts] = useState<VerdictBreakdown | null>(null);
  const [convergence, setConvergence] = useState<ConvergenceData | null>(null);
  const [dimFailures, setDimFailures] = useState<DimensionFailure[]>([]);
  const [quarantine, setQuarantine] = useState<QuarantineEntry[]>([]);
  const [recentFeedback, setRecentFeedback] = useState<FeedbackEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [quarantineLoading, setQuarantineLoading] = useState(false);
  const [embryChatStem, setEmbryChatStem] = useState<string | undefined>();
  const [embryChatDims, setEmbryChatDims] = useState<string[] | undefined>();

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, v, c, df] = await Promise.all([
        fetchDatalakeStats(),
        fetchVerdicts(),
        fetchConvergence(),
        fetchDimensionFailures().catch(() => ({ failures: [] })),
      ]);
      setStats(s);
      setVerdicts(v);
      setConvergence(c);
      setDimFailures(df.failures);
    } catch {
      toast.error("Failed to load datalake data");
    } finally {
      setLoading(false);
    }
    // Load quarantine + feedback in parallel (non-blocking)
    setQuarantineLoading(true);
    Promise.all([
      fetchQuarantine(30, 0).catch(() => ({ quarantine: [], total_fail: 0, offset: 0, limit: 30 })),
      fetchRecentFeedback(20).catch(() => ({ feedback: [], total: 0 })),
    ]).then(([q, fb]) => {
      setQuarantine(q.quarantine);
      setRecentFeedback(fb.feedback);
    }).finally(() => setQuarantineLoading(false));
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleFeedback = useCallback(async (
    stem: string, action: FeedbackAction, notes: string, dims?: string[],
  ) => {
    try {
      const result = await submitFeedback({ stem, action, notes, dimensions: dims });
      if (result.stored) {
        toast.success(`${action === "reextract" ? "Re-extraction requested" : "Feedback saved"} for ${stem}`);
        // Refresh feedback list
        fetchRecentFeedback(20).then((fb) => setRecentFeedback(fb.feedback)).catch(() => {});
      } else {
        toast.error("Failed to store feedback");
      }
    } catch {
      toast.error("Failed to submit feedback");
    }
  }, []);

  const handleAskEmbry = useCallback((stem: string, dims: string[]) => {
    setEmbryChatStem(stem);
    setEmbryChatDims(dims);
  }, []);

  const isTv = distance === "tv";
  const isPhone = distance === "phone";
  const isDesk = distance === "desk";

  // Desk (5ft): voice-activated answer canvas — no dashboard
  if (isDesk) return <AnswerCanvas />;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!stats) return null;

  // TV: war room — giant numbers only
  if (isTv) return <TvDashboard stats={stats} verdicts={verdicts} />;

  // Phone: compact 2x2
  if (isPhone) return <PhoneDashboard stats={stats} loadAll={loadAll} loading={loading} />;

  // Full dashboard with Nico collaboration panel
  return (
    <div className="bg-background">
      <div className="flex items-center justify-between px-4 pt-3">
        <h2 className="text-sm font-semibold">Datalake Dashboard</h2>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={loadAll} aria-label="Refresh">
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="max-w-6xl mx-auto p-4 space-y-4">
        <TrendBanner stats={stats} />
        <div className="grid gap-3 grid-cols-4">
          <StatCard label="Total Documents" value={stats.total_docs} icon={Database} color="text-primary" />
          <StatCard
            label="Average Score"
            value={`${Math.round(stats.avg_score * 100)}%`}
            icon={TrendingUp}
            color={stats.avg_score >= 0.88 ? "text-green-600" : stats.avg_score >= 0.65 ? "text-yellow-600" : "text-destructive"}
          />
          <StatCard
            label="PASS Rate"
            value={`${stats.total_docs > 0 ? Math.round(((stats.verdicts.PASS ?? 0) / stats.total_docs) * 100) : 0}%`}
            subtext={`${stats.verdicts.PASS ?? 0} of ${stats.total_docs}`}
            icon={CheckCircle2}
            color="text-green-600"
          />
          <StatCard
            label="Quarantined"
            value={(stats.verdicts.FAIL ?? 0) + (stats.verdicts.WARN ?? 0)}
            subtext={`${stats.verdicts.FAIL ?? 0} FAIL, ${stats.verdicts.WARN ?? 0} WARN`}
            icon={AlertTriangle}
            color="text-yellow-600"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <ScoreHistogram histogram={stats.score_histogram} />
          <GradeCards grades={stats.grades} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          {convergence && <ConvergenceChart entries={convergence.entries} />}
          <DimensionFailures failures={dimFailures} />
        </div>

        <DomainTable domains={stats.domains} />

        {verdicts && (
          <>
            <Separator />
            <h2 className="text-sm font-semibold">
              Verdict Breakdown by Dimension
              <span className="ml-2 text-[10px] text-muted-foreground font-normal">
                (focus: {top3.map((d) => d.replace(/_/g, " ")).join(", ")})
              </span>
            </h2>
            <VerdictCards verdicts={verdicts} />
          </>
        )}

        {/* Nico Collaboration: Quarantine Review + Embry Chat + Feedback */}
        <Separator />
        <h2 className="text-sm font-semibold flex items-center gap-2">
          Human-Agent Collaboration
          <Badge variant="outline" className="text-[10px]">Nico</Badge>
          <span className="text-[10px] text-muted-foreground font-normal ml-1">
            Ask Embry questions — conversations are archived and gradeable by /review-conversation
          </span>
        </h2>

        {/* Row 1: Embry Chat (full width) */}
        <EmbryChat contextStem={embryChatStem} contextDims={embryChatDims} />

        {/* Row 2: Quarantine + Feedback */}
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <QuarantineReviewPanel
              quarantine={quarantine}
              loading={quarantineLoading}
              onFeedback={handleFeedback}
              onAskEmbry={handleAskEmbry}
            />
          </div>
          <FeedbackActivity feedback={recentFeedback} />
        </div>

        <Separator />
        <div className="flex items-center gap-3">
          <Link to="/quarantine">
            <Button variant="outline" size="sm" className="text-xs gap-1">
              <AlertTriangle className="h-3 w-3" />
              Full Quarantine
            </Button>
          </Link>
          <Link to="/search">
            <Button variant="outline" size="sm" className="text-xs gap-1">
              Cross-Doc Search
            </Button>
          </Link>
          <Link to="/ask">
            <Button variant="outline" size="sm" className="text-xs gap-1">
              Persona Query
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
