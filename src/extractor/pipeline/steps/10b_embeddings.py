#!/usr/bin/env python3
"""
Stage 10b: Embedding Generator (post-flatten)

Reads the flattened PDF objects from Stage 10 and writes an embedding-enriched
copy. Keeps embeddings as a first-class, optional step so Stage 10 can focus on
flattening/Arango I/O.

Inputs:
  - flattened_json: data/results/.../10_arangodb_exporter/json_output/10_flattened_data.json

Outputs:
  - embeddings_json: same data with an `embedding` field per object (if text exists)
    written to 10b_embeddings/json_output/10b_embedded_data.json

Flags:
  --skip-embeddings: disable embeddings
  --fast-embeddings: use deterministic hash embedding (for smokes/CI)

Env:
  EMBEDDING_MODEL (default sentence-transformers/all-mpnet-base-v2)
  EMBEDDINGS_DISABLE (default 1) to skip heavy model load
"""

from __future__ import annotations

import json
import os
import hashlib
import struct
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from loguru import logger
from rich.console import Console

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.step_sanity import run_step_sanity

console = Console()
STEP_NAME = "10b_embeddings"

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
EMBEDDING_MODEL: Optional[object] = None


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


def _fast_embedding(text: str, dim: int = 8) -> List[float]:
    if not text:
        text = ""
    h = hashlib.md5(text.encode("utf-8")).digest()
    raw = (h * ((dim * 4 + len(h) - 1) // len(h)))[: dim * 4]
    vals = []
    for i in range(dim):
        chunk = raw[i * 4 : (i + 1) * 4]
        ui = struct.unpack("!I", chunk)[0]
        vals.append((ui % 10_000_000) / 10_000_000.0)
    return vals


def _ensure_embedder():
    global EMBEDDING_MODEL
    if os.getenv("EMBEDDINGS_DISABLE", "1").lower() in {"1", "true", "yes"}:
        logger.info("Embeddings disabled via EMBEDDINGS_DISABLE; skipping model load")
        return None
    if EMBEDDING_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
            EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.success("Embedding model loaded")
        except Exception as exc:
            log_stage_error(STEP_NAME, exc, {'context': STEP_NAME})
            raise
    return EMBEDDING_MODEL


def _embed_text(text: str, skip: bool, fast: bool) -> Optional[List[float]]:
    if skip or not text:
        return None
    if fast:
        return _fast_embedding(text)
    model = _ensure_embedder()
    if model is None:
        return None
    try:
        return model.encode(text).tolist()  # type: ignore[attr-defined]
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': STEP_NAME})
        raise


def run(
    flattened_json: Path,
    output_dir: Path,
    *,
    skip_embeddings: bool = False,
    fast_embeddings: bool = False,
) -> Path:
    console.print("[bold green]Starting Embedding Generation (Stage 10b)[/bold green]")

    out_dir = output_dir / "10b_embeddings" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "10b_embedded_data.json"

    data = json.loads(flattened_json.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("Flattened data must be a list of pdf_objects")

    for obj in data:
        if not isinstance(obj, dict):
            continue
        text = obj.get("text_content") or ""
        obj["embedding"] = _embed_text(text, skip_embeddings, fast_embeddings)

    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    console.print(f"Embeddings written to: {out_path}")
    return out_path


def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="Stage 10b embeddings")
    parser.add_argument("flattened_json", type=Path, help="Path to 10_flattened_data.json")
    parser.add_argument("output_dir", type=Path, help="Results root (e.g., data/results/pipeline_ui_XXXX)")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embeddings entirely")
    parser.add_argument("--fast-embeddings", action="store_true", help="Use deterministic hash embeddings")
    args = parser.parse_args()

    run(args.flattened_json, args.output_dir, skip_embeddings=args.skip_embeddings, fast_embeddings=args.fast_embeddings)


if __name__ == "__main__":
    _cli()
