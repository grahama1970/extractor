#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
#   "numpy>=1.26.0",
# ]
# ///
import importlib.util
import types
import sys
import numpy as np
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 11 graph math (offline)")


def _load_stage11():
    # Provide minimal faiss stub if not installed
    if "faiss" not in sys.modules:
        faiss_stub = types.ModuleType("faiss")

        class IndexFlatIP:  # noqa: N801
            """Track the total count of elements added to the index."""
            def __init__(self, d):
                """Initialize an object with a total count set to zero."""
                self.ntotal = 0

            def add(self, arr):
                """Increment the total count by the length of the array."""
                self.ntotal += len(arr)

        def normalize_L2(x):
            """Normalize input vector using L2 normalization."""
            return x

        faiss_stub.IndexFlatIP = IndexFlatIP  # type: ignore[attr-defined]
        faiss_stub.normalize_L2 = normalize_L2  # type: ignore[attr-defined]
        sys.modules["faiss"] = faiss_stub
    spec = importlib.util.spec_from_file_location(
        "stage11", "src/extractor/pipeline/steps/11_arango_create_graph.py"
    )
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 11 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@app.command()
def main():
    """Load environment variables and calculate hierarchy distance."""
    load_dotenv(find_dotenv())
    mod = _load_stage11()
    dist = mod.calculate_hierarchy_distance(
        {"source_pdf": "a.pdf", "section_level": 1, "section_breadcrumbs": ["A"]},
        {"source_pdf": "a.pdf", "section_level": 2, "section_breadcrumbs": ["A", "B"]},
    )
    if not (0.0 <= dist <= 1.0):
        raise SystemExit(1)
    w = mod.calculate_combined_weight(0.8, dist)
    if not (0.0 <= w <= 1.0):
        raise SystemExit(1)
    # Optional FAISS path
    embs = np.random.rand(5, 8).astype("float32")
    _, index = mod.build_faiss_index(embs)
    _ = index
    typer.echo("OK: Stage 11 math within bounds (FAISS guarded)")


if __name__ == "__main__":
    app()
