from __future__ import annotations
from extractor.pipeline.utils.reliability import log_stage_error
from typing import List, Dict, Any, Tuple
from pathlib import Path
import json

try:
    import faiss  # type: ignore
except Exception as exc:
    log_stage_error("ann_index.py", exc, {"context": "ann_index.py"})
    raise
    faiss = None  # type: ignore

import numpy as np  # type: ignore
from extractor.pipeline.utils.embeddings import ensure_embedder as _ensure_embedder


def _blocks_to_text(blks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for b in blks or []:
        for ln in b.get("lines", []) or []:
            for sp in ln.get("spans", []) or []:
                t = (sp.get("text") or "").strip()
                if t:
                    parts.append(t)
    return " ".join(" ".join(parts).split())


def _canon_text(a: Dict[str, Any]) -> str:
    inside = _blocks_to_text(a.get("inside_blocks", []))
    above = _blocks_to_text(a.get("above_blocks", []))
    below = _blocks_to_text(a.get("below_blocks", []))
    interp = a.get("interpretation") or {}
    title = str(interp.get("title") or "")
    summ = str(interp.get("summary") or "")
    note = str(a.get("human_note") or "")
    text = " ".join([title, summ, note, inside, above, below]).strip()
    return text[:2000]


def build_ann_index(annotations: List[Dict[str, Any]]) -> Tuple[Any, Dict[str, Any]]:
    """Build a FAISS IP index of annotation texts. Returns (index, meta)."""
    if faiss is None or not annotations:
        return None, {}
    embedder = _ensure_embedder()
    if embedder is None:
        return None, {}
    texts = [_canon_text(a) for a in annotations]
    vecs = np.array(embedder.encode(texts, normalize_embeddings=True), dtype="float32")
    dim = int(vecs.shape[1])
    idx = faiss.IndexFlatIP(dim)
    idx.add(vecs)
    return idx, {"dim": dim, "count": len(texts)}


def query_ann_index(index: Any, query_text: str, top_k: int = 3) -> List[Tuple[int, float]]:
    if faiss is None or index is None or not query_text:
        return []
    embedder = _ensure_embedder()
    if embedder is None:
        return []
    q = np.array(embedder.encode([query_text], normalize_embeddings=True), dtype="float32")
    D, I = index.search(q, top_k)
    return [(int(i), float(d)) for i, d in zip(I[0], D[0]) if int(i) >= 0]


def save_ann_index(index: Any, meta: Dict[str, Any], path_base: Path, annots: List[Dict[str, Any]]):
    if faiss is None or index is None:
        return
    faiss.write_index(index, str(path_base.with_suffix(".index")))
    meta_out = {
        "faiss_meta": meta,
        "annots_meta": [
            {
                "id": a.get("id"),
                "page": a.get("page"),
                "image_path": a.get("image_path"),
                "type": a.get("type"),
            }
            for a in annots
        ],
    }
    (path_base.with_suffix(".json")).write_text(json.dumps(meta_out, indent=2, ensure_ascii=False))


def load_ann_index(path_base: Path) -> Tuple[Any, Dict[str, Any]]:
    if faiss is None:
        return None, {}
    idx_path = path_base.with_suffix(".index")
    meta_path = path_base.with_suffix(".json")
    if not idx_path.exists() or not meta_path.exists():
        return None, {}
    index = faiss.read_index(str(idx_path))
    meta = json.loads(meta_path.read_text())
    return index, meta
