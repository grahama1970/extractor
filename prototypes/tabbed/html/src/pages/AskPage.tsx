/**
 * AskPage — Persona-aware query interface for the datalake.
 *
 * Supports both general chat (original /api/chat/query) and persona-weighted
 * datalake queries (via datalake_api.py). Persona is set via PersonaContext (shell header).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { toast } from '@/components/ui/sonner';
import { Loader2, MessageSquare, Search } from 'lucide-react';
import { personaQuery, fetchPersonas, type PersonaQueryResponse, type PersonaWeights } from '@/lib/datalake';
import { usePersona } from '@/contexts/PersonaContext';
import { PERSONAS, sortDimensions } from '@/lib/persona-config';

type Message = {
  role: 'user' | 'assistant';
  content: string;
  citations?: Array<{ page?: number; type?: string; stem?: string }>;
  persona?: string;
  personaResults?: PersonaQueryResponse;
};

// --- Dimension score bar ---

function DimBar({ label, score }: { label: string; score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "bg-green-500" : score >= 0.6 ? "bg-yellow-500" : "bg-destructive";
  return (
    <div className="flex items-center gap-1.5 text-[10px]">
      <span className="w-20 truncate text-muted-foreground">{label.replace(/_/g, ' ')}</span>
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono w-8 text-right">{pct}%</span>
    </div>
  );
}

// --- Main component ---

export default function AskPage() {
  const navigate = useNavigate();
  const { persona, config, distance } = usePersona();
  const isTv = distance === "tv";
  const [messages, setMessages] = useState<Message[]>([]);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(false);
  const [personas, setPersonas] = useState<PersonaWeights | null>(null);
  const [sessionId] = useState(() => `s-${Date.now()}`);

  // Load available personas
  useEffect(() => {
    fetchPersonas().then(setPersonas).catch(() => {});
  }, []);

  // Sorted dimensions for the active persona
  const dimOrder = sortDimensions(persona);

  const send = useCallback(async () => {
    const text = q.trim();
    if (!text) return;
    setMessages((m) => [...m, { role: 'user', content: text }]);
    setQ('');
    setLoading(true);

    try {
      // Persona-weighted datalake query
      const result = await personaQuery({ query: text, persona, k: 15 });

      // Format response text from results
      let content = `**${config.label}** analyzed ${result.result_count} results:\n\n`;
      if (result.results.length === 0) {
        content += "No matching documents found in the datalake.";
      } else {
        for (const r of result.results.slice(0, 5)) {
          const score = r.persona_score != null ? ` (score: ${Math.round(r.persona_score * 100)}%)` : '';
          const textPreview = (r.text ?? '').slice(0, 200);
          const meta = r.metadata ?? {};
          const src = (meta.source_pdf as string) ?? '';
          content += `- **${src}**${score}\n  ${textPreview}...\n\n`;
        }
      }

      // Build citations from results
      const citations = result.results.slice(0, 10).map((r) => ({
        stem: ((r.metadata ?? {}).source_pdf as string) ?? '',
        page: (r.metadata ?? {}).page_num as number | undefined,
        type: ((r.metadata ?? {}).asset_type as string) ?? 'text',
      }));

      setMessages((m) => [...m, {
        role: 'assistant',
        content,
        citations,
        persona,
        personaResults: result,
      }]);
    } catch {
      toast.error('Query failed');
    } finally {
      setLoading(false);
    }
  }, [q, persona, config, sessionId]);

  // TV: centered large input with latest response shown big
  if (isTv) {
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
    return (
      <div className="h-full flex flex-col items-center justify-center gap-6 p-8">
        <MessageSquare className="h-16 w-16 text-persona opacity-40" />
        <p className="text-2xl font-medium">
          Ask <span className="text-persona">{config.label}</span>
        </p>
        {/* Last response — large text */}
        {lastAssistant && (
          <Card className="w-full max-w-3xl p-6">
            <p className="text-base whitespace-pre-wrap leading-relaxed line-clamp-6">{lastAssistant.content}</p>
          </Card>
        )}
        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="text-lg">Searching...</span>
          </div>
        )}
        <div className="flex items-center gap-3 w-full max-w-3xl">
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={`Ask ${config.label} about the datalake...`}
            onKeyDown={(e) => { if (e.key === "Enter" && !loading) send(); }}
            disabled={loading}
            className="h-14 text-xl"
          />
          <Button onClick={send} disabled={loading || !q.trim()} className="h-14 px-8 text-lg">
            {loading ? <Loader2 className="h-6 w-6 animate-spin" /> : "Send"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-4">
      {/* Persona focus info */}
      <div className="text-xs text-muted-foreground">
        <span className="font-medium text-persona">{config.label}</span> — {config.focus}
        {personas?.[persona] && (
          <span className="ml-2">
            Weights: {dimOrder.map((k) => `${k.replace(/_/g, ' ')}: ${Math.round((personas[persona][k] ?? 0) * 100)}%`).join(', ')}
          </span>
        )}
      </div>

      <Separator />

      {/* Messages */}
      <div className="border rounded-lg bg-card min-h-[40vh] max-h-[60vh] overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Search className="h-8 w-8 mb-2 opacity-40" />
            <p className="text-sm">Ask a question about your extracted documents</p>
            <p className="text-xs mt-1">Persona weighting applied via <span className="text-persona font-medium">{config.label}</span></p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`${m.role === 'user' ? '' : 'bg-muted/50 rounded-lg p-3'}`}>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-semibold ${m.role === 'user' ? 'text-primary' : 'text-persona'}`}>
                {m.role === 'user' ? 'You' : (m.persona ? PERSONAS[m.persona as keyof typeof PERSONAS]?.label ?? 'Assistant' : 'Assistant')}
              </span>
            </div>
            <div className="text-sm whitespace-pre-wrap">{m.content}</div>

            {/* Persona dimension scores — sorted by persona weight */}
            {m.personaResults && m.personaResults.results.length > 0 && (
              <Card className="mt-2 p-2">
                <h4 className="text-[10px] font-semibold text-muted-foreground mb-1">Dimension Weights Applied</h4>
                <div className="space-y-0.5">
                  {dimOrder
                    .filter((dim) => dim in m.personaResults!.weights)
                    .map((dim) => (
                      <div key={dim} className="flex items-center gap-1 text-[9px]">
                        <span className="w-24 truncate text-muted-foreground">{dim.replace(/_/g, ' ')}</span>
                        <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
                          <div className="h-full rounded-full bg-persona" style={{ width: `${m.personaResults!.weights[dim] * 100}%` }} />
                        </div>
                        <span className="font-mono w-6 text-right">{Math.round(m.personaResults!.weights[dim] * 100)}%</span>
                      </div>
                    ))}
                </div>
              </Card>
            )}

            {/* Citations */}
            {m.citations && m.citations.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {m.citations.map((c, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      if (c.stem) {
                        const params = new URLSearchParams({ stem: c.stem });
                        if (c.page != null) params.set("page", String(c.page));
                        navigate(`/review?${params}`);
                      }
                    }}
                    className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-muted text-[10px] hover:bg-accent transition-colors"
                  >
                    {c.stem && <span className="font-medium truncate max-w-[120px]">{c.stem}</span>}
                    {c.page != null && <span className="text-muted-foreground">p.{c.page}</span>}
                    {c.type && <Badge variant="outline" className="text-[8px] px-0.5 py-0">{c.type}</Badge>}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-xs">Searching...</span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex items-center gap-2">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={`Ask ${config.label} about the datalake...`}
          onKeyDown={(e) => { if (e.key === 'Enter' && !loading) send(); }}
          disabled={loading}
        />
        <Button onClick={send} disabled={loading || !q.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send"}
        </Button>
      </div>
    </div>
  );
}
