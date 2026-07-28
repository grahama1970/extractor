import importlib.util
import os
import sys
import types

sys.path.insert(0, os.path.abspath("src"))
import numpy as np
import pytest


def _load_mod():
    # Provide a lightweight stub to avoid importing litellm_call and its transitive deps.
    stub = types.ModuleType("extractor.pipeline.utils.litellm_call")

    def _noop(*args, **kwargs):
        """Return an empty list, as a no-operation."""
        return []

    stub.litellm_call = _noop  # type: ignore[attr-defined]
    sys.modules["extractor.pipeline.utils.litellm_call"] = stub
    # Provide a minimal 'faiss' stub so type annotations don't crash on import
    if "faiss" not in sys.modules:
        faiss_stub = types.ModuleType("faiss")

        class IndexFlatIP:  # noqa: N801
            """Manage a flat vector index."""
            def __init__(self, d):
                """Initialize an instance with a dictionary and total count."""
                self.d = d
                self.ntotal = 0

            def add(self, arr):
                """Add array length to the total count."""
                self.ntotal += len(arr)

        def normalize_L2(x):
            """Normalize the input vector using the L2 norm."""
            return x

        faiss_stub.IndexFlatIP = IndexFlatIP  # type: ignore[attr-defined]
        faiss_stub.normalize_L2 = normalize_L2  # type: ignore[attr-defined]
        sys.modules["faiss"] = faiss_stub
    spec = importlib.util.spec_from_file_location(
        "stage11", "src/extractor/pipeline/steps/11_arango_create_graph.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_hierarchy_and_weights():
    """Validate hierarchy distance and combined weight calculations."""
    mod = _load_mod()
    dist = mod.calculate_hierarchy_distance(
        {"source_pdf": "a.pdf", "section_level": 1, "section_breadcrumbs": ["A"]},
        {"source_pdf": "a.pdf", "section_level": 2, "section_breadcrumbs": ["A", "B"]},
    )
    assert 0.0 <= dist <= 1.0
    w = mod.calculate_combined_weight(semantic_similarity=0.8, hierarchy_distance=dist)
    assert 0.0 <= w <= 1.0


def test_faiss_optional_build():
    """Skip test if FAISS is not installed, otherwise build FAISS index."""
    mod = _load_mod()
    if getattr(mod, "_HAVE_FAISS", False):
        embs = np.random.rand(5, 16).astype("float32")
        _ = mod.build_faiss_index(embs)
    else:
        pytest.skip("FAISS not installed")
