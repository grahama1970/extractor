from __future__ import annotations

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Extractor Review API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _bundle_path(root: Path | None = None) -> Path:
    base = Path(root) if root else Path("data/results/pipeline/ui")
    return base / "blocks_full.json"


def _load(root: Path | None = None):
    f = _bundle_path(root)
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"UI bundle not found at {f}")
    return json.loads(f.read_text())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/bundle")
def bundle():
    return JSONResponse(_load())


@app.get("/blocks")
def blocks(page: int | None = None):
    data = _load()
    if page is None:
        return {"count": len(data.get("blocks", []))}
    subset = [b for b in data.get("blocks", []) if b.get("page") == page]
    return {"page": page, "blocks": subset, "count": len(subset)}


@app.get("/pages")
def pages():
    data = _load()
    return {"page_sizes": data.get("page_sizes", [])}


@app.get("/verify-root")
def verify_root():
    root = Path("data/results/pipeline/05_table_extractor/verify")
    if root.exists():
        return {"verify_root": str(root.resolve())}
    return {"verify_root": None}


@app.get("/metrics")
def metrics():
    data = _load()
    gm = (data.get("gold") or {}).get("metrics") or {}
    return {
        "counts": data.get("counts"),
        "table_coverage": data.get("table_coverage"),
        "doc_id": data.get("doc_id"),
        "gold_imported": data.get("gold_imported"),
        "gold_metrics": gm,
    }


@app.get("/gold")
def gold():
    data = _load()
    return {
        "gold_imported": data.get("gold_imported"),
        "gold_blocks": (data.get("gold") or {}).get("blocks", []),
        "metrics": (data.get("gold") or {}).get("metrics", {}),
    }
