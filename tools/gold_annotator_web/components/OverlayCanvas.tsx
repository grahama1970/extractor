"use client";
import { Stage, Layer, Rect, Transformer, Label as KLabel, Tag as KTag, Text as KText } from "react-konva";
import * as React from "react";

export type Box = {
  id: string;
  page: number;
  x: number;
  y: number;
  w: number;
  h: number;
  type?: string;
  expected_json?: string;
  part_idx?: number;
};

export function OverlayCanvas({
  width,
  height,
  page = 1,
  boxes,
  onChange,
  selectedId,
  onSelect,
  onDelete,
  onCreate,
  defaultType,
}: {
  width: number;
  height: number;
  page?: number;
  boxes: Box[];
  onChange: (b: Box[]) => void;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  onDelete?: (id: string) => void;
  onCreate?: (b: Box) => void;
  defaultType?: string;
}) {
  const trRef = React.useRef<any>(null);
  const layerRef = React.useRef<any>(null);
  const drawingRef = React.useRef<{ startX: number; startY: number; id: string } | null>(null);
  const SNAP_PX = 6; // pixels

  const cssVar = (name: string): string | null => {
    try {
      if (typeof window === 'undefined') return null;
      const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return v || null;
    } catch { return null; }
  };
  const colorForType = (t?: string) => {
    const byType: Record<string, { var: string; fallback: string }> = {
      section: { var: '--label-color-section', fallback: '#8b5cf6' },
      table: { var: '--label-color-table', fallback: '#10b981' },
      figure: { var: '--label-color-figure', fallback: '#f59e0b' },
      requirements: { var: '--label-color-requirements', fallback: '#0ea5e9' },
      text: { var: '--label-color-text', fallback: '#f43f5e' },
      default: { var: '--label-color-default', fallback: '#64748b' },
    };
    const key = (t && byType[t]) ? t : 'default';
    const stroke = cssVar(byType[key].var) || byType[key].fallback;
    return { stroke, badge: stroke };
  };

  // Attach transformer to selected node
  React.useEffect(() => {
    if (!trRef.current || !layerRef.current) return;
    const layer = layerRef.current;
    const stage = layer.getStage();
    if (!stage) return;
    const node = selectedId ? stage.findOne(`#rect-${selectedId}`) : null;
    trRef.current.nodes(node ? [node] : []);
    layer.batchDraw();
  }, [selectedId, boxes]);

  // Delete with keyboard
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = (target?.tagName || '').toLowerCase();
      const isEditable = !!(target && (tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable));
      if (isEditable) return; // don't delete while typing in inputs
      if ((e.key === "Delete" || e.key === "Backspace") && selectedId) {
        onDelete?.(selectedId);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectedId, onDelete]);

  const snapNorm = (val: number, size: number, dimPx: number) => {
    const tol = SNAP_PX / dimPx;
    // snap start edge
    if (Math.abs(val - 0) <= tol) val = 0;
    if (Math.abs(val + size - 1) <= tol) val = 1 - size;
    // clamp
    return Math.max(0, Math.min(1 - size, val));
  };

  const handleMouseDown = (e: any) => {
    const stage = e.target.getStage();
    if (!stage) return;
    if (e.target === stage) {
      const pos = stage.getPointerPosition();
      if (!pos) return;
      const pref = (defaultType || 'box');
      const id = `${pref}_${Date.now()}`;
      drawingRef.current = { startX: pos.x, startY: pos.y, id };
      // create a zero-size box placeholder so we can show feedback
      const nb: Box = { id, page, x: pos.x / width, y: pos.y / height, w: 0.0001, h: 0.0001, type: defaultType } as Box;
      onChange([...boxes, nb]);
      onSelect?.(id);
      onCreate?.(nb);
    }
  };

  const handleMouseMove = (e: any) => {
    if (!drawingRef.current) return;
    const stage = e.target.getStage();
    if (!stage) return;
    const pos = stage.getPointerPosition();
    if (!pos) return;
    const { startX, startY, id } = drawingRef.current;
    const x1 = Math.min(startX, pos.x);
    const y1 = Math.min(startY, pos.y);
    const x2 = Math.max(startX, pos.x);
    const y2 = Math.max(startY, pos.y);
    let nx = x1 / width;
    let ny = y1 / height;
    let nw = Math.max(0.0001, (x2 - x1) / width);
    let nh = Math.max(0.0001, (y2 - y1) / height);
    // snap to canvas edges
    nx = snapNorm(nx, nw, width);
    ny = snapNorm(ny, nh, height);
    onChange(boxes.map(b => (b.id === id ? { ...b, x: nx, y: ny, w: nw, h: nh } : b)));
  };

  const handleMouseUp = (e: any) => {
    if (!drawingRef.current) return;
    const { id } = drawingRef.current;
    drawingRef.current = null;
    const b = boxes.find(bb => bb.id === id);
    if (!b) return;
    // remove if too small (less than 4x4 px)
    if (b.w * width < 4 || b.h * height < 4) {
      onChange(boxes.filter(bb => bb.id !== id));
      onSelect?.(null);
    }
  };

  return (
    <Stage width={width} height={height} onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} className="cursor-crosshair">
      <Layer ref={layerRef}>
        {boxes.map((b) => {
          const isActive = b.id === selectedId;
          const c = colorForType(b.type);
          const bx = b.x * width;
          const by = b.y * height;
          const bw = b.w * width;
          const bh = b.h * height;
          const labelText = (b.type || '').toString();
          const tagX = Math.max(2, Math.min(width - 120, bx + 2));
          const tagY = Math.max(2, by - 18);
          return (
            <React.Fragment key={b.id}>
              <Rect
                id={`rect-${b.id}`}
                x={bx}
                y={by}
                width={bw}
                height={bh}
                stroke={isActive ? c.stroke : c.stroke}
                strokeWidth={isActive ? 2.5 : 2}
                dash={isActive ? undefined : [4, 4]}
                draggable
                onClick={() => onSelect?.(b.id)}
                onDragEnd={(e) => {
                  const node = e.target;
                  const curW = b.w;
                  const curH = b.h;
                  let nx = node.x() / width;
                  let ny = node.y() / height;
                  nx = snapNorm(nx, curW, width);
                  ny = snapNorm(ny, curH, height);
                  onChange(boxes.map((bx0) => (bx0.id === b.id ? { ...bx0, x: nx, y: ny } : bx0)));
                }}
                onTransformEnd={(e) => {
                  const node = e.target;
                  let nx = node.x() / width;
                  let ny = node.y() / height;
                  let nw = Math.max(0.001, node.width() * node.scaleX()) / width;
                  let nh = Math.max(0.001, node.height() * node.scaleY()) / height;
                  node.scaleX(1); node.scaleY(1);
                  // snap after resize
                  nx = snapNorm(nx, nw, width);
                  ny = snapNorm(ny, nh, height);
                  onChange(boxes.map((bx0) => (bx0.id === b.id ? { ...bx0, x: nx, y: ny, w: nw, h: nh } : bx0)));
                }}
              />
              {labelText ? (
                <KLabel x={tagX} y={Math.max(2, tagY)}>
                  <KTag fill={c.badge} cornerRadius={4} />
                  <KText text={labelText} fill="#ffffff" fontSize={11} padding={4} />
                </KLabel>
              ) : null}
            </React.Fragment>
          );
        })}
        <Transformer ref={trRef} rotateEnabled={false} ignoreStroke={true} />
      </Layer>
    </Stage>
  );
}
