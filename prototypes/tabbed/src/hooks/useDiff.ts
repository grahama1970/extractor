import { useState, useCallback } from 'react';
import type { Block } from './useBundle';

export interface DiffMap {
  added: Set<string>;
  changed: Set<string>;
  unchanged: Set<string>;
  baselineOnlyCount: number;
}

export function computeDiff(current: Block[], baseline: Block[]): DiffMap {
  const added = new Set<string>();
  const changed = new Set<string>();
  const unchanged = new Set<string>();
  const baselineMini = new Map<string, Block>();
  const baselineByLoc = new Map<string, Block>();

  baseline.forEach(b => {
    baselineMini.set(b.mini_hash, b);
    const locKey = `${b.page}:${Math.round((((b.bbox?.[1]||0)+(b.bbox?.[3]||0))/2))}`;
    baselineByLoc.set(locKey, b);
  });

  const usedBaseline = new Set<string>();

  current.forEach(c => {
    if (baselineMini.has(c.mini_hash)) {
      unchanged.add(c.mini_hash);
      usedBaseline.add(c.mini_hash);
    } else {
      const locKey = `${c.page}:${Math.round((((c.bbox?.[1]||0)+(c.bbox?.[3]||0))/2))}`;
      const candidate = baselineByLoc.get(locKey);
      if (candidate && candidate.type === c.type) {
        changed.add(c.mini_hash);
        usedBaseline.add(candidate.mini_hash);
      } else {
        added.add(c.mini_hash);
      }
    }
  });

  const baselineOnlyCount = baseline.length - usedBaseline.size;
  return { added, changed, unchanged, baselineOnlyCount };
}

export function useDiff() {
  const [baseline, setBaseline] = useState<Block[] | null>(null);
  const [diff, setDiff] = useState<DiffMap | null>(null);

  const loadBaselineFile = useCallback((file: File, currentBlocks: Block[]) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const json = JSON.parse(reader.result as string);
        const blocks: Block[] = json.blocks || [];
        setBaseline(blocks);
        setDiff(computeDiff(currentBlocks, blocks));
      } catch (e) {
        console.error('Failed to parse baseline:', e);
      }
    };
    reader.readAsText(file);
  }, []);

  const recompute = useCallback((currentBlocks: Block[]) => {
    if (baseline) {
      setDiff(computeDiff(currentBlocks, baseline));
    }
  }, [baseline]);

  return { baseline, diff, loadBaselineFile, recompute };
}

