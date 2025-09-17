#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastapi>=0.115.0",
#   "uvicorn>=0.32.0",
#   "pydantic>=2.4.0",
#   "python-dotenv>=1.0.0",
# ]
# ///
from __future__ import annotations

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

try:
    import fitz  # PyMuPDF
except Exception as e:
    raise RuntimeError("PyMuPDF (fitz) is required for pipeline server") from e


class Box(BaseModel):
    id: Optional[str] = None
    type: str
    instanceId: Optional[str] = None
    x: float
    y: float
    w: float
    h: float


class RunExternalRequest(BaseModel):
    pdf_path: Optional[str] = None
    pdf_rel: Optional[str] = None
    boxes_by_page: Dict[int, List[Box]] = Field(default_factory=dict)
    results_dir: Optional[str] = None
    session: Optional[str] = None


app = FastAPI(title="Tabbed → Pipeline Bridge")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_pdf(req: RunExternalRequest) -> Path:
    if req.pdf_path:
        p = Path(req.pdf_path).expanduser().resolve()
        if not p.exists():
            raise HTTPException(400, f"pdf_path not found: {p}")
        return p
    if req.pdf_rel:
        # Try prototypes/tabbed/html/public first
        candidates = [
            Path("prototypes/tabbed/html/public") / req.pdf_rel,
            Path("public") / req.pdf_rel,
            Path(req.pdf_rel),
        ]
        for c in candidates:
            if c.exists():
                return c.resolve()
        raise HTTPException(400, f"pdf_rel not found: {req.pdf_rel}")
    raise HTTPException(400, "Either pdf_path or pdf_rel must be provided")


def _to_pipeline_annotations(pdf: Path, boxes_by_page: Dict[int, List[Box]]) -> Dict:
    doc = fitz.open(str(pdf))
    annotations: List[Dict] = []
    for page_key, boxes in boxes_by_page.items():
        # UI likely uses 1-based pages; make it robust
        try:
            page_index = int(page_key)
        except Exception:
            page_index = int(str(page_key))
        zero_based = max(0, page_index - 1)
        if zero_based >= len(doc):
            continue
        page = doc[zero_based]
        w = float(page.rect.width)
        h = float(page.rect.height)
        for b in boxes:
            x0 = max(0.0, min(w, b.x * w))
            y0 = max(0.0, min(h, b.y * h))
            x1 = max(0.0, min(w, (b.x + b.w) * w))
            y1 = max(0.0, min(h, (b.y + b.h) * h))
            # expand 10%
            pad_x = 0.1 * (x1 - x0)
            pad_y = 0.1 * (y1 - y0)
            ex0 = max(0.0, x0 - pad_x)
            ey0 = max(0.0, y0 - pad_y)
            ex1 = min(w, x1 + pad_x)
            ey1 = min(h, y1 + pad_y)

            typ = (b.type or "").strip().lower()
            if typ == "section":
                a_type = "section_header"
            elif typ == "table":
                a_type = "table_region"
            elif typ == "figure":
                a_type = "figure_region"
            else:
                a_type = typ or "region"

            annotations.append(
                {
                    "id": b.instanceId or b.id or f"anno_{len(annotations)+1:04d}",
                    "page": zero_based,
                    "type": a_type,
                    "original_rect": [x0, y0, x1, y1],
                    "expanded_rect": [ex0, ey0, ex1, ey1],
                }
            )
    doc.close()
    return {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "source_pdf": str(pdf),
        "status": "Completed",
        "annotation_count": len(annotations),
        "annotations": annotations,
    }


@app.post("/api/pipeline/run-external")
def run_external(req: RunExternalRequest):
    pdf = _resolve_pdf(req)
    results = Path(req.results_dir or (Path("data/results") / f"pipeline_ui_{os.getpid()}"))
    results.mkdir(parents=True, exist_ok=True)

    stage01 = results / "01_annotation_processor"
    json_dir = stage01 / "json_output"
    json_dir.mkdir(parents=True, exist_ok=True)
    annotations = _to_pipeline_annotations(pdf, req.boxes_by_page)
    anno_path = json_dir / "01_annotations.json"
    anno_path.write_text(json.dumps(annotations, indent=2))

    # Phase-1 cleaner: copy original as clean
    clean_path = stage01 / f"{pdf.stem}_clean.pdf"
    shutil.copyfile(str(pdf), str(clean_path))

    # Invoke run_all with external annotations
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(Path.cwd() / "src"))
    cmd = [
        env.get("PYTHON", "python"),
        "-m",
        "extractor.pipeline.run_all",
        "--pdf",
        str(pdf),
        "--results",
        str(results),
        "--annotations-json",
        str(anno_path),
        "--clean-pdf",
        str(clean_path),
        # Omit --validate here; UI path prioritizes finishing the run.
        # Deterministic toggles (optional):
        "--skip-llm03",
        "--skip-descriptions06",
        "--summary-only07",
        "--skip-proving08",
        "--fast-embeddings10",
    ]
    proc = subprocess.run(cmd, env=env)
    ok = proc.returncode == 0

    summary = Path("scripts/artifacts/run_summary_happy.json")
    final_json = results / "final_report.json"
    final_md = results / "final_report.md"
    return {
        "ok": ok,
        "results_dir": str(results),
        "summary_path": str(summary) if summary.exists() else None,
        "final_report_json": str(final_json) if final_json.exists() else None,
        "final_report_md": str(final_md) if final_md.exists() else None,
    }


@app.get("/api/artifacts/file")
def get_artifact_file(path: str):
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, f"File not found: {p}")
    # basic safety: restrict to workspace
    try:
        _ = p.resolve().relative_to(Path.cwd())
    except Exception:
        raise HTTPException(400, "Path must be within workspace")
    return FileResponse(str(p))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="info")
