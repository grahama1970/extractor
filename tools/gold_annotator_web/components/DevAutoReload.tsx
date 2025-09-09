"use client";
import * as React from "react";

export function DevAutoReload() {
  // Only active in development
  if (process.env.NODE_ENV !== 'development') return null as any;

  const [state, setState] = React.useState<'ok'|'waiting'|'reloading'>('ok');
  const lastOkRef = React.useRef<number>(Date.now());
  const reloadingRef = React.useRef(false);

  React.useEffect(() => {
    let mounted = true;
    const tick = async () => {
      try {
        // lightweight ping; avoids cache
        const res = await fetch(`/api/list?ping=${Date.now()}`, { cache: 'no-store' });
        if (res.ok) {
          lastOkRef.current = Date.now();
          if (mounted && state !== 'ok') setState('ok');
        } else {
          if (mounted && state === 'ok') setState('waiting');
        }
      } catch {
        if (mounted && state === 'ok') setState('waiting');
      }
      const sinceOk = Date.now() - lastOkRef.current;
      if (!reloadingRef.current && sinceOk > 8000 && mounted) {
        reloadingRef.current = true;
        setState('reloading');
        // Give the server a moment to come back, then reload
        setTimeout(() => { if (typeof window !== 'undefined') window.location.reload(); }, 1200);
      }
    };
    const id = setInterval(tick, 2000);
    return () => { mounted = false; clearInterval(id); };
  }, [state]);

  if (state === 'ok') return null;
  return (
    <div style={{ position: 'fixed', bottom: 8, right: 8, zIndex: 50 }}>
      <div className="text-xs px-2 py-1 rounded bg-yellow-600 text-white shadow">
        {state === 'waiting' ? 'Dev server disconnected… waiting' : 'Reconnecting…'}
      </div>
    </div>
  );
}

