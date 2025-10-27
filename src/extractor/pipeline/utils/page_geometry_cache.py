from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import hashlib


@dataclass
class PageGeom:
    width: float
    height: float
    text_bboxes: List[Tuple[float, float, float, float]]


@dataclass
class PageGeomCache:
    doc_key: str
    pages: Dict[int, PageGeom]

    def to_json(self) -> dict:
        return {
            "doc_key": self.doc_key,
            "pages": {
                int(k): {
                    "width": v.width,
                    "height": v.height,
                    "text_bboxes": v.text_bboxes,
                }
                for k, v in self.pages.items()
            },
        }

    @staticmethod
    def from_json(d: dict) -> "PageGeomCache":
        pages: Dict[int, PageGeom] = {}
        for k, v in (d.get("pages") or {}).items():
            pages[int(k)] = PageGeom(
                width=float(v.get("width") or 0.0),
                height=float(v.get("height") or 0.0),
                text_bboxes=[tuple(map(float, bb)) for bb in (v.get("text_bboxes") or [])],
            )
        return PageGeomCache(doc_key=str(d.get("doc_key") or ""), pages=pages)


def _doc_key_for(pdf_path: Optional[Path], extras: Optional[str] = None) -> str:
    h = hashlib.sha1()
    base = (str(pdf_path.resolve()) if pdf_path else "") + "|" + str(extras or "")
    try:
        if pdf_path and pdf_path.exists():
            st = pdf_path.stat()
            base += f"|{st.st_size}|{int(st.st_mtime)}"
    except Exception:
        pass
    h.update(base.encode("utf-8"))
    return h.hexdigest()


def _default_cache_dir(results_root: Path) -> Path:
    d = results_root / "_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_cache(results_root: Path, doc_key: str) -> Optional[PageGeomCache]:
    path = _default_cache_dir(results_root) / f"page_cache_{doc_key}.json"
    if not path.exists():
        return None
    try:
        return PageGeomCache.from_json(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def save_cache(results_root: Path, cache: PageGeomCache) -> Path:
    path = _default_cache_dir(results_root) / f"page_cache_{cache.doc_key}.json"
    path.write_text(json.dumps(cache.to_json(), ensure_ascii=False, indent=2))
    return path


def build_from_sections(sections: List[dict]) -> Dict[int, PageGeom]:
    pages: Dict[int, PageGeom] = {}
    for sec in sections or []:
        for b in sec.get("blocks") or []:
            try:
                p = int(b.get("page") or b.get("page_idx") or b.get("page_index") or -1)
                bb = b.get("bbox") or []
                if p < 0 or len(bb) != 4:
                    continue
                rec = pages.setdefault(p, PageGeom(width=0.0, height=0.0, text_bboxes=[]))
                rec.text_bboxes.append(tuple(map(float, bb)))
            except Exception:
                continue
    return pages


def fill_missing_with_pymupdf(pages: Dict[int, PageGeom], pdf_path: Optional[Path]) -> None:
    if not pdf_path or not pdf_path.exists():
        return
    try:
        import fitz  # PyMuPDF
    except Exception:
        return
    try:
        doc = fitz.open(str(pdf_path))
        for pno in range(len(doc)):
            rect = doc[pno].rect
            pg = pages.setdefault(pno, PageGeom(width=float(rect.width), height=float(rect.height), text_bboxes=[]))
            if not pg.width or not pg.height:
                pg.width, pg.height = float(rect.width), float(rect.height)
            if not pg.text_bboxes:
                blocks = doc[pno].get_text("blocks")
                for blk in blocks:
                    if isinstance(blk, (list, tuple)) and len(blk) >= 5 and str(blk[4] or "").strip():
                        x0, y0, x1, y1 = map(float, blk[:4])
                        pg.text_bboxes.append((x0, y0, x1, y1))
        doc.close()
    except Exception:
        pass


def build_or_load(results_root: Path, sections: List[dict], pdf_path: Optional[Path]) -> PageGeomCache:
    titles = "|".join((sec.get("title") or "") for sec in (sections or [])[:10])
    extras = f"{len(sections)}|{titles}"
    key = _doc_key_for(pdf_path, extras=extras)
    cached = load_cache(results_root, key)
    if cached:
        return cached
    pages = build_from_sections(sections)
    fill_missing_with_pymupdf(pages, pdf_path)
    cache = PageGeomCache(doc_key=key, pages=pages)
    save_cache(results_root, cache)
    return cache
