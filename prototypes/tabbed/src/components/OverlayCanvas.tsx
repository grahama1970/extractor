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
  selected?: string | null;
  decisions?: Record<string, { decision: string }>;
  onSelect?: (b: Block) => void;
  diffMap?: {
    added: Set<string>;
    changed: Set<string>;
    unchanged: Set<string>;
  } | null;
  diffMode?: boolean;
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
  width, height, blocks, activeTypes, opacity, labelStyle,
  onTableClick, selected, decisions, onSelect, diffMap, diffMode
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
        const isSelected = selected === b.mini_hash;
        const dec = decisions?.[b.mini_hash]?.decision;
        let ring = dec === 'accept' ? '2px solid #18a85e'
          : dec === 'reject' ? '2px solid #d42a2a'
          : dec === 'needs-fix' ? '2px solid #e0b000'
          : `1.5px solid ${color}`;
        if (diffMode && diffMap) {
          if (diffMap.added?.has(b.mini_hash)) {
            ring = '2px solid #008cdd';
          } else if (diffMap.changed?.has(b.mini_hash)) {
            ring = '2px solid #ff7f00';
          }
        }
        return (
          <div
            key={`b-${b.mini_hash}`}
            data-testid={`block-${b.mini_hash}`}
            onClick={() => { if (isTable) onTableClick?.(b); onSelect?.(b); }}
            style={{
              position:'absolute', left:x0, top:y0, width:w, height:h,
              boxSizing:'border-box', border:ring,
              outline: isSelected ? '2px dashed #222' : undefined,
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
