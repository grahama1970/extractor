import React from "react";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import type { PdfDoc } from "@/lib/pdf";
import { renderPageThumbnail } from "@/lib/pdf";
import { cn } from "@/lib/utils";

const memCache = new Map<string, string>();

export function ThumbnailStrip({
  doc,
  pageCount,
  currentPage,
  onJump,
  height = 132,
  itemWidth = 120,
}: {
  doc: PdfDoc;
  pageCount: number;
  currentPage: number; // 1-based
  onJump: (n: number) => void;
  height?: number;
  itemWidth?: number;
}) {
  const ref = React.useRef<VirtuosoHandle>(null);

  React.useEffect(() => {
    ref.current?.scrollToIndex({ index: currentPage - 1, align: "center", behavior: "smooth" });
  }, [currentPage]);

  return (
    <div className="w-full border rounded-md bg-muted/30 overflow-hidden" style={{ height }}>
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
          />
        )}
        computeItemKey={(i) => `ph-${i + 1}`}
        style={{ height: "100%" }}
      />
    </div>
  );
}

function ThumbItem({ doc, n, isActive, onJump, width }: { doc: PdfDoc; n: number; isActive: boolean; onJump: (n: number) => void; width: number; }) {
  const [src, setSrc] = React.useState<string | undefined>(undefined);
  React.useEffect(() => {
    let cancelled = false;
    const key = `${n}@${width}`;
    const hit = memCache.get(key);
    if (hit) setSrc(hit);
    else {
      renderPageThumbnail(doc, n, width).then((s) => {
        if (!cancelled && s) {
          memCache.set(key, s);
          setSrc(s);
        }
      });
    }
    return () => { cancelled = true; };
  }, [doc, n, width]);

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
      <div className={cn("w-full h-full rounded-md overflow-hidden shadow-sm ring-1 ring-border")}
           style={{ aspectRatio: "3 / 4" }}>
        {src ? (
          <img src={src} alt={`Page ${n}`} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full animate-pulse bg-muted" />
        )}
      </div>
      <span className="ml-2 text-xs text-muted-foreground">P.{n}</span>
    </button>
  );
}
