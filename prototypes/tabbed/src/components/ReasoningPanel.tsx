import React from 'react';
import type { Block } from '../hooks/useBundle';

interface Props {
  block?: Block | null;
}

export const ReasoningPanel: React.FC<Props> = ({ block }) => {
  if (!block) {
    return <div style={{fontSize:11, padding:'4px'}} data-testid="reasoning-empty">Select a block for reasoning</div>;
  }
  const reasoning = (block as any).reasoning;
  if (!reasoning) {
    return <div style={{fontSize:11, padding:'4px'}} data-testid="reasoning-none">No reasoning available</div>;
  }
  return (
    <div style={{fontSize:11, padding:'6px', lineHeight:1.3}} data-testid="reasoning-panel">
      <strong>LLM Reasoning</strong>
      <div style={{marginTop:4, whiteSpace:'pre-wrap'}}>{reasoning}</div>
    </div>
  );
};

