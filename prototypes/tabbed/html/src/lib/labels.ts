export type LabelDef = {
  id: string; // display name & type id
  icon: string; // lucide icon name (for future use)
  color: string; // tailwind token like 'annotation-section'
  description?: string;
};

export const DEFAULT_LABELS: LabelDef[] = [
  { id: 'Section', icon: 'Heading', color: 'annotation-section', description: 'Section header' },
  { id: 'Table', icon: 'Table', color: 'annotation-table', description: 'Data table' },
  { id: 'Figure', icon: 'Image', color: 'annotation-figure', description: 'Figure or image' },
];

const LS_KEY = 'anno_labels';

export function loadLabels(): LabelDef[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    const extra: LabelDef[] = raw ? JSON.parse(raw) : [];
    const map = new Map<string, LabelDef>();
    for (const l of DEFAULT_LABELS) map.set(l.id.toLowerCase(), l);
    for (const l of extra) map.set(l.id.toLowerCase(), l);
    return Array.from(map.values());
  } catch {
    return DEFAULT_LABELS.slice();
  }
}

export function saveLabel(newLabel: LabelDef): { ok: boolean; reason?: string } {
  try {
    const existing = loadLabels();
    if (existing.find((l) => l.id.toLowerCase() === newLabel.id.toLowerCase())) {
      return { ok: false, reason: 'duplicate' };
    }
    const extra = (JSON.parse(localStorage.getItem(LS_KEY) || '[]') as LabelDef[]);
    extra.push(newLabel);
    localStorage.setItem(LS_KEY, JSON.stringify(extra));
    return { ok: true };
  } catch {
    return { ok: false, reason: 'storage' };
  }
}

// --- Calibration MVP: submit label to backend ---
export type SubmitLabelParams = {
  docId: string;
  objectType: 'table' | 'section' | 'figure' | 'equation' | 'entity';
  objectId: string;
  structureCorrect: boolean;
  cellAccuracy?: number | null;
  notes?: string;
  pageIndices?: number[];
  originalPrediction?: Record<string, unknown>;
  userId?: string;
};

export async function submitLabel(params: SubmitLabelParams): Promise<{ status: string; event_id: string } | { ok: boolean; event_id?: string }>{
  const payload = {
    doc_id: params.docId,
    object_type: params.objectType,
    object_id: params.objectId,
    gold_label: {
      structure_correct: params.structureCorrect,
      cell_accuracy: params.cellAccuracy ?? null,
      notes: params.notes ?? ''
    },
    context: {
      page_indices: params.pageIndices ?? [],
      source_stage: '05_table_extractor'
    },
    original_prediction: params.originalPrediction ?? {},
    user_id: params.userId ?? (typeof (window as any) !== 'undefined' && (window as any).CURRENT_USER) || 'internal'
  };
  const res = await fetch('/api/labels', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    // Keep legacy shape fallback
    return { ok: false };
  }
  return res.json();
}
