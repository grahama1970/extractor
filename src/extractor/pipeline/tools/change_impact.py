#!/usr/bin/env python3
"""
Change Impact (v0)

Diff two Stage 10 flattened JSON files and output a JSON report of likely
impacted sections/objects (added/removed/modified by text).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _index_by_key(objs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(o.get("_key")): o for o in objs if isinstance(o, dict) and o.get("_key")}


def change_impact(old_path: Path, new_path: Path, out_file: Path) -> Dict[str, Any]:
    o = json.loads(old_path.read_text())
    n = json.loads(new_path.read_text())
    if not isinstance(o, list) or not isinstance(n, list):
        raise ValueError("Both inputs must be lists")
    io = _index_by_key(o)
    inew = _index_by_key(n)
    old_keys = set(io.keys())
    new_keys = set(inew.keys())
    added = list(new_keys - old_keys)
    removed = list(old_keys - new_keys)
    common = old_keys & new_keys
    modified: List[str] = []
    for k in common:
        if (io[k].get("text_content") or "") != (inew[k].get("text_content") or ""):
            modified.append(k)
    report = {
        "added": added,
        "removed": removed,
        "modified": modified,
        "impact_sections": sorted(
            {inew[k].get("section_id") for k in added if k in inew}
            | {io[k].get("section_id") for k in removed if k in io}
            | {inew[k].get("section_id") for k in modified if k in inew}
        ),
    }
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2))
    return {"ok": True, **report, "path": str(out_file)}


if __name__ == "__main__":
    import typer

    app = typer.Typer(add_completion=False)

    @app.command()
    def main(old: Path, new: Path, out: Path = Path("scripts/artifacts/change_impact.json")):
        res = change_impact(old, new, out)
        print(json.dumps(res, indent=2))

    app()
