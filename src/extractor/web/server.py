from __future__ import annotations

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Extractor Review API")


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

