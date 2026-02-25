/**
 * CrossDocSearch — Search across all documents in the datalake.
 *
 * BM25 + semantic search via /memory, filterable by asset_type.
 * Results link back to ReviewLayout at the exact page.
 */
import React, { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText, Image as ImageIcon, Loader2,
  Search, Table2, Type,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { toast } from "@/components/ui/sonner";
import { searchDatalake, type SearchResult, type SearchResponse } from "@/lib/datalake";
import { usePersona } from "@/contexts/PersonaContext";
import { topDimensions, dimensionToAssetType } from "@/lib/persona-config";

// --- Asset type filter chips ---

const ASSET_TYPES = [
  { key: "all", label: "All", icon: Search },
  { key: "table", label: "Tables", icon: Table2 },
  { key: "text", label: "Text", icon: Type },
  { key: "figure", label: "Figures", icon: ImageIcon },
  { key: "section", label: "Sections", icon: FileText },
];

// --- Result card ---

function ResultCard({
  result,
  onNavigate,
}: {
  result: SearchResult;
  onNavigate: (stem: string, page?: number) => void;
}) {
  const meta = result.metadata ?? {};
  const stem = (meta.source_pdf as string) ?? (meta.pdf_hash as string) ?? "";
  const page = meta.page_num as number | undefined;
  const assetType = (meta.asset_type as string) ?? (result.tags?.find((t) =>
    ["table", "text", "figure", "section"].includes(t),
  )) ?? "text";
  const text = result.text ?? "";
  const truncated = text.length > 300 ? text.slice(0, 300) + "..." : text;

  return (
    <Card className="p-3 hover:bg-accent/30 transition-colors">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className="text-[9px] px-1 py-0">{assetType}</Badge>
            {stem && (
              <button
                onClick={() => onNavigate(stem, page)}
                className="text-xs font-medium text-primary hover:underline truncate"
              >
                {stem}
              </button>
            )}
            {page != null && (
              <span className="text-[10px] text-muted-foreground">p.{page}</span>
            )}
            {result.score != null && (
              <span className="text-[10px] text-muted-foreground font-mono">
                score: {typeof result.score === "number" ? result.score.toFixed(3) : result.score}
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed">{truncated}</p>
          {result.tags && result.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {result.tags.slice(0, 8).map((tag) => (
                <Badge key={tag} variant="secondary" className="text-[8px] px-1 py-0">{tag}</Badge>
              ))}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

// --- Main component ---

export default function CrossDocSearch() {
  const navigate = useNavigate();
  const { persona, distance } = usePersona();
  const isTv = distance === "tv";
  // Default asset_type from persona's top dimension
  const defaultAsset = dimensionToAssetType(topDimensions(persona, 1)[0]) ?? "all";
  const [query, setQuery] = useState("");
  const [assetType, setAssetType] = useState(defaultAsset);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    try {
      const data = await searchDatalake({
        query: q,
        asset_type: assetType === "all" ? undefined : assetType,
        k: 30,
      });
      setResults(data);
    } catch {
      toast.error("Search failed");
    } finally {
      setLoading(false);
    }
  }, [query, assetType]);

  const handleNavigate = useCallback((stem: string, page?: number) => {
    const params = new URLSearchParams({ stem });
    if (page != null) params.set("page", String(page));
    navigate(`/review?${params}`);
  }, [navigate]);

  // TV: centered large search with giant text
  if (isTv) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-6 p-8">
        <Search className="h-16 w-16 text-muted-foreground opacity-30" />
        <p className="text-2xl text-muted-foreground font-medium">Cross-Document Search</p>
        <div className="flex items-center gap-3 w-full max-w-3xl">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-4 h-6 w-6 text-muted-foreground" />
            <Input
              placeholder="Search all documents..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
              className="pl-14 h-14 text-xl"
            />
          </div>
          <Button onClick={handleSearch} disabled={loading || !query.trim()} className="h-14 px-8 text-lg">
            {loading ? <Loader2 className="h-6 w-6 animate-spin" /> : "Search"}
          </Button>
        </div>
        {/* Filter chips — large for 10ft */}
        <div className="flex items-center gap-3">
          {ASSET_TYPES.map(({ key, label, icon: Icon }) => (
            <Button
              key={key}
              variant={assetType === key ? "secondary" : "ghost"}
              className="h-12 text-base gap-2 px-5"
              onClick={() => setAssetType(key)}
            >
              <Icon className="h-5 w-5" />
              {label}
            </Button>
          ))}
        </div>
        {/* Results count */}
        {results && (
          <div className="w-full max-w-3xl">
            <p className="text-lg text-muted-foreground mb-4">
              {results.result_count} results for "{results.query}"
            </p>
            <div className="space-y-3">
              {results.results.slice(0, 10).map((r, i) => {
                const meta = r.metadata ?? {};
                const stem = (meta.source_pdf as string) ?? "";
                return (
                  <Card key={i} className="p-4 hover:bg-accent/30 transition-colors">
                    <button
                      onClick={() => { if (stem) handleNavigate(stem, meta.page_num as number | undefined); }}
                      className="text-left w-full"
                    >
                      <p className="text-base font-medium text-primary">{stem || "Unknown"}</p>
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                        {(r.text ?? "").slice(0, 200)}
                      </p>
                    </button>
                  </Card>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-background">
      <div className="max-w-4xl mx-auto p-4 space-y-4">
        {/* Search bar */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder='Search across all documents (e.g., "control surface deflection limits")'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
              className="pl-10 h-10"
            />
          </div>
          <Button onClick={handleSearch} disabled={loading || !query.trim()}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
          </Button>
        </div>

        {/* Asset type filter chips — horizontally scrollable on phone */}
        <div className="flex items-center gap-2 overflow-x-auto">
          <span className="text-xs text-muted-foreground flex-shrink-0">Filter:</span>
          {ASSET_TYPES.map(({ key, label, icon: Icon }) => (
            <Button
              key={key}
              variant={assetType === key ? "secondary" : "ghost"}
              size="sm"
              className="h-7 text-xs gap-1"
              onClick={() => setAssetType(key)}
            >
              <Icon className="h-3 w-3" />
              {label}
            </Button>
          ))}
        </div>

        {/* Results */}
        {results && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              {results.result_count} results for "{results.query}"
              {results.asset_type && ` (${results.asset_type})`}
            </p>
            {results.results.map((r, i) => (
              <ResultCard key={i} result={r} onNavigate={handleNavigate} />
            ))}
            {results.result_count === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No results found. Try different keywords or broaden the filter.</p>
              </div>
            )}
          </div>
        )}

        {!results && !loading && (
          <div className="text-center py-16 text-muted-foreground">
            <Search className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p className="text-sm">Search across tables, text, figures, and sections in the datalake</p>
            <p className="text-xs mt-1">Results link directly to the page in the PDF viewer</p>
          </div>
        )}
      </div>
    </div>
  );
}
