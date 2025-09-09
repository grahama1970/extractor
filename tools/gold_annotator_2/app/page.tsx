'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';

const PdfViewer = dynamic(() => import('../components/PdfViewer'), { ssr: false });

export default function Page() {
  const [file, setFile] = useState<ArrayBuffer | null>(null);
  const [meta, setMeta] = useState<{ name: string; size: number } | null>(null);
  const [debugDemo, setDebugDemo] = useState(false);
  const [auto, setAuto] = useState(false);

  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    if (sp.get('sample') === '1') setAuto(true);
    if (sp.get('demo') === '1') setDebugDemo(true);
  }, []);

  useEffect(() => {
    // No-op: page is client-only
  }, []);

  return (
    <div className="container">
      {/* Explorer */}
      <div className="panel">
        <div className="header">Explorer</div>
        <div className="section">
          <div className="toolbar" style={{ marginBottom: 12 }}>
            <button className="btn" onClick={() => document.querySelector<HTMLInputElement>('[data-testid=file-input]')?.click()}>Load PDF</button>
            <input placeholder="Search PDF" className="btn" style={{ flex:1 }} />
          </div>
          <input
            data-testid="file-input"
            type="file"
            accept="application/pdf"
            style={{ display: 'none' }}
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              const buf = await f.arrayBuffer();
              setFile(buf);
              setMeta({ name: f.name, size: f.size });
            }}
          />
          <div className="toolbar" style={{ marginBottom: 8 }}>
            <button
              className="btn small"
              data-testid="load-sample"
              onClick={async () => {
                const url = 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf';
                const res = await fetch(url);
                const buf = await res.arrayBuffer();
                setFile(buf);
                setMeta({ name: 'sample.pdf', size: buf.byteLength });
              }}
            >Load Sample</button>
          </div>
        </div>
        <hr className="divider" />
        <div className="list">
          <div className="item"><span>PDF file name</span><span className="muted">export</span></div>
          <div className="item"><span>PDF file name</span><span className="muted">export</span></div>
          <div className="item"><span>PDF file name</span><span className="muted">export</span></div>
        </div>
        <div className="section">
          <button className="btn primary" style={{ width:'100%', justifyContent:'center' }}>Export All</button>
        </div>
      </div>

      {/* Annotation */}
      <div className="panel" style={{ display:'flex', flexDirection:'column' }}>
        <div className="header" style={{ color:'#ef4444', textAlign:'center' }}>Annotation</div>
        <div className="section" style={{ flex:1 }}>
          <PdfViewer fileData={file ?? undefined} fileName={meta?.name} fileSize={meta?.size} debugDemo={debugDemo} />
        </div>
      </div>

      {/* Inspector */}
      <div className="panel">
        <div className="header" style={{ color:'#ef4444' }}>Inspector</div>
        <div className="section">
          <p className="muted" style={{ margin:0 }}>Use the side panel in the center to edit labels. Shortcuts: [ / ] to navigate, f/t/s for type, Ctrl/Cmd+S to save.</p>
        </div>
      </div>

      {auto && (
        <script
          dangerouslySetInnerHTML={{
            __html: `
            (async () => {
              try {
                const url = 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf';
                const res = await fetch(url);
                const buf = await res.arrayBuffer();
                const input = document.querySelector('[data-testid="file-input"]');
                if (input) {
                  const dt = new DataTransfer();
                  // can't set File from here cross-origin in all browsers, but Load Sample exists above
                  console.log('autoload ready');
                  document.querySelector('[data-testid="load-sample"]').click();
                }
              } catch (e) { console.error('autoload failed', e); }
            })();
          `}}
        />
      )}
    </div>
  );
}
