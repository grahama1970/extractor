from __future__ import annotations

from typing import Any
from loguru import logger

_EMBEDDER: Any = None

def ensure_embedder() -> Any:
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading Sentence Transformer model for text embeddings...")
            _EMBEDDER = SentenceTransformer('all-MiniLM-L6-v2')
            logger.success("Text embedding model loaded.")
        except Exception as e:
            logger.warning(f"Failed to load text embedding model (continuing without embeddings): {e}")
    return _EMBEDDER
