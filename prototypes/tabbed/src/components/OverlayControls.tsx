import React from 'react';

export interface OverlayConfig {
  labelStyle: 'tab' | 'free' | 'off';
  palette: 'default' | 'colorblind-safe';
  opacity: number;
  types: Record<string, boolean>;
}

interface Props {
  config: OverlayConfig;
  onChange(cfg: OverlayConfig): void;
}

export const OverlayControls: React.FC<Props> = ({ config, onChange }) => {
  const update = (partial: Partial<OverlayConfig>) =>
    onChange({ ...config, ...partial });

  const toggleType = (t: string) =>
    update({
      types: { ...config.types, [t]: !config.types[t] },
    });

  return (
    <div style={{ width: 280, borderRight: '1px solid #ddd', padding: '0.75rem', overflowY: 'auto' }} data-testid="overlay-controls">
      <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Overlay Controls</h2>

      <section>
        <h3 style={{ fontSize: '0.9rem' }}>Block Types</h3>
        {Object.keys(config.types).map(t => (
          <label key={t} style={{ display: 'block', fontSize: '.8rem' }} data-testid={`toggle-type-${t}`}>
            <input
              type="checkbox"
              checked={config.types[t]}
              onChange={() => toggleType(t)}
            />{' '}
            {t}
          </label>
        ))}
      </section>

      <section>
        <h3 style={{ fontSize: '0.9rem' }}>Label Style</h3>
        {['tab', 'free', 'off'].map(s => (
          <label key={s} style={{ display: 'inline-block', marginRight: '0.5rem', fontSize: '.8rem' }} data-testid={`label-style-${s}`}>
            <input
              type="radio"
              name="labelStyle"
              value={s}
              checked={config.labelStyle === s}
              onChange={() => update({ labelStyle: s as any })}
            />{' '}
            {s}
          </label>
        ))}
      </section>

      <section>
        <h3 style={{ fontSize: '0.9rem' }}>Opacity</h3>
        <input
          data-testid="opacity-slider"
          type="range"
          min={0}
          max={0.3}
          step={0.01}
          value={config.opacity}
          onChange={e => update({ opacity: parseFloat(e.target.value) })}
        />
        <div data-testid="opacity-value" style={{ fontSize: '.75rem' }}>{config.opacity.toFixed(2)}</div>
      </section>

      <section>
        <h3 style={{ fontSize: '0.9rem' }}>Palette</h3>
        <select
          data-testid="palette-select"
          value={config.palette}
          onChange={e => update({ palette: e.target.value as any })}
        >
          <option value="default">default</option>
          <option value="colorblind-safe">colorblind-safe</option>
        </select>
      </section>

      <section>
        <h3 style={{ fontSize: '0.9rem' }}>Table Viewer</h3>
        <p style={{ fontSize: '.7rem', lineHeight: 1.2 }}>
          Clicking a table region (in integrated viewer) should open its
          <code> view.html</code> in the side panel (placeholder here).
        </p>
      </section>
    </div>
  );
};

