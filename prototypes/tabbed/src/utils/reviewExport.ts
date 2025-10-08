export interface ReviewDecision {
  block_id: number | string;
  decision: 'accept'|'reject'|'needs-fix';
  comment?: string;
  mini_hash?: string;
}

export function exportReview(docId: string | undefined, decisions: ReviewDecision[]) {
  const payload = {
    doc_id: docId || 'document',
    exported_at: new Date().toISOString(),
    decisions
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${docId || 'document'}_review_${Date.now()}.json`;
  a.click();
}

