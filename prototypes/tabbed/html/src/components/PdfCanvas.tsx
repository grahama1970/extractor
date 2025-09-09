import React from "react";
import type { PdfDoc } from "@/lib/pdf";
import { renderPageCanvas } from "@/lib/pdf";

export function PdfCanvas({ doc, page, zoom = 1 }: { doc: PdfDoc; page: number; zoom?: number }) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let cancelled = false;
    (async () => {
      await renderPageCanvas(doc, page, canvas, zoom);
      if (cancelled) return;
    })();
    return () => {
      cancelled = true;
    };
  }, [doc, page, zoom]);

  return <canvas ref={canvasRef} className="bg-white rounded" />;
}

