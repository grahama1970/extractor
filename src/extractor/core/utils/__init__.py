"""
Utility modules for Marker
Module: __init__.py
Description: Package initialization and exports

Provides additional functionality for:
- Document processing and debugging
- Table extraction and evaluation  
- Text chunking and summarization
- Embedding and vector operations
- ArangoDB setup and operations
"""

# Export embedding utilities
try:
    from extractor.core.utils.embedding_utils import (
        get_embedding,
        get_embedder_model,
        cosine_similarity,
        calculate_cosine_similarity,
    )
except ImportError:
    # If there's an import error, don't crash, just don't export the functions
    pass

# Export other utilities
__all__ = [
    'get_embedding',
    'get_embedder_model',
    'cosine_similarity',
    'calculate_cosine_similarity'
]