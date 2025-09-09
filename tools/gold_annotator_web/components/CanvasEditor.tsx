"use client";
import { Stage, Layer, Image as KonvaImage, Rect, Transformer } from "react-konva";
import * as React from "react";

export type Box = {
  id: string;
  page: number;
  x: number; // normalized [0,1]
  y: number;
  w: number;
  h: number;
};

function URLImage({ src, width, height }: { src: string; width: number; height: number }) {
  const [image] = useImage(src);
  return <KonvaImage image={image as HTMLImageElement} width={width} height={height} />;
}

export function CanvasEditor({
  src,
  width,
  height,
  boxes,
  onChange,
}: {
  src: string;
  width: number;
  height: number;
  boxes: Box[];
  onChange: (boxes: Box[]) => void;
}) {
  const [selectedId, setSelectedId] = React.useState<string | null>(null);

  const handleMouseDown = (e: any) => {
    // click on empty area - start drawing
    const stage = e.target.getStage();
    if (!stage) return;
    const pos = stage.getPointerPosition();
    if (!pos) return;
    const x = pos.x / width;
    const y = pos.y / height;
    const newBox: Box = {
      id: `box_${Date.now()}`,
      page: 1,
      x,
      y,
      w: 0.01,
      h: 0.01,
    };
    onChange([...boxes, newBox]);
    setSelectedId(newBox.id);
  };

  return (
    <Stage width={width} height={height} onMouseDown={(e) => { if (e.target === e.target.getStage()) handleMouseDown(e); }}>
      <Layer>
        <URLImage src={src} width={width} height={height} />
        {boxes.map((b) => (
          <Rect
            key={b.id}
            x={b.x * width}
            y={b.y * height}
            width={b.w * width}
            height={b.h * height}
            stroke={b.id === selectedId ? "#2563eb" : "#111"}
            strokeWidth={2}
            draggable
            onClick={() => setSelectedId(b.id)}
            onDragEnd={(e) => {
              const nx = Math.max(0, Math.min(1, e.target.x() / width));
              const ny = Math.max(0, Math.min(1, e.target.y() / height));
              onChange(boxes.map((bx) => (bx.id === b.id ? { ...bx, x: nx, y: ny } : bx)));
            }}
            onTransformEnd={(e) => {
              const node = e.target;
              const nx = Math.max(0, Math.min(1, node.x() / width));
              const ny = Math.max(0, Math.min(1, node.y() / height));
              const nw = Math.max(0.001, node.width() * node.scaleX()) / width;
              const nh = Math.max(0.001, node.height() * node.scaleY()) / height;
              node.scaleX(1); node.scaleY(1);
              onChange(boxes.map((bx) => (bx.id === b.id ? { ...bx, x: nx, y: ny, w: nw, h: nh } : bx)));
            }}
          />
        ))}
        {boxes.map((b) => (
          b.id === selectedId ? (
            <Transformer key={b.id + "_tr"}
              nodes={(window as any).Konva?.stage?.find?.(`#${b.id}`) || []}
              rotateEnabled={false}
            />
          ) : null
        ))}
      </Layer>
    </Stage>
  );
}
// Lightweight image loader hook to avoid external deps
function useImage(src: string): [HTMLImageElement | null] {
  const [image, setImage] = React.useState<HTMLImageElement | null>(null);
  React.useEffect(() => {
    if (!src) { setImage(null); return; }
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.src = src;
    const onLoad = () => setImage(img);
    img.addEventListener('load', onLoad);
    return () => img.removeEventListener('load', onLoad);
  }, [src]);
  return [image];
}
