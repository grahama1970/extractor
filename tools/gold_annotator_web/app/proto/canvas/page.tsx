"use client";
export const dynamic = "force-dynamic";
import * as React from "react";
import NextDynamic from "next/dynamic";
// Excalidraw prefers client-only import
const Excalidraw = NextDynamic<any>(
  async () => {
    const m: any = await import("@excalidraw/excalidraw");
    return m?.Excalidraw || m?.default || m;
  },
  { ssr: false, loading: () => <div className="p-2 text-sm text-gray-500">Loading canvas…</div> }
);

type ExcalState = { elements: any[]; appState?: any; files?: Record<string, any> } | null;


class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { error: any | null }> {
  constructor(props: any) {
    super(props);
    this.state = { error: null };
  }
  componentDidCatch(error: any, info: any) {
    this.setState({ error });
    try {
      fetch('/api/proto/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'error', where: 'canvas', message: String(error?.message||error), stack: String(error?.stack||''), info })
      });
    } catch {}
  }
  render() {
    if (this.state.error) {
      return <div className="p-4 text-red-700">Canvas error: {String(this.state.error?.message || this.state.error)}</div>;
    }
    return this.props.children as any;
  }
}


export default function CanvasProto() {
  const excalRef = React.useRef<any>(null);
  const [mountKey, setMountKey] = React.useState(0);
  const [initialData, setInitialData] = React.useState<ExcalState>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [version, setVersion] = React.useState<number>(0);
  const [publish, setPublish] = React.useState<boolean>(true);
  const pushTimerRef = React.useRef<any>(null);
  const [ready, setReady] = React.useState(false);

  const readScene = (): ExcalState => {
    const api = excalRef.current;
    if (!api?.getSceneElements) return null;
    try {
      return {
        elements: api.getSceneElements() || [],
        appState: api.getAppState ? api.getAppState() : {},
        files: api.getFiles ? api.getFiles() : {},
      };
    } catch {
      return null;
    }
  };

  const applyScene = (data: ExcalState) => {
    const api = excalRef.current;
    if (api?.updateScene && data) {
      api.updateScene(data);
    } else {
      setInitialData(data);
    }
  };

  const saveLocal = () => {
    try { const data = readScene(); localStorage.setItem("excal_proto", JSON.stringify(data)); } catch {}
  };
  const loadLocal = () => {
    try { const raw = localStorage.getItem("excal_proto"); if (raw) applyScene(JSON.parse(raw)); } catch {}
  };

  const loadServer = async () => {
    try {
      setLoading(true); setError(null);
      const res = await fetch("/api/proto/state");
      if (!res.ok) throw new Error(await res.text());
      const j = await res.json();
      applyScene(j.state || null);
      if (typeof j.version === "number") setVersion(j.version);
    } catch (e: any) { setError(e.message || "load failed"); }
    finally { setLoading(false); }
  };
  const saveServer = async () => {
    try {
      setLoading(true); setError(null);
      const data = readScene();
      if (!data || !Array.isArray((data as any).elements)) { setLoading(false); return; }
      const res = await fetch("/api/proto/state", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ifVersion: version, state: data }) });
      if (!res.ok) throw new Error(await res.text());
      const j = await res.json();
      if (typeof j.version === "number") setVersion(j.version);
    } catch (e: any) { setError(e.message || "save failed"); }
    finally { setLoading(false); }
  };

  const schedulePush = React.useCallback((next: ExcalState) => {
    if (!publish) return;
    if (pushTimerRef.current) clearTimeout(pushTimerRef.current);
    pushTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch('/api/proto/state', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ifVersion: version, state: next }) });
        if (res.status === 409) {
          const r2 = await fetch('/api/proto/state');
          const j2 = await r2.json();
          if (typeof j2.version === 'number') setVersion(j2.version);
        } else if (res.ok) {
          const j = await res.json();
          if (typeof j.version === 'number') setVersion(j.version);
        }
      } catch {}
    }, 700);
  }, [publish, version]);

  // Poll for agent updates
  React.useEffect(() => {
    let timer: any;
    const tick = async () => {
      try {
        const res = await fetch('/api/proto/state');
        if (!res.ok) return;
        const j = await res.json();
        if (typeof j.version === 'number' && j.version > version) {
          applyScene(j.state || null);
          setVersion(j.version);
        }
      } catch {}
      timer = setTimeout(tick, 1000);
    };
    timer = setTimeout(tick, 1000);
    return () => timer && clearTimeout(timer);
  }, [version]);

  // Initial load from server
  React.useEffect(() => { loadServer(); }, []);

  // Detect when the Excalidraw ref becomes available
  React.useEffect(() => {
    const t = setInterval(() => {
      const ok = !!(excalRef.current && excalRef.current.updateScene);
      setReady(ok);
      if (ok) clearInterval(t);
    }, 300);
    return () => clearInterval(t);
  }, [mountKey]);

  // Global client error capture
  React.useEffect(() => {
    const onErr = (e: any) => {
      try {
        fetch('/api/proto/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'error', where: 'window.onerror', message: String(e?.message||e), stack: String(e?.error?.stack||'') }) });
      } catch {}
    };
    const onRej = (e: any) => {
      try {
        fetch('/api/proto/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'error', where: 'unhandledrejection', message: String(e?.reason||e), stack: "" }) });
      } catch {}
    };
    window.addEventListener('error', onErr);
    window.addEventListener('unhandledrejection', onRej);
    return () => {
      window.removeEventListener('error', onErr);
      window.removeEventListener('unhandledrejection', onRej);
    };
  }, []);

  return (
    <div className="h-screen flex flex-col">
      <div className="p-2 border-b flex items-center gap-2 text-sm">
        <button className="px-2 py-1 border rounded" onClick={loadServer}>Load (server)</button>
        <button className="px-2 py-1 border rounded" onClick={saveServer}>Save (server)</button>
        <button
          className="px-2 py-1 border rounded"
          onClick={async () => {
            try {
              const api = excalRef.current;
              const scene = readScene() || { elements: [], appState: {}, files: {} };
              const baseX = 120 + Math.random()*60;
              const baseY = 120 + Math.random()*40;
              const elText: any = { id: `selftest_text_${Date.now()}`, type: 'text', x: baseX, y: baseY, text: 'SELF-TEST', fontSize: 22, width: 200, height: 32 };
              const elRect: any = { id: `selftest_rect_${Date.now()}`, type: 'rectangle', x: baseX-20, y: baseY+40, width: 220, height: 100, strokeColor: '#1f2937', backgroundColor: 'transparent' };
              const next = { elements: [...(scene.elements||[]), elText, elRect], appState: scene.appState||{}, files: scene.files||{} };
              if (api?.updateScene) api.updateScene(next); else setInitialData(next);
              let tries=0; let v=version; while (tries<2) {
                const res = await fetch('/api/proto/state', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ifVersion: v, state: next }) });
                if (res.status===409){ const r2=await fetch('/api/proto/state'); const j2=await r2.json(); v=typeof j2.version==='number'?j2.version:v; tries++; continue; }
                if (res.ok){ const j=await res.json(); if (typeof j.version==='number') setVersion(j.version); }
                break; }
            } catch {}
          }}
        >Self-Test</button>
        <span className="mx-2">|</span>
        <button className="px-2 py-1 border rounded" onClick={loadLocal}>Load (local)</button>
        <button className="px-2 py-1 border rounded" onClick={saveLocal}>Save (local)</button>
        {loading && <span className="ml-2 text-gray-500">…</span>}
        {error && <span className="ml-2 text-red-600">{error}</span>}
        <span className="ml-auto text-gray-500">{ready ? 'Canvas: ready' : 'Canvas: loading…'}</span>
        <button className="px-2 py-1 border rounded" onClick={()=>setMountKey(v=>v+1)}>Reload Canvas</button>
        <label className="flex items-center gap-2"><input type="checkbox" checked={publish} onChange={(e)=>setPublish(e.target.checked)} /> <span className="text-gray-700">Publish to Agent</span></label> <span className="text-gray-500">v{version}</span>
      </div>
      <div className="px-2 py-1 border-b text-sm flex items-center gap-2 bg-gray-50">
        <span className="text-gray-700">Icons:</span>
        {['upload','search','file-text','download','folder-plus','settings'].map((name) => (
          <button
            key={name}
            className="px-2 py-0.5 border rounded hover:bg-gray-100"
            onClick={() => {
              const tag = `[icon:${name}]`;
              const scene = readScene();
              const api = excalRef.current;
              const baseX = 80 + Math.random()*60;
              const baseY = 80 + Math.random()*40;
              const el: any = { id: `icon_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,6)}`, type: 'text', x: baseX, y: baseY, text: tag, fontSize: 20, width: 160, height: 30 };
              const next = { elements: [...(scene?.elements||[]), el], appState: scene?.appState||{}, files: scene?.files||{} };
              if (api?.updateScene) { api.updateScene(next); } else { setInitialData(next); }
              schedulePush(next);
            }}
            title={`Insert ${name}`}
          >
            {name}
          </button>
        ))}
        <span className="text-gray-500 ml-2">(exporter maps [icon:name] → lucide icon)</span>
      </div>
      <div className="flex-1 min-h-0 h-full relative" style={{ minHeight: "calc(100vh - 90px)" }}>
        <ErrorBoundary>
          <Excalidraw
            key={mountKey}
            ref={excalRef}
            initialData={initialData || undefined}
            onChange={(elements: any[], appState: any, files: any)=> schedulePush({ elements, appState, files })}
          />
        </ErrorBoundary>
      </div>
    </div>
  );
}
