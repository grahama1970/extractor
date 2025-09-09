"use client";
import * as React from "react";
import * as pdfjsLib from "pdfjs-dist";

export function PdfViewer({
  url,
  pageNumber,
  scale,
  onRendered,
  onDocLoaded,
}: {
  url: string;
  pageNumber: number;
  scale: number; // e.g., 1.0, 1.5, 2.0
  onRendered?: (width: number, height: number) => void;
  onDocLoaded?: (pageCount: number) => void;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const loadingRef = React.useRef<any>(null);
  const renderRef = React.useRef<any>(null);
  const pdfRef = React.useRef<any>(null);
  const [docReadyKey, setDocReadyKey] = React.useState(0);
  const onRenderedRef = React.useRef<typeof onRendered>();
  // Keep latest callback without retriggering effects
  React.useEffect(() => { onRenderedRef.current = onRendered; }, [onRendered]);
  const onDocLoadedRef = React.useRef<typeof onDocLoaded>();
  React.useEffect(() => { onDocLoadedRef.current = onDocLoaded; }, [onDocLoaded]);

  // Configure pdf.js v4 worker using a module worker served from our API route
  React.useEffect(() => {
    try {
      const prev: Worker | undefined = (pdfjsLib as any).GlobalWorkerOptions.workerPort;
      if (prev && typeof (prev as any).terminate === 'function') {
        try { (prev as any).terminate(); } catch {}
      }
    } catch {}
    try {
      if (typeof window !== 'undefined' && 'Worker' in window) {
        const worker = new Worker('/api/pdfjs/pdf.worker.mjs', { type: 'module' } as any);
        (pdfjsLib as any).GlobalWorkerOptions.workerPort = worker as any;
      }
    } catch (e) {
      try { (pdfjsLib as any).GlobalWorkerOptions.workerPort = null; } catch {}
    }
  }, []);


  // Effect 1: (re)load document when URL changes
  React.useEffect(() => {
    let cancelled = false;

    // Cancel any in-flight render before switching documents and await its rejection
    try {
      const prevRender = renderRef.current;
      if (prevRender?.cancel) {
        prevRender.cancel();
        try { prevRender.promise?.catch(() => {}); } catch {}
      }
    } catch {}

    // Capture previous tasks and clear refs so we can await destruction before starting a new load
    const prevLoading = loadingRef.current;
    const prevPdf = pdfRef.current;
    loadingRef.current = null;
    pdfRef.current = null;

    const awaitDestroy = async (obj: any) => {
      try {
        if (obj?.destroy) {
          await obj.destroy();
        }
      } catch {}
    };

    (async () => {
      // Ensure previous loading/doc and their worker are fully torn down (pdf.js v4 requires await)
      await awaitDestroy(prevLoading);
      await awaitDestroy(prevPdf);
      if (cancelled) return;

      const loadingTask = (pdfjsLib as any).getDocument({ url });
      loadingRef.current = loadingTask;

      loadingTask.promise.then((pdf: any) => {
        if (cancelled) return;
        pdfRef.current = pdf;
        try { onDocLoadedRef.current?.(pdf.numPages || 0); } catch {}
        // Signal that a new document is ready to render
        setDocReadyKey(k => k + 1);
      }).catch((err: any) => {
        const name = err?.name || "";
        if (name === "RenderingCancelledException" || name === "AbortException") {
          return; // expected during fast reloads
        }
        if (!cancelled) {
          // eslint-disable-next-line no-console
          console.error("PDF load error:", err);
        }
      });
    })();

    return () => {
      cancelled = true;
      // Cancel the current render, and best-effort wait for rejection
      const prevRender = renderRef.current;
      try { prevRender?.cancel?.(); } catch {}
      try { prevRender?.promise?.catch(() => {}); } catch {}
      // Trigger destruction of any in-flight loading/doc tasks (next effect will await them)
      try { loadingRef.current?.destroy?.(); } catch {}
      try { pdfRef.current?.destroy?.(); } catch {}
    };
  }, [url]);

  // Effect 2: render the requested page/scale for the loaded document
  React.useEffect(() => {
    let cancelled = false;
    const pdf = pdfRef.current;
    if (!pdf) return;

    // Cancel any previous render before starting a new one
    try { renderRef.current?.cancel?.(); } catch {}

    (async () => {
      try {
        const page = await pdf.getPage(pageNumber);
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current!;
        const ctx = canvas?.getContext("2d");
        if (!canvas || !ctx) return;
        const dpr = (typeof window !== 'undefined' && window.devicePixelRatio) ? window.devicePixelRatio : 1;
        const cssWidth = Math.floor(viewport.width);
        const cssHeight = Math.floor(viewport.height);
        // Set CSS size for layout/overlay alignment
        canvas.style.width = cssWidth + 'px';
        canvas.style.height = cssHeight + 'px';
        // Set backing store size for crisp rendering on HiDPI
        canvas.width = Math.floor(cssWidth * dpr);
        canvas.height = Math.floor(cssHeight * dpr);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const renderTask = page.render({
          canvasContext: ctx,
          viewport,
          transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
        } as any);
        renderRef.current = renderTask;
        try {
          await renderTask.promise;
          if (cancelled) return;
          // Report CSS dimensions, not backing store size
          onRenderedRef.current?.(cssWidth, cssHeight);
        } catch (err: any) {
          const name = err?.name || "";
          if (name === "RenderingCancelledException" || name === "AbortException") {
            // expected when superseded by a new render
          } else if (!cancelled) {
            // eslint-disable-next-line no-console
            console.error("PDF render error:", err);
          }
        }
      } catch (err: any) {
        const name = err?.name || "";
        if (name === "RenderingCancelledException" || name === "AbortException") {
          return;
        }
        if (!cancelled) {
          // eslint-disable-next-line no-console
          console.error("PDF page fetch error:", err);
        }
      }
    })();

    return () => {
      cancelled = true;
      try { renderRef.current?.cancel?.(); } catch {}
    };
  }, [docReadyKey, pageNumber, scale]);

  return <canvas ref={canvasRef} className="block" data-testid="viewer-canvas" />;
}
