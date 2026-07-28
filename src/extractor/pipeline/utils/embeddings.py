"""Lazy-loaded sentence-transformer embedder singleton for text similarity tasks."""
from __future__ import annotations

from typing import Any
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error

_EMBEDDER: Any = None


def ensure_embedder() -> Any:
    """Load and cache a SentenceTransformer embedding model."""
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading Sentence Transformer model for text embeddings...")
            _EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2")
            logger.success("Text embedding model loaded.")
        except Exception as exc:
            log_stage_error("embeddings.py", exc, {"context": "embeddings.py"})
            raise
            logger.warning(
                f"Failed to load text embedding model (continuing without embeddings): {e}"
            )
    return _EMBEDDER
