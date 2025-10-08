import React, { useState } from 'react';
import { OverlayControls, OverlayConfig } from './components/OverlayControls';

export const App: React.FC = () => {
  const [config, setConfig] = useState<OverlayConfig>({
    labelStyle: 'tab',
    palette: 'default',
    opacity: 0.12,
    types: {
      SectionHeader: true,
      Text: true,
      Table: true,
      Figure: true,
      ListItem: true,
      Equation: true,
      Caption: true,
    },
  });

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'sans-serif' }}>
      <OverlayControls config={config} onChange={setConfig} />
      <div style={{ flex: 1, padding: '1rem', overflow: 'auto' }}>
        <h1 data-testid="viewer-title">PDF Viewer Placeholder</h1>
        <p>Use the panel to the left to toggle overlay options.</p>
        <pre data-testid="config-json">{JSON.stringify(config, null, 2)}</pre>
        <div data-testid="table-viewer-panel" style={{ border:'1px solid #ccc', marginTop:'1rem', padding:'0.5rem' }}>
          <strong>Table view.html iframe placeholder</strong>
        </div>
      </div>
    </div>
  );
};

