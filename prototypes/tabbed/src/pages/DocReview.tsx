import React, { useMemo, useState } from 'react';
import { useBundle } from '../hooks/useBundle';
import { OverlayCanvas } from '../components/OverlayCanvas';
import { TableViewerPanel } from '../components/TableViewerPanel';

interface Props {
  bundleUrl: string;
  verifyDir?: string;
}

export const DocReview: React.FC<Props> = ({ bundleUrl, verifyDir }) => {
  const { data, loading, error } = useBundle(bundleUrl);
  const [labelStyle, setLabelStyle] = useState<'tab'|'free'|'off'>('tab');
  const [opacity, setOpacity] = useState(0.12);
  const [activeTypes, setActiveTypes] = useState<Record<string, boolean>>({});
  const [page, setPage] = useState(0);
  const [tableBlock, setTableBlock] = useState<any>(null);

  const pages = useMemo(() => {
    if (!data?.blocks?.length) return 0;
    return Math.max(...data.blocks.map(b => b.page || 0)) + 1;
  }, [data]);

  const pageBlocks = useMemo(() => {
    if (!data) return [] as any[];
    return data.blocks.filter(b => (b.page || 0) === page);
  }, [data, page]);

  if (loading) return <div>Loading bundle…</div>;
  if (error) return <div>Error: {error}</div>;
  if (!data) return <div>No data</div>;

  const toggleType = (t: string) => {
    setActiveTypes(prev => ({ ...prev, [t]: prev[t] === false }));
  };

  const allTypes = Array.from(new Set(data.blocks.map(b => b.type))).sort();

  return (
    <div style={{display:'flex', height:'100%', gap:'1rem'}}>
      <div style={{width:260, borderRight:'1px solid #ccc', padding:'0.5rem', overflowY:'auto'}}>
        <h3 style={{marginTop:0}}>{data.doc_id || 'Document'}</h3>
        <div style={{fontSize:11, opacity:0.7}}>Pages: {pages}</div>
        <hr/>
        <div>
          <label style={{fontSize:11}}>Page:</label>
          <input type="number" min={0} max={Math.max(0,pages-1)} value={page} onChange={e => setPage(parseInt(e.target.value)||0)} style={{width:60,marginLeft:4}}/>
        </div>
        <div style={{marginTop:8}}>
          <strong style={{fontSize:12}}>Label Style</strong><br/>
          {['tab','free','off'].map(s => (
            <label key={s} style={{fontSize:11, marginRight:6}}>
              <input type="radio" name="labelStyle" value={s} checked={labelStyle===s} onChange={()=>setLabelStyle(s as any)} /> {s}
            </label>
          ))}
        </div>
        <div style={{marginTop:8}}>
          <strong style={{fontSize:12}}>Opacity</strong>
          <input type="range" min={0} max={0.3} step={0.01} value={opacity} onChange={e=>setOpacity(parseFloat(e.target.value))} />
          <div style={{fontSize:10}}>{opacity.toFixed(2)}</div>
        </div>
        <div style={{marginTop:8}}>
          <strong style={{fontSize:12}}>Types</strong>
          <div style={{display:'flex', flexWrap:'wrap', gap:4}}>
            {allTypes.map(t => {
              const off = activeTypes[t] === false;
              return (
                <button key={t} onClick={()=>toggleType(t)} style={{
                  fontSize:10, padding:'2px 4px', border:'1px solid #666',
                  background: off ? '#eee':'#cfe2ff', cursor:'pointer'
                }}>{t}</button>
              );
            })}
          </div>
        </div>
        <div style={{marginTop:10}}>
          <strong style={{fontSize:12}}>Suspects</strong>
          <div style={{fontSize:11}}>
            suspicious_total: {data.suspects?.suspicious_total ?? '–'}<br/>
            coverage_ratio: {data.suspects?.coverage_ratio ?? data.suspects?.counters?.coverage_ratio ?? '–'}
          </div>
        </div>
      </div>
      <div style={{flex:1, overflow:'auto', position:'relative'}}>
        <OverlayCanvas
          width={800}
          height={1100}
          blocks={pageBlocks as any}
          activeTypes={activeTypes}
          opacity={opacity}
          labelStyle={labelStyle}
          onTableClick={b => setTableBlock(b)}
        />
      </div>
      <div style={{width:320, borderLeft:'1px solid #ccc', display:'flex', flexDirection:'column'}}>
        <TableViewerPanel block={tableBlock} verifyBase={verifyDir} />
      </div>
    </div>
  );
};

