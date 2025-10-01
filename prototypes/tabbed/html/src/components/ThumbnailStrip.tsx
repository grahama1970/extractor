import React from "react";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import type { PdfDoc } from "@/lib/pdf";
import { renderPageThumbnail } from "@/lib/pdf";
import { cn } from "@/lib/utils";

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

export function ThumbnailStrip({
  doc,
  pageCount,
  currentPage,
  onJump,
  height = 132,
  itemWidth = 120,
  cacheKey,
  hitCounts,
}: {
  doc: PdfDoc;
  pageCount: number;
  currentPage: number; // 1-based
  onJump: (n: number) => void;
  height?: number;
  itemWidth?: number;
  cacheKey?: string;
  hitCounts?: Record<number, number>;
}) {
  const ref = React.useRef<VirtuosoHandle>(null);

  React.useEffect(() => {
    ref.current?.scrollToIndex({ index: currentPage - 1, align: "center", behavior: "smooth" });
  }, [currentPage]);

  // For small docs, render a simple row so multiple thumbs are visible without scrolling
  if (pageCount <= 4) {
    return (
      <div className="w-full border rounded-md bg-muted/30 overflow-x-auto" style={{ height }}>
        <div className="h-full flex items-stretch gap-2 px-2">
          {Array.from({ length: pageCount }).map((_, idx) => (
            <ThumbItem
              key={idx}
              doc={doc}
              n={idx + 1}
              isActive={idx + 1 === currentPage}
              onJump={onJump}
              width={itemWidth}
              cacheKey={cacheKey}
              hitCount={hitCounts?.[idx+1] || 0}
            />
          ))}
        </div>
      </div>
    );
  }

  // Ensure the strip is tall enough for 3:4 thumbs at the given width plus a small padding for ring/padding
  const minHeight = Math.round(itemWidth * 4 / 3) + 16;
  const effectiveHeight = Math.max(height, minHeight);
  return (
    <div className="w-full border rounded-md bg-muted/30 overflow-hidden" style={{ height: effectiveHeight }}>
      <Virtuoso
        ref={ref}
        totalCount={pageCount}
        overscan={10}
        horizontal
        itemContent={(index) => (
          <ThumbItem
            key={index}
            doc={doc}
            n={index + 1}
            isActive={index + 1 === currentPage}
            onJump={onJump}
            width={itemWidth}
            cacheKey={cacheKey}
            hitCount={hitCounts?.[index+1] || 0}
          />
        )}
        computeItemKey={(i) => `ph-${i + 1}`}
        style={{ height: "100%" }}
      />
    </div>
  );
}

function ThumbItem({ doc, n, isActive, onJump, width, cacheKey, hitCount }: { doc: PdfDoc; n: number; isActive: boolean; onJump: (n: number) => void; width: number; cacheKey?: string; hitCount?: number; }) {
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
      if (cancelled || !s) { if (attempt < 5) { setTimeout(() => load(attempt+1), 300); } return; }
      // Avoid caching non-PNG outputs (placeholders) — retry instead
      if (!s.startsWith('data:image/png')) {
        if (attempt < 5) { setTimeout(() => load(attempt+1), 300); return; }
        // last resort, still show but don't cache to allow future refreshes
        setSrc(s); return;
      }
      setCache(s);
    };
    load(0);
    return () => { cancelled = true; };
  }, [doc, n, width, cacheKey]);

  return (
    <button
      onClick={() => onJump(n)}
      className={cn(
        "px-2 py-2 h-full inline-flex items-center",
        isActive && "bg-primary/10"
      )}
      aria-current={isActive ? "page" : undefined}
      style={{ width: width + 16 }}
    >
      <div className={cn("relative w-full h-full rounded-md overflow-hidden shadow-sm ring-1", isActive ? "ring-primary" : "ring-border", "bg-white p-1 box-border")}
           style={{ aspectRatio: "3 / 4" }}>
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
      <span className="ml-2 text-xs text-muted-foreground">P.{n}</span>
    </button>
  );
}
