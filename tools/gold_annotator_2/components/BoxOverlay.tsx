'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { Box, BBox } from '../lib/types';
import { toScreen, toNormalized } from '../lib/transforms';

type Props = {
  width: number;
  height: number;
  viewport: { width: number; height: number } | null;
  boxes: Box[];
  onChange: (boxes: Box[]) => void;
  page: number;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
};

type Drag =
  | { kind: 'none' }
  | { kind: 'creating'; start: { x: number; y: number } }
  | { kind: 'moving'; id: string; start: { x: number; y: number }; orig: BBox }
  | { kind: 'resizing'; id: string; handle: string; start: { x: number; y: number }; orig: BBox };

export default function BoxOverlay({ width, height, viewport, boxes, onChange, page, selectedId, onSelect }: Props) {
  const [drag, setDrag] = useState<Drag>({ kind: 'none' });
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!selectedId) return;
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        onChange(boxes.filter((b) => b.id !== selectedId));
        onSelect(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedId, boxes, onChange]);

  const handleDown = (e: React.MouseEvent) => {
    if (!viewport) return;
    const rect = (e.target as Element).closest('svg')!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const target = (e.target as HTMLElement).dataset.handle;
    const id = (e.target as HTMLElement).dataset.boxid;
    if (target && id) {
      const b = boxes.find((bb) => bb.id === id)!;
      onSelect(id);
      setDrag({ kind: 'resizing', id, handle: target, start: { x, y }, orig: { ...b.bbox } });
      return;
    }
    if (id) {
      const b = boxes.find((bb) => bb.id === id)!;
      onSelect(id);
      setDrag({ kind: 'moving', id, start: { x, y }, orig: { ...b.bbox } });
      return;
    }
    onSelect(null);
    setDrag({ kind: 'creating', start: { x, y } });
  };

  const handleMove = (e: React.MouseEvent) => {
    if (!viewport) return;
    if (drag.kind === 'none') return;
    const rect = (e.target as Element).closest('svg')!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (drag.kind === 'creating') {
      const s = drag.start;
      const rx = Math.min(s.x, x);
      const ry = Math.min(s.y, y);
      const rw = Math.abs(x - s.x);
      const rh = Math.abs(y - s.y);
      const nb = toNormalized({ x: rx, y: ry, w: rw, h: rh }, viewport);
      const temp: Box = { id: '__creating__', page, bbox: nb };
      // render temporary by replacing/adding if present
      const others = boxes.filter((b) => b.id !== '__creating__');
      onChange([...others, temp]);
      return;
    }

    if (drag.kind === 'moving') {
      const b = boxes.find((bb) => bb.id === drag.id);
      if (!b) return;
      const s = toScreen(drag.orig, viewport);
      const dx = x - drag.start.x;
      const dy = y - drag.start.y;
      const moved = toNormalized({ x: s.x + dx, y: s.y + dy, w: s.w, h: s.h }, viewport);
      onChange(boxes.map((bb) => (bb.id === drag.id ? { ...bb, bbox: moved } : bb)));
      return;
    }

    if (drag.kind === 'resizing') {
      const b = boxes.find((bb) => bb.id === drag.id);
      if (!b) return;
      const s = toScreen(drag.orig, viewport);
      let { x: nx, y: ny, w: nw, h: nh } = s;
      const dx = x - drag.start.x;
      const dy = y - drag.start.y;
      if (drag.handle.includes('left')) {
        nx += dx;
        nw -= dx;
      }
      if (drag.handle.includes('right')) {
        nw += dx;
      }
      if (drag.handle.includes('top')) {
        ny += dy;
        nh -= dy;
      }
      if (drag.handle.includes('bottom')) {
        nh += dy;
      }
      nw = Math.max(2, nw);
      nh = Math.max(2, nh);
      const resized = toNormalized({ x: nx, y: ny, w: nw, h: nh }, viewport);
      onChange(boxes.map((bb) => (bb.id === drag.id ? { ...bb, bbox: resized } : bb)));
      return;
    }
  };

  const handleUp = () => {
    if (!viewport) return;
    if (drag.kind === 'creating') {
      const temp = boxes.find((b) => b.id === '__creating__');
      if (temp && temp.bbox.w > 0.005 && temp.bbox.h > 0.005) {
        const id = `b_${Date.now().toString(36)}`;
        onChange(boxes.map((b) => (b.id === '__creating__' ? { ...b, id } : b)));
        onSelect(id);
      } else if (temp) {
        onChange(boxes.filter((b) => b.id !== '__creating__'));
      }
    }
    setDrag({ kind: 'none' });
  };

  const renderHandles = (b: Box) => {
    if (b.id !== selectedId || !viewport) return null;
    const s = toScreen(b.bbox, viewport);
    const hs = 6;
    const handles = [
      { k: 'top-left', x: s.x, y: s.y },
      { k: 'top-right', x: s.x + s.w, y: s.y },
      { k: 'bottom-left', x: s.x, y: s.y + s.h },
      { k: 'bottom-right', x: s.x + s.w, y: s.y + s.h }
    ];
    return handles.map((h) => (
      <rect
        key={h.k}
        x={h.x - hs / 2}
        y={h.y - hs / 2}
        width={hs}
        height={hs}
        fill="#fff"
        stroke="#2563eb"
        strokeWidth={1}
        data-handle={h.k}
        data-boxid={b.id}
        style={{ cursor: `${h.k.replace('-', '-')}-resize` }}
      />
    ));
  };

  const renderHud = (b: Box) => {
    if (b.id !== selectedId || !viewport) return null;
    const s = toScreen(b.bbox, viewport);
    const bx = Math.max(8, s.x + 8);
    const by = Math.max(8, s.y - 32);
    const pad = 6;
    const w = 64, h = 28, r = 8;
    return (
      <g>
        <rect x={bx} y={by} width={w} height={h} rx={r} ry={r} fill="#ffffff" stroke="#e5e7eb" />
        <g transform={`translate(${bx + pad}, ${by + pad})`}>
          <rect width={20} height={16} rx={4} ry={4} fill="#eef2ff" stroke="#c7d2fe" cursor="pointer"
            onClick={() => {
              const dup: Box = { ...b, id: `b_${Date.now().toString(36)}` };
              onChange([...boxes, dup]);
            }}
          />
          <text x={6} y={12} fontSize={10} fill="#4f46e5">⎘</text>
          <rect x={28} width={20} height={16} rx={4} ry={4} fill="#fee2e2" stroke="#fecaca" cursor="pointer"
            onClick={() => onChange(boxes.filter(x => x.id !== b.id))}
          />
          <text x={34} y={12} fontSize={10} fill="#ef4444">🗑</text>
        </g>
      </g>
    );
  };

  const content = useMemo(() => {
    if (!viewport) return null;
    return boxes
      .filter((b) => b.page === page)
      .map((b) => {
        const s = toScreen(b.bbox, viewport);
        return (
          <g key={b.id} data-boxid={b.id} style={{ cursor: 'move' }}>
            <rect
              x={s.x}
              y={s.y}
              width={s.w}
              height={s.h}
              fill="rgba(59,130,246,0.08)"
              stroke={b.id === selectedId ? '#2563eb' : '#60a5fa'}
              strokeDasharray={b.id === selectedId ? undefined : '4 2'}
              strokeWidth={1}
              data-boxid={b.id}
            />
            {renderHandles(b)}
            {renderHud(b)}
          </g>
        );
      });
  }, [boxes, page, selectedId, viewport]);

  return (
    <svg
      data-testid="overlay"
      ref={svgRef}
      width={width}
      height={height}
      onMouseDown={handleDown}
      onMouseMove={handleMove}
      onMouseUp={handleUp}
      style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'auto' }}
    >
      {content}
    </svg>
  );
}
