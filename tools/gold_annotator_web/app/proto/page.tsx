"use client";
import * as React from "react";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const PdfViewer = dynamic(() => import("@/components/PdfViewer").then(m => m.PdfViewer), { ssr: false });

export default function ProtoTriPane() {
  const [pdfPath, setPdfPath] = React.useState("tools/gold_annotator_web/data/input/BHT CV32A65X.pdf");
  const [pdfUrl, setPdfUrl] = React.useState<string>("");

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100">
      {/* Left Explorer */}
      <aside className="w-72 border-r border-slate-800 p-3 space-y-3" data-testid="explorer-pane">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-slate-200">Explorer</h2>
        </div>
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wider text-slate-400">Document</div>
          <Input className="bg-slate-800 border-slate-700 text-slate-100"
                 value={pdfPath} onChange={e=>setPdfPath(e.target.value)} placeholder="data/input/...pdf" />
          <Button variant="secondary" onClick={()=>setPdfUrl(`/api/pdf?path=${encodeURIComponent(pdfPath)}`)} data-testid="load-pdf-btn">Load PDF</Button>
        </div>
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wider text-slate-400">Pages</div>
          <div className="text-sm italic text-slate-500">No PDF loaded.</div>
        </div>
        <div className="mt-auto space-y-2">
          <div className="text-xs uppercase tracking-wider text-slate-400">Export</div>
          <Button variant="ghost" className="w-full" disabled>Export Annotations</Button>
          <Button variant="ghost" className="w-full" disabled>Export Pane State</Button>
        </div>
      </aside>

      {/* Center Viewer */}
      <main className="flex-1 relative" data-testid="viewer-pane">
        <div className="h-10 border-b border-slate-800 flex items-center gap-2 px-3 text-slate-300">
          <span className="text-sm">PDF Viewer</span>
          <div className="ml-auto text-xs opacity-60">Prototype</div>
        </div>
        <div className="absolute inset-0 top-10 flex items-center justify-center">
          {pdfUrl ? (
            <div className="p-3">
              <PdfViewer url={pdfUrl} pageNumber={1} scale={1.2} onRendered={()=>{}} onDocLoaded={()=>{}} />
            </div>
          ) : (
            <div className="text-center text-slate-400">
              <div className="text-lg font-semibold mb-2">No PDF Loaded</div>
              <div className="text-sm">Load a PDF from the Explorer panel to start.</div>
              <div className="mt-4 space-y-1 text-xs text-slate-500">
                <div><kbd className="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded">V</kbd> Box tool</div>
                <div><kbd className="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded">P</kbd> Pan tool</div>
                <div><kbd className="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded">S</kbd> Select tool</div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Right Inspector */}
      <aside className="w-80 border-l border-slate-800 p-3 space-y-4" data-testid="inspector-pane">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-slate-200">Inspector</h2>
        </div>
        <div className="flex flex-col items-center justify-center text-slate-400 h-full">
          <div className="text-sm font-semibold mb-1">No Selection</div>
          <div className="text-xs text-center opacity-70">Select a region to edit its properties.</div>
        </div>
      </aside>
    </div>
  );
}

