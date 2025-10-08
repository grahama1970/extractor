import React, { useMemo, useState, useEffect } from 'react';
import { useBundle } from '../hooks/useBundle';
import { OverlayCanvas } from '../components/OverlayCanvas';
import { TableViewerPanel } from '../components/TableViewerPanel';
import { useReviewState, exportReview } from '../hooks/useReviewState';
import { useDiff } from '../hooks/useDiff';
import { ReasoningPanel } from '../components/ReasoningPanel';

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
  const [selectedBlock, setSelectedBlock] = useState<any>(null);
  const { decisions, setDecision } = useReviewState(data?.doc_id);
  const { baseline, diff, loadBaselineFile, recompute } = useDiff();
  const [filterMode, setFilterMode] = useState<'all'|'suspicious'|'undecided'|'decided'>('all');
  const [diffMode, setDiffMode] = useState(false);

  const pages = useMemo(() => {
    if (!data?.blocks?.length) return 0;
    return Math.max(...data.blocks.map(b => b.page || 0)) + 1;
  }, [data]);

  const pageBlocks = useMemo(() => {
    if (!data) return [] as any[];
    let subset = data.blocks.filter(b => (b.page || 0) === page);
    if (filterMode === 'suspicious') {
      subset = subset.filter(b => (b as any).is_suspicious || (b as any).suspicious);
    } else if (filterMode === 'undecided') {
      subset = subset.filter(b => !decisions[b.mini_hash]);
    } else if (filterMode === 'decided') {
      subset = subset.filter(b => !!decisions[b.mini_hash]);
    }
    return subset;
  }, [data, page, filterMode, decisions]);

  if (loading) return <div>Loading bundle…</div>;
  if (error) return <div>Error: {error}</div>;
  if (!data) return <div>No data</div>;

  useEffect(() => {
    if (baseline) recompute(data.blocks);
  }, [baseline, data.blocks, recompute]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target && (e.target as HTMLElement).tagName === 'INPUT') return;
      if (e.key === '[') { setPage(p => Math.max(0, p - 1)); return; }
      if (e.key === ']') { setPage(p => Math.min(pages - 1, p + 1)); return; }
      if (!selectedBlock) return;
      switch (e.key) {
        case 'a': setDecision(selectedBlock, 'accept'); break;
        case 'r': setDecision(selectedBlock, 'reject'); break;
        case 'f': setDecision(selectedBlock, 'needs-fix'); break;
        case 'c': setDecision(selectedBlock, null); break;
        case 'ArrowDown': {
          const idx = pageBlocks.findIndex(b => b.mini_hash === selectedBlock.mini_hash);
          if (idx >= 0 && idx < pageBlocks.length - 1) setSelectedBlock(pageBlocks[idx+1]);
          break;
        }
        case 'ArrowUp': {
          const idx = pageBlocks.findIndex(b => b.mini_hash === selectedBlock.mini_hash);
          if (idx > 0) setSelectedBlock(pageBlocks[idx-1]);
          break;
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectedBlock, pageBlocks, pages, setDecision]);

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
        <div style={{marginTop:10}}>
          <strong style={{fontSize:12}}>Filters</strong>
          <div style={{display:'flex', flexWrap:'wrap', gap:4, marginTop:4}}>
            {(['all','suspicious','undecided','decided'] as const).map(f => (
              <button
                key={f}
                onClick={()=>setFilterMode(f)}
                style={{ fontSize:10, padding:'2px 5px', border:'1px solid #666', background: filterMode===f ? '#bcdfff':'#eee' }}
              >{f}</button>
            ))}
          </div>
        </div>
        <div style={{marginTop:10}}>
          <strong style={{fontSize:12}}>Diff</strong><br/>
          <label style={{fontSize:11}}>
            <input type="checkbox" checked={diffMode} onChange={e=>setDiffMode(e.target.checked)} /> enable diff
          </label>
          <div style={{marginTop:4}}>
            <input type="file" accept=".json,application/json" style={{fontSize:10}} onChange={e=>{ const f = e.target.files?.[0]; if (f) loadBaselineFile(f, data.blocks); }} />
          </div>
          {diff && diffMode && (
            <div style={{fontSize:10, marginTop:4, lineHeight:1.3}}>
              added: {diff.added.size}<br/>
              changed: {diff.changed.size}<br/>
              removed: {diff.baselineOnlyCount}<br/>
              unchanged: {diff.unchanged.size}
            </div>
          )}
        </div>
        <div style={{marginTop:10}}>
          <strong style={{fontSize:12}}>Gold (PDF Annotations)</strong><br/>
          <label style={{fontSize:11}}>
            <input type="checkbox" checked={showGold} onChange={e=>setShowGold(e.target.checked)} /> show gold overlay
          </label>
          <div style={{fontSize:11, marginTop:4}}>gold items: {(data as any).counts?.gold ?? ((data as any).gold?.length || 0)}</div>
        </div>
        <hr/>
        <div>
          <strong style={{fontSize:12}}>Review</strong>
          <div style={{fontSize:11, marginTop:4}}>Decisions: {Object.keys(decisions).length}</div>
          <div style={{display:'flex', gap:4, flexWrap:'wrap', marginTop:4}}>
            <button disabled={!selectedBlock} onClick={()=> selectedBlock && setDecision(selectedBlock,'accept')} style={{fontSize:10}}>Accept</button>
            <button disabled={!selectedBlock} onClick={()=> selectedBlock && setDecision(selectedBlock,'reject')} style={{fontSize:10}}>Reject</button>
            <button disabled={!selectedBlock} onClick={()=> selectedBlock && setDecision(selectedBlock,'needs-fix')} style={{fontSize:10}}>Needs‑Fix</button>
            <button disabled={!selectedBlock} onClick={()=> selectedBlock && setDecision(selectedBlock,null)} style={{fontSize:10}}>Clear</button>
          </div>
          <button style={{marginTop:6, fontSize:11}} onClick={()=> exportReview(data.doc_id, decisions)}>Export Review JSON</button>
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
          selected={selectedBlock?.mini_hash || null}
          decisions={Object.fromEntries(Object.entries(decisions).map(([k,v]) => [k,{decision:v.decision}]))}
          onSelect={b => setSelectedBlock(b)}
          diffMap={diffMode ? diff : null}
          diffMode={diffMode}
        />
        {showGold && Array.isArray((data as any).gold) && (
          <GoldOverlay items={(data as any).gold} page={page} />
        )}
      </div>
      <div style={{width:360, borderLeft:'1px solid #ccc', display:'flex', flexDirection:'column'}}>
        <TableViewerPanel block={tableBlock} verifyBase={verifyDir} />
        {selectedBlock && (
          <div style={{borderTop:'1px solid #ccc', padding:'4px 6px', fontSize:11}}>
            <strong>Selected</strong><br/>
            {selectedBlock.type}:{selectedBlock.block_id} p.{selectedBlock.page}<br/>
            hash={selectedBlock.mini_hash}
          </div>
        )}
        <div style={{borderTop:'1px solid #ccc', flex:'1 1 auto', overflowY:'auto'}}>
          <ReasoningPanel block={selectedBlock} />
        </div>
      </div>
    </div>
  );
};
