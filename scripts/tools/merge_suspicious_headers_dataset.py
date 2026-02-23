#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.0",
# ]
# ///

"""
Merge + dedupe Stage 03 suspicious header JSONL records by text_sha1.

Input: directory containing one or more JSONL files (default: data/results/pipeline/03_suspicious_headers/datasets)
Output: merged JSONL (default: scripts/artifacts/suspicious_headers_merged.jsonl)

Each input line is expected to be a dict with keys including:
- text_sha1, header_text, context_text, label_is_header, label_source, timestamp

Dedup precedence: prefer label_source in this order: human > llm > heuristic_auto
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(add_completion=False, help="Merge and dedupe Stage 03 header dataset JSONLs")


PREF_ORDER = {"human": 3, "llm": 2, "heuristic_auto": 1}


def _prefer(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    la = str(a.get("label_source") or "llm").lower()
    lb = str(b.get("label_source") or "llm").lower()
    sa = PREF_ORDER.get(la, 0)
    sb = PREF_ORDER.get(lb, 0)
    if sa != sb:
        return a if sa > sb else b
    # tie-breaker: latest timestamp wins
    ta = str(a.get("timestamp") or "")
    tb = str(b.get("timestamp") or "")
    return a if ta >= tb else b


@app.command()
def main(
    input_dir: Path = typer.Option(
        Path("data/results/pipeline/03_suspicious_headers/datasets"),
        exists=False,
        help="Directory with JSONL files",
    ),
    output_path: Path = typer.Option(
        Path("scripts/artifacts/suspicious_headers_merged.jsonl"), help="Output JSONL path"
    ),
    include_sources: str = typer.Option(
        "human,llm,heuristic_auto", help="Comma-separated label_source whitelist"
    ),
) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    allow = {s.strip().lower() for s in include_sources.split(",") if s.strip()}
    merged: dict[str, dict[str, Any]] = {}
    files: list[Path] = []
    for ext in ("*.jsonl", "*.ndjson"):
        files.extend(list(input_dir.glob(ext)))
    for fp in files:
        with fp.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                src = str(obj.get("label_source") or "llm").lower()
                if src not in allow:
                    continue
                key = obj.get("text_sha1") or ""
                if not key:
                    # derive basic fingerprint
                    key = str(hash((obj.get("header_text") or "", obj.get("font_signature") or "")))
                prev = merged.get(key)
                merged[key] = obj if prev is None else _prefer(prev, obj)

    with output_path.open("w", encoding="utf-8") as out:
        for _, obj in merged.items():
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")
    typer.echo(
        json.dumps(
            {"ok": True, "files": len(files), "unique": len(merged), "out": str(output_path)},
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
