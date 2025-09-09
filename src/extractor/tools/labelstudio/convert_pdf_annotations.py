#!/usr/bin/env python3
"""
Convert PDF annotations (Boxes + FreeText mini-schema) into Label Studio tasks with
pre-populated predictions. Optionally render page images suitable for LS.

Expected PDF annotations pattern:
- Box: a Square/Rectangle annotation marking the target region (table, requirements, etc.)
- FreeText: nearby text with a mini-schema (either JSON or key:value lines) containing:
  - id: e.g., qb50_table_007
  - type: table | requirements | figure
  - expected_json: e.g., data/gold_standards/tables/007_table.json

Label Studio labeling config (recommended):
  <Image name="image" value="$image" />
  <RectangleLabels name="label" toName="image">
    <Label value="Table" />
    <Label value="Requirements" />
    <Label value="Figure" />
  </RectangleLabels>
  <Choices name="type" toName="image" perRegion="true">
    <Choice value="table" />
    <Choice value="requirements" />
    <Choice value="figure" />
  </Choices>
  <TextArea name="id" toName="image" perRegion="true" />
  <TextArea name="expected_json" toName="image" perRegion="true" />

Usage:
  python -m src.extractor.tools.labelstudio.convert_pdf_annotations \
    --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf \
    --out data/labelstudio \
    --render-dpi 150

This will create:
- data/labelstudio/images/<doc_id>/page_001.png ...
- data/labelstudio/tasks/<doc_id>.tasks.json

Import tasks JSON into Label Studio (as tasks/predictions) and map Local Storage to
"/label-studio/localdata" (docker-compose mounts repo ./data there).
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    raise SystemExit("PyMuPDF (fitz) is required. Install with `pip install pymupdf`.\n" + str(e))


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Region:
    box: Box
    meta: Dict[str, str] = field(default_factory=dict)


def parse_machine_note(text: str) -> Dict[str, str]:
    """Parse FreeText content into a mini-schema dict.

    Accepts either JSON or simple key:value lines (case-insensitive keys).
    Unknown keys are preserved verbatim.
    """
    if not text:
        return {}
    text = text.strip()
    # Try JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            # Normalize keys
            return {k.strip().lower(): str(v).strip() for k, v in data.items()}
    except Exception:
        pass
    # Fallback: key:value lines
    meta: Dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip().lower()
            v = v.strip()
            if k:
                meta[k] = v
    return meta


def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def extract_regions_from_pdf(pdf_path: Path) -> Tuple[List[List[Region]], List[Tuple[float, float]]]:
    """Extract regions per page from a PDF with annotations.

    Returns (pages_regions, pages_sizes) where pages_regions is a list of lists of Region
    per page, and pages_sizes is a list of (W, H) tuples per page.
    """
    doc = fitz.open(pdf_path)
    pages_regions: List[List[Region]] = []
    pages_sizes: List[Tuple[float, float]] = []

    for p in range(len(doc)):
        page = doc[p]
        W, H = page.rect.width, page.rect.height
        pages_sizes.append((W, H))

        rect_annots: List[Box] = []
        free_texts: List[Tuple[Box, Dict[str, str]]] = []

        annot = page.first_annot
        while annot:
            atype = (annot.type[1] or annot.type[0]) if hasattr(annot, "type") else None
            arect = annot.rect  # x0, y0 (bottom-left), x1, y1 (top-right)
            box = Box(arect.x0, arect.y0, arect.x1, arect.y1)

            # Normalize common names: Square/Rect for boxes, FreeText for notes
            if atype and str(atype).lower() in {"square", "rect", "rectangle"}:
                rect_annots.append(box)
            elif atype and str(atype).lower() in {"freetext", "free text"}:
                content = getattr(annot, "info", {}).get("content") or getattr(annot, "content", "")
                meta = parse_machine_note(content or "")
                if meta:
                    free_texts.append((box, meta))
            annot = annot.next

        # Initialize regions from rectangles
        regions: List[Region] = [Region(box=b, meta={}) for b in rect_annots]

        # Pair FreeText to nearest rectangle; merge metadata if multiple notes refer to same region
        for fbox, fmeta in free_texts:
            if not regions:
                continue
            fx, fy = fbox.cx, fbox.cy
            # Pick nearest rect center
            idx = min(range(len(regions)), key=lambda i: dist((fx, fy), (regions[i].box.cx, regions[i].box.cy)))
            # Merge, but don't overwrite existing keys unless empty
            for k, v in fmeta.items():
                if v and (k not in regions[idx].meta or not regions[idx].meta[k]):
                    regions[idx].meta[k] = v

        pages_regions.append(regions)

    doc.close()
    return pages_regions, pages_sizes


def render_pages(pdf_path: Path, out_dir: Path, dpi: int = 150) -> List[Path]:
    """Render PDF pages as PNGs. Returns list of image paths in order."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    images: List[Path] = []
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    for p in range(len(doc)):
        page = doc[p]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_path = out_dir / f"page_{p+1:03d}.png"
        pix.save(img_path.as_posix())
        images.append(img_path)
    doc.close()
    return images


def to_ls_percent(box: Box, page_w: float, page_h: float) -> Dict[str, float]:
    """Convert PDF box (bottom-left origin) to Label Studio percentage coordinates (top-left origin)."""
    x = 100.0 * (box.x0 / page_w)
    y = 100.0 * (1.0 - (box.y1 / page_h))
    width = 100.0 * (box.w / page_w)
    height = 100.0 * (box.h / page_h)
    return {"x": x, "y": y, "width": width, "height": height, "rotation": 0}


def build_ls_tasks(
    pdf_path: Path,
    images: List[Path],
    pages_regions: List[List[Region]],
    pages_sizes: List[Tuple[float, float]],
    localdata_prefix: str = "/label-studio/localdata",
    image_repo_root: Path = Path("data/labelstudio/images"),
) -> List[Dict]:
    """Build Label Studio task list with predictions for each page."""
    # Map doc slug to correct container path
    doc_id = pdf_path.stem
    tasks: List[Dict] = []

    # Allowed labels mapping based on meta.type
    def label_from_type(t: Optional[str]) -> str:
        t = (t or "").strip().lower()
        if t == "table":
            return "Table"
        if t == "requirements":
            return "Requirements"
        return "Figure"

    for idx, img_path in enumerate(images):
        page_num = idx + 1
        # Build a URL that LS can serve for local files: /data/local-files/?d=<path-relative-to-DOCUMENT_ROOT>
        # Our compose mounts repo ./data at /label-studio/localdata (DOCUMENT_ROOT),
        # so we make the path relative to 'data' and use the /data/local-files proxy.
        try:
            rel_from_data = img_path.relative_to("data")
            container_image = f"/data/local-files/?d={rel_from_data.as_posix()}"
        except Exception:
            # Fallback: if the image path is already absolute relative to document root
            # try to strip the leading localdata prefix if present
            p = img_path.as_posix()
            if p.startswith("/label-studio/localdata/"):
                rel = p[len("/label-studio/localdata/"):]
                container_image = f"/data/local-files/?d={rel}"
            else:
                # Last resort: use as-is; may fail to render if not routable
                container_image = f"/data/local-files/?d={p}"

        W, H = pages_sizes[idx]
        preds: List[Dict] = []
        for region in pages_regions[idx]:
            coords = to_ls_percent(region.box, W, H)
            # Rectangle labels
            preds.append({
                "from_name": "label",
                "to_name": "image",
                "type": "rectanglelabels",
                "value": {**coords, "rectanglelabels": [label_from_type(region.meta.get("type"))]},
            })
            # Per-region fields if present
            if region.meta.get("type"):
                preds.append({
                    "from_name": "type",
                    "to_name": "image",
                    "type": "choices",
                    "value": {"choices": [region.meta.get("type")]},
                })
            if region.meta.get("id"):
                preds.append({
                    "from_name": "id",
                    "to_name": "image",
                    "type": "textarea",
                    "value": {"text": [region.meta.get("id")]},
                })
            if region.meta.get("expected_json"):
                preds.append({
                    "from_name": "expected_json",
                    "to_name": "image",
                    "type": "textarea",
                    "value": {"text": [region.meta.get("expected_json")]},
                })

        task = {
            "data": {
                "image": container_image,
                "source_pdf": str(pdf_path.as_posix()),
                "page": page_num,
                "doc_id": doc_id,
            },
            # Add predictions so they show as pre-annotations for review
            "predictions": [{
                "model_version": "pdf-annotations-import",
                "score": 1.0,
                "result": preds,
            }],
        }
        tasks.append(task)

    return tasks


def main():
    ap = argparse.ArgumentParser(description="Convert PDF annotations to Label Studio tasks with predictions.")
    ap.add_argument("--pdf", required=True, help="Path to a marked PDF with annotations.")
    ap.add_argument("--out", default="data/labelstudio", help="Output root for images/tasks (default: data/labelstudio)")
    ap.add_argument("--render-dpi", type=int, default=150, help="DPI for page rendering (default: 150)")
    ap.add_argument(
        "--localdata-prefix",
        default="/label-studio/localdata",
        help="Container path for mounted local data (default: /label-studio/localdata)",
    )
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    out_root = Path(args.out)
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    doc_id = pdf_path.stem
    images_dir = out_root / "images" / doc_id
    tasks_dir = out_root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Rendering pages → {images_dir}")
    images = render_pages(pdf_path, images_dir, dpi=args.render_dpi)

    print(f"[2/3] Extracting annotations from {pdf_path}")
    pages_regions, pages_sizes = extract_regions_from_pdf(pdf_path)

    print("[3/3] Building Label Studio tasks with predictions")
    tasks = build_ls_tasks(
        pdf_path=pdf_path,
        images=images,
        pages_regions=pages_regions,
        pages_sizes=pages_sizes,
        localdata_prefix=args.localdata_prefix,
    )

    out_tasks = tasks_dir / f"{doc_id}.tasks.json"
    with open(out_tasks, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

    # Also create per-task JSON files for LocalFiles import (one task per file)
    split_dir = tasks_dir / f"{doc_id}_local"
    split_dir.mkdir(parents=True, exist_ok=True)
    for idx, task in enumerate(tasks, start=1):
        with open(split_dir / f"task_{idx:03d}.json", "w", encoding="utf-8") as g:
            json.dump(task, g, indent=2, ensure_ascii=False)

    print(f"Done. Tasks written to: {out_tasks}")
    print(f"Also wrote per-task JSON for LocalFiles: {split_dir}")
    print("In Label Studio: Add Source Storage → Local files → path to the folder above → Sync.")


if __name__ == "__main__":  # pragma: no cover
    main()
