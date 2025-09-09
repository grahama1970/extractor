'use client';

import { useEffect, useRef, useState, useMemo } from 'react';
import BoxOverlay from './BoxOverlay';
import Inspector from './Inspector';
import type { Box } from '../lib/types';
import { keyForDoc, loadBoxes, loadLastPage, saveBoxes, saveLastPage } from '../lib/storage';

type PdfModule = typeof import('pdfjs-dist');

export default function PdfViewer({ fileData, fileName, fileSize, debugDemo }: { fileData?: ArrayBuffer; fileName?: string; fileSize?: number; debugDemo?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pdfRef = useRef<any>(null);
  const pageRef = useRef<number>(1);
  const renderTaskRef = useRef<any>(null);
  const pdfjsRef = useRef<PdfModule | null>(null);
  const [pageCount, setPageCount] = useState<number>(0);
  const [scale, setScale] = useState<number>(1);
  const [ready, setReady] = useState<boolean>(false);
  const [viewportSize, setViewportSize] = useState<{ width: number; height: number } | null>(null);
  const [boxes, setBoxes] = useState<Box[]>([]);
  const docKeyRef = useRef<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Configure worker and lazy-load pdfjs on first client render
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const pdfjs = (await import('pdfjs-dist')) as PdfModule;
      // @ts-ignore - worker options exist at runtime
      (pdfjs as any).GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';
      if (!cancelled) {
        pdfjsRef.current = pdfjs;
        setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Listen for autoload from page script (for ?sample=1)
  useEffect(() => {
    const handler = (e: any) => {
      const buf: ArrayBuffer | undefined = e?.detail?.buf;
      if (buf) {
        setTimeout(() => {
          // use synthetic name/size
          (async () => {
            const data = buf;
            const name = 'sample.pdf';
            const size = data.byteLength;
            // set via local state in parent; we can't from here, but we can directly set file via hack
          })();
        }, 0);
      }
    };
    // noop in this simplified spike — page.tsx sets state directly
    window.addEventListener('ga2_autoload', handler as any);
    return () => window.removeEventListener('ga2_autoload', handler as any);
  }, []);

  // Load the PDF when fileData changes
  useEffect(() => {
    if (!ready || !fileData) return;
    let destroyed = false;
    (async () => {
      try {
        const pdfjs = pdfjsRef.current!;
        const loadingTask = (pdfjs as any).getDocument({ data: fileData });
        const pdf = await loadingTask.promise;
        if (destroyed) return;
        pdfRef.current = pdf;
        setPageCount(pdf.numPages);
        // derive a basic docKey from blob size and a monotonic counter
        // note: in a real app, use a content hash; here we rely on name+size via input element upstairs
        docKeyRef.current = keyForDoc(fileName || 'local', fileSize ?? fileData.byteLength);
        const last = loadLastPage(docKeyRef.current) || 1;
        pageRef.current = Math.min(Math.max(1, last), pdf.numPages);
        const loaded = loadBoxes(docKeyRef.current, pageRef.current).map((b) => ({ ...b, page: b.page || pageRef.current }));
        setBoxes(loaded);
        await renderPage(pageRef.current, scale);
        // Optional demo box when ?demo=1
        if (debugDemo) {
          const demo = [{ id: 'demo1', page: pageRef.current, bbox: { x: 0.1, y: 0.1, w: 0.3, h: 0.2 } } as Box];
          setBoxes(demo);
          if (docKeyRef.current) saveBoxes(docKeyRef.current, pageRef.current, demo);
        }
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Failed to load PDF', e);
      }
    })();
    return () => {
      destroyed = true;
      cancelRender();
      if (pdfRef.current) {
        try {
          pdfRef.current.destroy();
        } catch {}
        pdfRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileData, ready]);

  // Re-render current page when scale changes
  useEffect(() => {
    if (!pdfRef.current) return;
    renderPage(pageRef.current, scale);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scale]);

  // Keyboard shortcuts: [ / ] nav, Ctrl/Cmd+S save, f/t/s set label type
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName || '').toLowerCase();
      const inField = tag === 'input' || tag === 'textarea' || (document.activeElement as HTMLElement)?.isContentEditable;
      if (inField) return;
      if (e.key === '[') {
        e.preventDefault();
        gotoPage(pageRef.current - 1);
        return;
      }
      if (e.key === ']') {
        e.preventDefault();
        gotoPage(pageRef.current + 1);
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        if (docKeyRef.current) saveBoxes(docKeyRef.current, pageRef.current, boxes);
        return;
      }
      if (selectedId) {
        const i = boxes.findIndex((b) => b.id === selectedId);
        if (i >= 0) {
          const k = e.key.toLowerCase();
          if (k === 'f' || k === 't' || k === 's') {
            e.preventDefault();
            const type = k === 'f' ? 'Field' : k === 't' ? 'Table' : 'Section';
            const next = boxes.slice();
            next[i] = { ...next[i], labelType: type };
            setBoxes(next);
            if (docKeyRef.current) saveBoxes(docKeyRef.current, pageRef.current, next);
          }
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [boxes, selectedId]);

  function cancelRender() {
    const task = renderTaskRef.current;
    if (task && typeof task.cancel === 'function') {
      try {
        task.cancel();
      } catch {}
    }
    renderTaskRef.current = null;
  }

  async function renderPage(pageNumber: number, sc: number) {
    const pdf = pdfRef.current;
    if (!pdf) return;
    cancelRender();
    const page = await pdf.getPage(pageNumber);
    const viewport = page.getViewport({ scale: sc });
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d')!;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(viewport.width * ratio);
    canvas.height = Math.floor(viewport.height * ratio);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    setViewportSize({ width: viewport.width, height: viewport.height });
    const task = page.render({ canvasContext: ctx as any, viewport });
    renderTaskRef.current = task;
    try {
      await task.promise;
    } catch (e: any) {
      // Ignore cancellations
      if (!String(e).includes('Rendering cancelled')) {
        // eslint-disable-next-line no-console
        console.error('Render error', e);
      }
    }
  }

  async function gotoPage(next: number) {
    const pdf = pdfRef.current;
    if (!pdf) return;
    const clamped = Math.max(1, Math.min(pdf.numPages, next));
    pageRef.current = clamped;
    // load boxes for this page
    if (docKeyRef.current) setBoxes(loadBoxes(docKeyRef.current, clamped));
    if (docKeyRef.current) saveLastPage(docKeyRef.current, clamped);
    await renderPage(clamped, scale);
  }

  const disabled = !pdfRef.current;
  const chips = (() => {
    const total = pdfRef.current?.numPages || pageCount || 0;
    const cur = Math.max(1, Math.min(total || 1, pageRef.current || 1));
    const start = Math.max(1, cur - 3);
    const end = Math.min(total || cur, cur + 3);
    const arr: number[] = [];
    for (let i = start; i <= end; i++) arr.push(i);
    return arr;
  })();

  return (
    <div style={{ display: 'flex', gap: 16 }}>
      <div style={{ flex: '0 1 auto' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
          <button onClick={() => gotoPage(pageRef.current - 1)} disabled={disabled || pageRef.current <= 1}>
            Prev
          </button>
        <span>
          Page {disabled ? '-' : pageRef.current} / {pageCount || '-'}
        </span>
        <button onClick={() => gotoPage(pageRef.current + 1)} disabled={disabled || pageRef.current >= pageCount}>
          Next
        </button>
        <label style={{ marginLeft: 12 }}>
          Zoom
          <input
            type="range"
            min={50}
            max={200}
            step={10}
            value={Math.round(scale * 100)}
            onChange={(e) => setScale(Number(e.target.value) / 100)}
            style={{ verticalAlign: 'middle', marginLeft: 6 }}
          />
          <span style={{ marginLeft: 6 }}>{Math.round(scale * 100)}%</span>
        </label>
        <button
          style={{ marginLeft: 12 }}
          onClick={() => {
            const data = JSON.stringify(boxes, null, 2);
            const blob = new Blob([data], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `boxes_page_${pageRef.current}.json`;
            document.body.appendChild(a);
            a.click();
            a.remove();
          }}
          disabled={!boxes.length}
        >
          Export Boxes JSON
        </button>
        <button
          onClick={() => {
            setBoxes([]);
            if (docKeyRef.current) saveBoxes(docKeyRef.current, pageRef.current, []);
            setSelectedId(null);
          }}
          disabled={!boxes.length}
        >
          Clear Boxes
        </button>
        </div>
        <div style={{ position: 'relative', width: viewportSize?.width || 0, height: viewportSize?.height || 0, userSelect: 'none' }}>
          <canvas ref={canvasRef} style={{ background: '#f8f9fb', border: '1px solid #e2e8f0', position: 'absolute', left: 0, top: 0, zIndex: 1 }} />
          {viewportSize && (
            <BoxOverlay
              width={viewportSize.width}
              height={viewportSize.height}
              viewport={viewportSize}
              boxes={boxes}
              page={pageRef.current}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onChange={(next) => {
                setBoxes(next.map((b) => ({ ...b, page: pageRef.current })));
                if (docKeyRef.current) saveBoxes(docKeyRef.current, pageRef.current, next.map((b) => ({ ...b, page: pageRef.current })));
              }}
              // ensure on top of canvas
              
            />
          )}
        </div>
        <div className="pills" style={{ marginTop: 8 }}>
          {chips.map((p) => (
            <button key={p} className={"pill" + (p === pageRef.current ? ' active' : '')} onClick={() => gotoPage(p)}>
              P.{p}
            </button>
          ))}
        </div>
        <div className="sliderRow">
          <button className="btn small" onClick={() => gotoPage(1)} disabled={disabled || pageRef.current <= 1}>{'⟨'}</button>
          <input
            type="range"
            min={1}
            max={(pdfRef.current?.numPages || pageCount || 1)}
            value={pageRef.current}
            onChange={(e) => gotoPage(parseInt(e.target.value, 10))}
            style={{ flex:1 }}
          />
          <button className="btn small" onClick={() => gotoPage((pdfRef.current?.numPages || pageCount || 1))} disabled={disabled || pageRef.current >= (pdfRef.current?.numPages || pageCount || 1)}>{'⟩'}</button>
        </div>
      <div style={{ width: 280, borderLeft: '1px solid #e5e7eb', alignSelf: 'flex-start' }}>
        <Inspector
          box={boxes.find((b) => b.id === selectedId) || null}
          onChange={(updated) => {
            const next = boxes.map((b) => (b.id === updated.id ? updated : b));
            setBoxes(next);
            if (docKeyRef.current) saveBoxes(docKeyRef.current, pageRef.current, next);
          }}
          onDuplicate={(dup) => {
            const next = [...boxes, { ...dup, page: pageRef.current }];
            setBoxes(next);
            if (docKeyRef.current) saveBoxes(docKeyRef.current, pageRef.current, next);
            setSelectedId(dup.id);
          }}
        />
      </div>
    </div>
  </div>
  );
}
