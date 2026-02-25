/**
 * DatalakeDashboard — Visual representation of the datalake.
 *
 * Stats cards, quality histogram, domain table, convergence trend chart,
 * persona verdict cards.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Database, Loader2, RefreshCw,
  CheckCircle2, AlertTriangle, XCircle, TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "@/components/ui/sonner";
import {
  fetchDatalakeStats, fetchVerdicts, fetchConvergence,
  type DatalakeStats, type VerdictBreakdown, type ConvergenceData,
} from "@/lib/datalake";
import { usePersona } from "@/contexts/PersonaContext";
import { topDimensions } from "@/lib/persona-config";
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
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, v, c] = await Promise.all([
        fetchDatalakeStats(),
        fetchVerdicts(),
        fetchConvergence(),
      ]);
      setStats(s);
      setVerdicts(v);
      setConvergence(c);
    } catch {
      toast.error("Failed to load datalake data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

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

  // Fallback: full dashboard (shouldn't reach here due to desk check above)
  return (
    <div className="bg-background">
      <div className="flex items-center justify-between px-4 pt-3">
        <h2 className="text-sm font-semibold">Datalake Dashboard</h2>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={loadAll} aria-label="Refresh">
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="max-w-6xl mx-auto p-4 space-y-4">
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
          <DomainTable domains={stats.domains} />
        </div>

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

        <Separator />
        <div className="flex items-center gap-3">
          <Link to="/quarantine">
            <Button variant="outline" size="sm" className="text-xs gap-1">
              <AlertTriangle className="h-3 w-3" />
              View Quarantine
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
