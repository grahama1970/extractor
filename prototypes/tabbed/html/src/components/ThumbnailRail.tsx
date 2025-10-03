import React from "react";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PdfDoc } from "@/lib/pdf";
import { renderPageThumbnail } from "@/lib/pdf";

const memCache = new Map<string, string>();
const MAX_CACHE = 500;
function lruSet(key: string, val: string) {
  if (memCache.has(key)) memCache.delete(key);
  memCache.set(key, val);
  if (memCache.size > MAX_CACHE) {
    const first = memCache.keys().next().value as string | undefined;
    if (first) memCache.delete(first);
  }
}

export function ThumbnailRail({
  doc,
  pageCount,
  currentPage,
  onJump,
  width = 144,
  cacheKey,
  hitCounts,
}: {
  doc: PdfDoc;
  pageCount: number;
  currentPage: number; // 1-based
  onJump: (n: number) => void;
  width?: number;
  cacheKey?: string;
  hitCounts?: Record<number, number>;
}) {
  const ref = React.useRef<VirtuosoHandle>(null);

  React.useEffect(() => {
    ref.current?.scrollToIndex({ index: currentPage - 1, align: "center", behavior: "smooth" });
  }, [currentPage]);

  return (
    <div
      data-testid="thumbs-left"
      className="shrink-0 border-r bg-muted/30 overflow-x-hidden overflow-y-auto min-h-0"
      style={{ width, transition: 'width 180ms ease' }}
    >
      <Virtuoso
        ref={ref}
        totalCount={pageCount}
        overscan={8}
        itemContent={(index) => (
          <ThumbItem
            key={index}
            doc={doc}
            n={index + 1}
            isActive={index + 1 === currentPage}
            onJump={onJump}
            width={width}
            cacheKey={cacheKey}
            hitCount={hitCounts?.[index+1] || 0}
          />
        )}
        computeItemKey={(i) => `p-${i + 1}`}
        style={{ height: "100%" }}
      />
    </div>
  );
}

function ThumbItem({
  doc,
  n,
  isActive,
  onJump,
  width,
  cacheKey,
  hitCount,
}: {
  doc: PdfDoc;
  n: number;
  isActive: boolean;
  onJump: (n: number) => void;
  width: number;
  cacheKey?: string;
  hitCount?: number;
}) {
  const [src, setSrc] = React.useState<string | undefined>(undefined);
  React.useEffect(() => {
    let cancelled = false;
    const key = `${cacheKey || 'doc'}:${n}@${width}`;
    const setCache = (val: string) => { lruSet(key, val); setSrc(val); };
    const load = async (attempt = 0) => {
      if (cancelled) return;
      const hit = memCache.get(key);
      if (hit) { setSrc(hit); return; }
      const s = await renderPageThumbnail(doc, n, width).catch(()=>undefined);
      if (cancelled || !s) {
        if (attempt < 5) { setTimeout(() => load(attempt+1), 300); }
        return;
      }
      // Treat non-PNG as placeholder and retry more aggressively
      if (!s.startsWith('data:image/png')) {
        if (attempt < 5) { setTimeout(() => load(attempt+1), 300); return; }
        setSrc(s); return; // last resort
      }
      setCache(s);
    };
    load(0);
    return () => {
      cancelled = true;
    };
  }, [doc, n, width, cacheKey]);

  return (
    <button
      data-testid={`thumb-${n}`}
      onClick={() => onJump(n)}
      className={cn(
        "group w-full px-2 py-2 text-left focus:outline-none relative",
        isActive && "bg-primary/10 before:absolute before:left-0 before:top-0 before:bottom-0 before:w-0.5 before:bg-primary"
      )}
      aria-current={isActive ? "page" : undefined}
      style={{
        // innerWidth accounts for horizontal padding inside the button (px-2 => 16px)
        height: Math.round(Math.max(1, (width - 16)) * 4 / 3) + 36,
      }}
    >
      <div
        className={cn(
          "relative w-full rounded-xl overflow-hidden shadow-sm ring-1 bg-white p-1",
          isActive ? "ring-primary" : "ring-border"
        )}
        style={{ aspectRatio: '3 / 4' }}
      >
        {src ? (
          <img src={src} alt={`Page ${n}`} className="w-full h-full object-contain" />
        ) : (
          <div className="w-full h-full animate-pulse bg-muted" />
        )}
        {!!hitCount && (
          <div data-testid="thumb-hit" className="absolute top-1 right-1 text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500 text-white shadow">
            {hitCount > 9 ? '9+' : hitCount}
          </div>
        )}
      </div>
      <div className="mt-2 text-xs text-muted-foreground flex items-center justify-between">
        <span>P.{n}</span>
      </div>
    </button>
  );
}
