import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { toast } from '@/components/ui/sonner';

type Message = { role: 'user'|'assistant'; content: string; citations?: any[] };

export default function AskPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [q, setQ] = useState('');
  const [sessionId] = useState(() => `s-${Date.now()}`);

  const send = async () => {
    const text = q.trim(); if (!text) return;
    setMessages(m => [...m, { role:'user', content: text }]); setQ('');
    try {
      const r = await fetch('/api/chat/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, q: text })});
      const j = await r.json();
      if (j?.ok) setMessages(m => [...m, { role:'assistant', content: j.answer || '', citations: j.citations || [] }]);
      else toast.error(j?.error || 'Query failed');
    } catch { toast.error('Query failed'); }
  };

  return (
    <div className="min-h-screen">
      <header className="h-16 border-b bg-card flex items-center px-6">
        <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground"><span>←</span> Back</Link>
        <div className="flex-1 text-center"><h1 className="text-lg font-semibold">Ask</h1></div>
      </header>
      <main className="p-6 space-y-4">
        <div className="text-sm text-muted-foreground">Ask questions across extracted PDFs. Answers include citations to relevant pages.</div>
        <Separator />
        <div className="space-y-3">
          <div className="border rounded p-3 bg-card min-h-[30vh]">
            {messages.length===0 && (<div className="text-sm text-muted-foreground">No messages yet. Ask a question below.</div>)}
            {messages.map((m, i) => (
              <div key={i} className="my-2">
                <div className={m.role==='user'?'font-medium':'text-foreground'}>{m.role==='user'?'You':'Assistant'}</div>
                <div className="text-sm whitespace-pre-wrap">{m.content}</div>
                {m.citations?.length ? (
                  <div className="text-xs text-muted-foreground mt-1">Citations: {m.citations.map((c:any, idx:number)=> <span key={idx} className="mr-2">P.{c.page} ({c.type})</span>)}</div>
                ) : null}
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Input value={q} onChange={e=>setQ(e.target.value)} placeholder="Ask a question…" onKeyDown={(e)=>{ if (e.key==='Enter') send(); }} />
            <Button onClick={send}>Send</Button>
          </div>
        </div>
      </main>
    </div>
  );
}
