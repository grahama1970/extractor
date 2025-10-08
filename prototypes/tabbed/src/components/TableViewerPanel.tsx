import React from 'react';
import type { Block } from '../hooks/useBundle';

interface Props {
  block?: Block;
  verifyBase?: string;
}

export const TableViewerPanel: React.FC<Props> = ({ block, verifyBase }) => {
  if (!block || block.type?.toLowerCase?.() !== 'table') {
    return <div data-testid="table-panel-empty" style={{padding:'0.5rem', fontSize:12}}>Select a table</div>;
  }
  const rawId = (block as any)['raw_table_id'] || (block as any)['table_id'] || `table_${block.block_id ?? 'x'}`;
  const viewPath = verifyBase ? `${verifyBase}/${String(rawId).replace('rawtbl_','table_')}/view.html` : undefined;
  return (
    <div style={{height:'100%', display:'flex', flexDirection:'column'}} data-testid="table-panel">
      <div style={{padding:'4px 8px', fontWeight:'bold', fontSize:12}}>
        {String(rawId)}
      </div>
      {viewPath ? (
        <iframe src={viewPath} style={{flex:1, border:'none'}} title="table-view" />
      ) : (
        <div style={{padding:'0.5rem', fontSize:12}}>No view.html found</div>
      )}
    </div>
  );
};

