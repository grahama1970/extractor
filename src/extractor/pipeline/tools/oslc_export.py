#!/usr/bin/env python3
"""
OSLC Export (stub, offline)

Converts Stage 10 flattened JSON into a minimal OSLC-like JSON with resources
and links. This is a stub for future OSLC integrations and requires no network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def export_oslc(stage10_json: Path, out_file: Path) -> Dict[str, Any]:
    data = json.loads(stage10_json.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Stage 10 JSON must be a list")
    resources: List[Dict[str, Any]] = []
    for o in data:
        if not isinstance(o, dict):
            continue
        rid = f"urn:pdf-object:{o.get('_key')}"
        res = {
            "@type": "oslc:Requirement",
            "@id": rid,
            "dcterms:title": (o.get("section_title") or "Object"),
            "oslc:shortTitle": o.get("object_type"),
            "dcterms:identifier": o.get("_key"),
            "oslc_cm:instanceShape": "urn:shape:requirement-min",
            "ex:docId": o.get("doc_id"),
            "ex:sectionId": o.get("section_id"),
        }
        resources.append(res)
    payload = {"oslc:resources": resources, "oslc:links": []}
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, indent=2))
    return {"ok": True, "count": len(resources), "path": str(out_file)}


if __name__ == "__main__":
    import typer

    app = typer.Typer(add_completion=False)

    @app.command()
    def main(stage10: Path, out: Path = Path("scripts/artifacts/oslc_links.json")):
        res = export_oslc(stage10, out)
        print(json.dumps(res, indent=2))

    app()

