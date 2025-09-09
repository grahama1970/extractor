"use client";
import * as React from "react";
import { Button } from "@/components/ui/button";

export function PdfTree({ files, current, onSelect }: { files: string[]; current?: string; onSelect: (rel: string) => void; }) {
  type Node = { name: string; path: string; children?: Record<string, Node>; file?: boolean };
  const root: Node = { name: "", path: "", children: {} } as any;
  for (const f of files) {
    const parts = f.split("/").filter(Boolean);
    let cur = root;
    let accum = [] as string[];
    for (let i=0;i<parts.length;i++) {
      const p = parts[i];
      accum.push(p);
      const key = p;
      if (!cur.children) cur.children = {};
      if (!cur.children[key]) cur.children[key] = { name: p, path: accum.join("/"), children: {} };
      cur = cur.children[key];
      if (i === parts.length-1) { cur.file = true; }
    }
  }
  const [open, setOpen] = React.useState<Set<string>>(() => {
    const s = new Set<string>();
    if (current) {
      const parts = current.split("/");
      let path = "";
      for (const p of parts.slice(0, -1)) { path = path ? path + "/" + p : p; s.add(path); }
    }
    return s;
  });
  const toggle = (p: string) => setOpen(prev => { const n = new Set(prev); if (n.has(p)) n.delete(p); else n.add(p); return n; });
  const renderNode = (node: Node, depth: number) => {
    if (!node.children || Object.keys(node.children).length === 0) return null;
    const entries = Object.values(node.children).sort((a,b) => Number(!!b.file) - Number(!!a.file) || a.name.localeCompare(b.name));
    return (
      <div>
        {entries.map(child => {
          const isFile = !!child.file;
          const isOpen = open.has(child.path);
          const isActive = current === child.path;
          return (
            <div key={child.path} style={{ paddingLeft: depth * 10 }} className="text-sm">
              {isFile ? (
                <Button size="sm" variant={isActive? 'default':'secondary'} className="justify-start w-full" onClick={()=>onSelect(child.path)}>
                  {child.name}
                </Button>
              ) : (
                <div>
                  <Button size="sm" variant="ghost" className="justify-start w-full" onClick={()=>toggle(child.path)}>
                    <span className="inline-block w-4">{isOpen? '▾':'▸'}</span>
                    <span className="opacity-80">{child.name}</span>
                  </Button>
                  {isOpen && renderNode(child, depth+1)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };
  return (
    <div className="max-h-48 overflow-auto border rounded p-1">
      {renderNode(root, 0)}
    </div>
  );
}
