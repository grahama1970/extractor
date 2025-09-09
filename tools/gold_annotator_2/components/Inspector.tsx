'use client';

import { useEffect, useMemo, useState } from 'react';
import type { Box } from '../lib/types';

const LABELS = ['Section', 'Table', 'Field'];

type Props = {
  box: Box | null;
  onChange: (b: Box) => void;
  onDuplicate?: (b: Box) => void;
};

export default function Inspector({ box, onChange, onDuplicate }: Props) {
  const [instanceId, setInstanceId] = useState('');
  const [labelType, setLabelType] = useState('Section');
  const [notes, setNotes] = useState('');

  useEffect(() => {
    setInstanceId(box?.instanceId || '');
    setLabelType(box?.labelType || 'Section');
    setNotes(box?.notes || '');
  }, [box?.id]);

  if (!box) {
    return (
      <div style={{ padding: 12, color: '#666' }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Inspector</div>
        <div>Select a box to edit label</div>
      </div>
    );
  }

  return (
    <div style={{ padding: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 12 }}>Inspector</div>

      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'block', fontSize: 12, color: '#555' }}>Label Type</label>
        <select
          value={labelType}
          onChange={(e) => {
            const v = e.target.value;
            setLabelType(v);
            onChange({ ...box, labelType: v });
          }}
          style={{ width: '100%' }}
        >
          {LABELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'block', fontSize: 12, color: '#555' }}>Instance ID</label>
        <input
          value={instanceId}
          onChange={(e) => {
            const v = e.target.value;
            setInstanceId(v);
            onChange({ ...box, instanceId: v });
          }}
          style={{ width: '100%' }}
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'block', fontSize: 12, color: '#555' }}>Notes</label>
        <textarea
          value={notes}
          onChange={(e) => {
            const v = e.target.value;
            setNotes(v);
            onChange({ ...box, notes: v });
          }}
          rows={5}
          style={{ width: '100%' }}
        />
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={() => {
            if (onDuplicate) onDuplicate({ ...box, id: `b_${Date.now().toString(36)}` });
          }}
        >
          Duplicate
        </button>
      </div>
    </div>
  );
}

