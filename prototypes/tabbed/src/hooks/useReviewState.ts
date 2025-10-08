import { useEffect, useState } from 'react';
import type { Block } from './useBundle';

export type Decision = 'accept' | 'reject' | 'needs-fix';

export interface ReviewDecision {
  block_id?: number;
  mini_hash: string;
  decision: Decision;
  comment?: string;
  page: number;
  type: string;
}

export function useReviewState(docId: string | undefined) {
  const storageKey = docId ? `review_state_${docId}` : undefined;
  const [decisions, setDecisions] = useState<Record<string, ReviewDecision>>({});

  useEffect(() => {
    if (!storageKey) return;
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) setDecisions(JSON.parse(raw));
    } catch {
      // ignore
    }
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(decisions));
    } catch {
      // ignore
    }
  }, [storageKey, decisions]);

  const setDecision = (block: Block, decision: Decision | null, comment?: string) => {
    setDecisions(prev => {
      const next = { ...prev } as Record<string, ReviewDecision>;
      const key = block.mini_hash;
      if (!decision) {
        delete next[key];
      } else {
        next[key] = {
          block_id: block.block_id,
          mini_hash: block.mini_hash,
          decision,
          comment,
          page: block.page,
          type: block.type,
        };
      }
      return next;
    });
  };

  return { decisions, setDecision };
}

export function exportReview(docId: string | undefined, decisions: Record<string, ReviewDecision>) {
  const list = Object.values(decisions);
  const payload = {
    doc_id: docId,
    exported_at: new Date().toISOString(),
    count: list.length,
    decisions: list,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${docId || 'document'}_review_${Date.now()}.json`;
  a.click();
}

