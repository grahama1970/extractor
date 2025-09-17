import React from "react";
import type { PdfDoc } from "@/lib/pdf";
import { renderPageCanvas } from "@/lib/pdf";

export function PdfCanvas({ doc, page, zoom = 1 }: { doc: PdfDoc; page: number; zoom?: number }) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctrl = new AbortController();
    (async () => {
      await renderPageCanvas(doc, page, canvas, zoom, ctrl.signal);
    })();
    return () => ctrl.abort();
  }, [doc, page, zoom]);

  return <canvas ref={canvasRef} className="bg-white rounded" />;
}
