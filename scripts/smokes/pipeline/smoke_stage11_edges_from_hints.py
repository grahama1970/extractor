#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations
import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(tmpdir: Path = typer.Option(Path("/tmp/extractor_smoke11"))):
    tmpdir.mkdir(parents=True, exist_ok=True)
    # Minimal edge_hints JSON like Lean4's --emit-edge-hints
    hints = {
        "nodes": {
            "sections": [{"key": "S1"}, {"key": "S2"}],
            "lemmas": [{"key": "Nat_add_comm", "name": "Nat.add_comm"}],
        },
        "edges": {
            "depends_on": [{"from": "S1", "to": "Nat_add_comm", "source": "used_lemmas"}],
            "contradicts_candidates": [{"a": "S1", "b": "S2", "reason": "opposite_polarity_same_prop"}],
            "refines_candidates": [],
        },
    }
    hints_path = tmpdir / "edge_hints.json"
    hints_path.write_text(json.dumps(hints))
    out_edges = tmpdir / "edges.json"
    import importlib.util as _util
    from pathlib import Path as _Path
    p = _Path("scripts/pipeline/stage11_build_edges.py").resolve()
    spec = _util.spec_from_file_location("stage11_build_edges", str(p))
    mod = _util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    mod.main(source=hints_path, out_edges=out_edges, arango_db="")  # type: ignore
    edges = json.loads(out_edges.read_text())
    assert edges["edges"]["depends_on"] and edges["edges"]["contradicts"]
    print("OK: Stage 11 edges-from-hints smoke passed")


if __name__ == "__main__":
    app()
