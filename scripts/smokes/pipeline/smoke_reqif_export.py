#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "lxml>=5.3.0",
# ]
# ///
"""Smoke: ReqIF export v0

Loads latest Stage 10 JSON under data/results/** and exports a minimal .reqif file.
Writes a short report to scripts/artifacts/reqif_export_report.json.
"""
from __future__ import annotations

import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


def _find_latest_stage10(root: Path) -> Path:
    """Return the most recently modified flattened data file in the specified directory."""
    cands = sorted(
        root.rglob("10_arangodb_exporter/json_output/10_flattened_data.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return (
        cands[0]
        if cands
        else root / "pipeline/10_arangodb_exporter/json_output/10_flattened_data.json"
    )


@app.command()
def main(root: Path = typer.Option(Path("data/results"), exists=True)):
    """Find and validate the latest Stage 10 JSON file in the specified directory."""
    stage10 = _find_latest_stage10(root)
    if not stage10.exists():
        typer.echo(f"No Stage 10 JSON found under {root}", err=True)
        raise typer.Exit(1)
    # Import exporter and write to artifacts
    import sys

    repo_src = (Path(__file__).resolve().parents[3] / "src").resolve()
    if str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))
    from extractor.pipeline.tools.reqif_export import export_reqif

    out = Path("scripts/artifacts/export.reqif")
    res = export_reqif(stage10, out)
    # Minimal validation: well-formed + expected structure
    from lxml import etree as ET  # type: ignore

    try:
        tree = ET.parse(str(out))
        root = tree.getroot()
        ok_xml = root.tag.upper().endswith("REQ-IF") or root.tag.upper() == "REQ-IF"
        has_core = root.find("CORE-CONTENT") is not None
        has_specs = root.xpath("//SPECIFICATIONS/SPECIFICATION")
        has_types = root.xpath("//SPEC-OBJECT-TYPES/SPEC-OBJECT-TYPE")
        structure_ok = bool(has_core and has_specs and has_types)
    except Exception:
        ok_xml = False
        structure_ok = False
    report = {
        "ok": bool(res.get("ok")) and ok_xml and structure_ok,
        "count": int(res.get("count", 0)),
        "path": str(out),
        "xml_ok": ok_xml,
        "structure_ok": structure_ok,
    }
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "reqif_export_report.json").write_text(
        json.dumps(report, indent=2)
    )
    if not report["ok"]:
        typer.echo("ReqIF export failed", err=True)
        raise typer.Exit(1)
    print("OK: ReqIF export")


if __name__ == "__main__":
    app()
