"use client";
import * as React from "react";
import { Stage, Layer, Rect, Group, Text } from "react-konva";

type NodePos = { id: string; x: number; y: number };

const CARD_W = 540;
const PAD = 16;

function Card({
  id,
  x,
  y,
  title,
  subtitle,
  onDragEnd,
}: {
  id: string;
  x: number;
  y: number;
  title: string;
  subtitle?: string;
  onDragEnd: (p: NodePos) => void;
}) {
  const HEIGHT = subtitle ? 88 : 68;
  return (
    <Group
      x={x}
      y={y}
      draggable
      onDragEnd={(e) => onDragEnd({ id, x: e.target.x(), y: e.target.y() })}
    >
      <Rect
        width={CARD_W}
        height={HEIGHT}
        cornerRadius={6}
        fill="#ffffff"
        stroke="#111827"
        strokeWidth={2}
        shadowColor="#00000022"
        shadowBlur={2}
        shadowOpacity={0.2}
      />
      <Text x={14} y={12} text={`📄 ${title}`} fontSize={22} fill="#111827" fontStyle="bold" />
      {subtitle ? (
        <Text x={18} y={44} text={subtitle} fontSize={16} fill="#374151" />
      ) : null}
      <Text
        x={CARD_W - 110}
        y={20}
        text="⬇ Export"
        fontSize={18}
        fill="#1d4ed8"
      />
    </Group>
  );
}

export default function LeftPaneProto() {
  const [nodes, setNodes] = React.useState<NodePos[]>([
    { id: "add", x: 20, y: 20 },
    { id: "search", x: 20, y: 110 },
    { id: "card1", x: 20, y: 190 },
    { id: "card2", x: 20, y: 300 },
    { id: "card3", x: 20, y: 410 },
    { id: "exportAll", x: 20, y: 740 },
  ]);

  const get = (id: string) => nodes.find((n) => n.id === id)!;
  const update = (p: NodePos) => setNodes((prev) => prev.map((n) => (n.id === p.id ? p : n)));

  const saveLocal = () => {
    try { localStorage.setItem("left_pane_proto", JSON.stringify(nodes)); } catch {}
  };
  const loadLocal = () => {
    try { const raw = localStorage.getItem("left_pane_proto"); if (!raw) return; const arr = JSON.parse(raw); if (Array.isArray(arr)) setNodes(arr as NodePos[]); } catch {}
  };
  const reset = () => {
    setNodes([
      { id: "add", x: 20, y: 20 },
      { id: "search", x: 20, y: 110 },
      { id: "card1", x: 20, y: 190 },
      { id: "card2", x: 20, y: 300 },
      { id: "card3", x: 20, y: 410 },
      { id: "exportAll", x: 20, y: 740 },
    ]);
  };

  const W = 620;
  const H = 900;

  return (
    <div className="p-4 space-y-2">
      <div className="flex items-center gap-2">
        <button className="px-3 py-1 border rounded" onClick={saveLocal}>Save</button>
        <button className="px-3 py-1 border rounded" onClick={loadLocal}>Load</button>
        <button className="px-3 py-1 border rounded" onClick={reset}>Reset</button>
        <div className="text-sm text-gray-600 ml-2">Drag blocks to rearrange. This is a rough, editable mock.</div>
      </div>

      <div className="border rounded shadow bg-gray-50 inline-block">
        <Stage width={W + PAD * 2} height={H + PAD * 2} className="bg-white">
          <Layer x={PAD} y={PAD}>
            {/* Add/Drop PDFs */}
            <Group
              x={get("add").x}
              y={get("add").y}
              draggable
              onDragEnd={(e) => update({ id: "add", x: e.target.x(), y: e.target.y() })}
            >
              <Rect width={CARD_W} height={70} cornerRadius={6} fill="#eef2f7" stroke="#6b7280" />
              <Text text="📁 Add / Drop PDFs" x={20} y={20} fontSize={26} fill="#111827" fontStyle="bold" />
            </Group>

            {/* Search */}
            <Group
              x={get("search").x}
              y={get("search").y}
              draggable
              onDragEnd={(e) => update({ id: "search", x: e.target.x(), y: e.target.y() })}
            >
              <Rect width={CARD_W} height={60} cornerRadius={6} fill="#ffffff" stroke="#6b7280" />
              <Text text="🔎 Search PDFs…" x={20} y={18} fontSize={20} fill="#6b7280" />
            </Group>

            {/* Cards */}
            <Card id="card1" x={get("card1").x} y={get("card1").y} title="BHT_CV32A65X.pdf" subtitle="12 pages | In Progress ⧗" onDragEnd={update} />
            <Card id="card2" x={get("card2").x} y={get("card2").y} title="DesignDoc_v2.pdf" subtitle="25 pages | ✓ Exported" onDragEnd={update} />
            <Card id="card3" x={get("card3").x} y={get("card3").y} title="2507.00114v1.pdf" subtitle="6 pages | □ Not Started" onDragEnd={update} />

            {/* Export All */}
            <Group
              x={get("exportAll").x}
              y={get("exportAll").y}
              draggable
              onDragEnd={(e) => update({ id: "exportAll", x: e.target.x(), y: e.target.y() })}
            >
              <Rect width={CARD_W} height={70} cornerRadius={6} fill="#eef2f7" stroke="#6b7280" />
              <Text text="⬇ Export All → JSON Dataset" x={20} y={22} fontSize={22} fill="#111827" fontStyle="bold" />
            </Group>
          </Layer>
        </Stage>
      </div>
    </div>
  );
}
