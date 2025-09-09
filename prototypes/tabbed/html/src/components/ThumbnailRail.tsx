import React from "react";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PdfDoc } from "@/lib/pdf";
import { renderPageThumbnail } from "@/lib/pdf";

const memCache = new Map<string, string>();

export function ThumbnailRail({
  doc,
  pageCount,
  currentPage,
  onJump,
  width = 144,
}: {
  doc: PdfDoc;
  pageCount: number;
  currentPage: number; // 1-based
  onJump: (n: number) => void;
  width?: number;
}) {
  const ref = React.useRef<VirtuosoHandle>(null);

  React.useEffect(() => {
    ref.current?.scrollToIndex({ index: currentPage - 1, align: "center", behavior: "smooth" });
  }, [currentPage]);

  return (
    <div className="w-40 border-r bg-muted/30 overflow-hidden">
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
}: {
  doc: PdfDoc;
  n: number;
  isActive: boolean;
  onJump: (n: number) => void;
  width: number;
}) {
  const [src, setSrc] = React.useState<string | undefined>(undefined);
  React.useEffect(() => {
    let cancelled = false;
    const key = `${n}@${width}`;
    const hit = memCache.get(key);
    if (hit) {
      setSrc(hit);
    } else {
      renderPageThumbnail(doc, n, width).then((s) => {
        if (!cancelled && s) {
          memCache.set(key, s);
          setSrc(s);
        }
      });
    }
    return () => {
      cancelled = true;
    };
  }, [doc, n, width]);

  return (
    <button
      onClick={() => onJump(n)}
      className={cn(
        "group w-full px-2 py-3 text-left focus:outline-none",
        isActive && "bg-primary/10"
      )}
      aria-current={isActive ? "page" : undefined}
    >
      <div
        className={cn(
          "aspect-[3/4] w-full rounded-xl overflow-hidden shadow-sm ring-1 ring-border",
          "group-hover:ring-primary"
        )}
      >
        {src ? (
          <img src={src} alt={`Page ${n}`} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full animate-pulse bg-muted" />
        )}
      </div>
      <div className="mt-2 text-xs text-muted-foreground flex items-center justify-between">
        <span>P.{n}</span>
      </div>
    </button>
  );
}

