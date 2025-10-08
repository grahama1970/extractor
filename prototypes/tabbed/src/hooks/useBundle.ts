import { useEffect, useState } from 'react';

export interface Block {
  block_id?: number;
  page: number;
  type: string;
  text?: string;
  bbox: [number, number, number, number];
  mini_hash: string;
  suspicious?: boolean;
  [key: string]: any;
}

export interface UIBundle {
  doc_id?: string;
  blocks: Block[];
  tables: any[];
  figures: any[];
  suspects?: any;
}

export function useBundle(url: string) {
  const [data, setData] = useState<UIBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(j => { if (alive) setData(j); })
      .catch(e => { if (alive) setError(String(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [url]);

  return { data, error, loading };
}

