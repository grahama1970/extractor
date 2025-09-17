import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { LoaderDots } from '@/components/ui/loader';
import { toast } from '@/components/ui/sonner';

type PdfItem = { name: string; rel: string; size?: number };

export default function ExtractPage() {
  const [items, setItems] = useState<PdfItem[]>([]);
  const [job, setJob] = useState<{ id: string; status: string } | null>(null);
  useEffect(() => {
    (async () => {
      try { const r = await fetch('/api/list'); const j = await r.json(); if (j?.ok) setItems(j.items || []); } catch {}
    })();
  }, []);
  useEffect(() => {
    if (!job?.id) return;
    let cancelled=false; const t = setInterval(async () => {
      try { const r = await fetch(`/api/pipeline/status?job_id=${encodeURIComponent(job.id)}`); const j = await r.json(); if (j?.ok && !cancelled) { setJob({ id: j.job.id, status: j.job.status }); if (j.job.status==='done'||j.job.status==='error') clearInterval(t); } } catch {}
    }, 1000);
    return () => { cancelled=true; clearInterval(t); };
  }, [job?.id]);
  const runExtraction = async (rel: string) => {
    try {
      const r = await fetch('/api/pipeline/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rel }) });
      const j = await r.json();
      if (j?.ok && j.job_id) { setJob({ id: j.job_id, status: 'queued' }); toast('Extraction started'); }
      else toast.error(j?.error || 'Failed to start');
    } catch { toast.error('Failed to start'); }
  };
  const openResult = async () => {
    if (!job?.id) return;
    try { const r = await fetch(`/api/pipeline/result?job_id=${encodeURIComponent(job.id)}`); const j = await r.json(); if (j?.ok && j.result?.out_dir) { const href = `/api/artifacts/browse?dir=${encodeURIComponent(j.result.out_dir)}`; window.open(href, '_blank'); } else toast('Not done yet'); } catch { toast.error('Failed'); }
  };
  return (
    <div className="min-h-screen">
      <header className="h-16 border-b bg-card flex items-center px-6">
        <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground"><span>←</span> Back</Link>
        <div className="flex-1 text-center"><h1 className="text-lg font-semibold">Extract</h1></div>
      </header>
      <main className="p-6 space-y-4">
        <div className="text-sm text-muted-foreground">Run the extraction pipeline on a PDF and inspect artifacts.</div>
        <Separator />
        <div className="grid gap-2">
          {items.map(it => (
            <div key={it.rel} className="flex items-center justify-between border rounded p-2 bg-card">
              <div className="min-w-0"><div className="truncate font-medium">{it.name}</div><div className="text-xs text-muted-foreground">{it.size ? Math.round(it.size/1024) + ' KB' : ''}</div></div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => runExtraction(it.rel)}>Run Extraction</Button>
                <Link to={`/classic`} className="text-sm underline">Annotate</Link>
              </div>
            </div>
          ))}
        </div>
        {job && (
          <div className="fixed bottom-4 right-4 bg-card/95 border rounded-full px-3 py-1 text-xs shadow flex items-center gap-2">
            <LoaderDots /> <span>Job {job.id}: {job.status}</span>
            <Button size="sm" variant="ghost" onClick={openResult}>Open Result</Button>
          </div>
        )}
      </main>
    </div>
  );
}
