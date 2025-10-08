import React from 'react';
import type { Block } from '../hooks/useBundle';

interface Props {
  width: number;
  height: number;
  blocks: Block[];
  activeTypes: Record<string, boolean>;
  opacity: number;
  labelStyle: 'tab' | 'free' | 'off';
  onTableClick?: (b: Block) => void;
}

const colorMap: Record<string,string> = {
  sectionheader: '#E5861A',
  table: '#1A78F2',
  figure: '#18A85E',
  equation: '#941AE5',
  caption: '#B06A1A',
  listitem: '#E51A64',
};

function pickColor(t: string) {
  return colorMap[t?.toLowerCase?.() ?? ''] || '#D42A2A';
}

export const OverlayCanvas: React.FC<Props> = ({
  width, height, blocks, activeTypes, opacity, labelStyle, onTableClick
}) => {
  return (
    <div style={{ position:'relative', width, height, border:'1px solid #ccc', background:'#fff' }}>
      {blocks.filter(b => activeTypes[b.type] !== false).map(b => {
        const [x0,y0,x1,y1] = b.bbox;
        const w = Math.max(0, x1 - x0);
        const h = Math.max(0, y1 - y0);
        const color = pickColor(b.type);
        const label = `${b.type}${b.block_id !== undefined ? ':'+b.block_id : ''}`;
        const isTable = b.type?.toLowerCase?.() === 'table';
        return (
          <div
            key={`b-${b.mini_hash}`}
            data-testid={`block-${b.mini_hash}`}
            onClick={() => isTable && onTableClick?.(b)}
            style={{
              position:'absolute', left:x0, top:y0, width:w, height:h,
              boxSizing:'border-box', border:`1.5px solid ${color}`,
              background: labelStyle==='off' ? 'transparent' : `rgba(255,255,255,${opacity})`,
              cursor: isTable ? 'pointer' : 'default'
            }}
            title={b.text?.slice(0,200)}
          >
            {labelStyle!=='off' && (
              <div style={{
                position: labelStyle==='tab' ? 'absolute':'static',
                top: labelStyle==='tab' ? -14:0,
                right: labelStyle==='tab' ? 0: undefined,
                background: color, color:'#fff', fontSize:10, padding:'0 3px',
                whiteSpace:'nowrap', maxWidth:120, overflow:'hidden', textOverflow:'ellipsis'
              }}>
                {label}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

