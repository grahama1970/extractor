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

