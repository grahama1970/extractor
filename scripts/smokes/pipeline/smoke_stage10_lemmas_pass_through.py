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
def main(tmpdir: Path = typer.Option(Path("/tmp/extractor_smoke10"))):
    """Initialize a minimal Lean4 output JSON structure."""
    tmpdir.mkdir(parents=True, exist_ok=True)
    # Minimal Lean4 OUT.json with analysis.used_lemmas
    out = {
        "proof_results": [
            {
                "status": "unproved",
                "analysis": {
                    "normalized_prop": "A",
                    "polarity": "assert",
                    "shape": "predicate",
                    "used_lemmas": ["Nat.add_comm"],
                },
                "item": {
                    "requirement_text": "A",
                    "context": {"section_id": "S1", "doc_id": "D1"},
                    "source_details": {"section_id": "S1"},
                },
            }
        ]
    }
    lean4_json = tmpdir / "out.json"
    lean4_json.write_text(json.dumps(out))
    flat_json = tmpdir / "flat10.json"
    import importlib.util as _util
    from pathlib import Path as _Path

    p = _Path("scripts/pipeline/stage10_pass_through_lemmas.py").resolve()
    spec = _util.spec_from_file_location("stage10_pass", str(p))
    mod = _util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    mod.main(lean4_out=lean4_json, out_json=flat_json)  # type: ignore

    flat = json.loads(flat_json.read_text())
    items = flat.get("items") or []
    assert items and items[0]["rtm"]["lean4_lemmas"] == ["Nat.add_comm"]
    print("OK: Stage 10 lemmas pass-through smoke passed")


if __name__ == "__main__":
    app()
