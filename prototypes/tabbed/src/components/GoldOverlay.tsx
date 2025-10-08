import React from 'react';

interface GoldItem {
  page: number;
  bbox: [number, number, number, number];
  type: string;
  text?: string;
}

interface Props {
  items: GoldItem[];
  page: number;
}

export const GoldOverlay: React.FC<Props> = ({ items, page }) => {
  const pageItems = items.filter(it => (it.page || 0) === page);
  return (
    <>
      {pageItems.map((g, idx) => {
        const [x0,y0,x1,y1] = g.bbox as any;
        return (
          <div key={`gold-${idx}`} style={{
            position:'absolute', left:x0, top:y0, width:Math.max(0,x1-x0), height:Math.max(0,y1-y0),
            boxSizing:'border-box', border:'2px dashed #6a1b9a', pointerEvents:'none'
          }} title={`Gold:${g.type}`}/>
        );
      })}
    </>
  );
};

