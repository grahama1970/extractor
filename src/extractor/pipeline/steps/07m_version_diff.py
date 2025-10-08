#!/usr/bin/env python3
from __future__ import annotations

"""
07m: Version diff between two 07e reflow JSONs.
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict
import re

import typer
from loguru import logger

app = typer.Typer(help="Version diff generator.")


def block_sig_components(b: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": b.get("type"),
        "text": b.get("text") if b.get("type") == "paragraph" else None,
        "columns": b.get("columns") if b.get("type") == "table" else None,
        "rows_hash": hashlib.sha256(
            json.dumps(b.get("rows"), sort_keys=True, default=str).encode()
        ).hexdigest()
        if b.get("rows")
        else None,
        "caption": b.get("caption") if b.get("type") == "figure" else None,
    }

def block_sig(b: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(block_sig_components(b), sort_keys=True).encode()).hexdigest()

# Fallback punctuation/whitespace pattern compatible with stdlib re
_PUNCT_WS = re.compile(r"[\W_]+", re.UNICODE)

def _normalize_text(s: str | None) -> str:
    try:
        import regex as _rx  # optional for \p{P} support
        return _rx.sub(r"[\p{P}\p{Zs}]+", "", s or "")
    except Exception:
        return re.sub(r"[\W_]+", "", s or "")

def _snippet(s: str | None, n: int = 40) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s[:n]


@app.command()
def run(
    old_reflow_json: Path = typer.Option(..., "--old", exists=True),
    new_reflow_json: Path = typer.Option(..., "--new", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
):
    old = json.loads(old_reflow_json.read_text())
    new = json.loads(new_reflow_json.read_text())
    old_index: Dict[str, str] = {}
    old_components: Dict[str, Dict[str, Any]] = {}
    for s in old.get("reflowed_sections", old.get("sections", [])):
        for b in s.get("reflowed_json", {}).get("blocks", []):
            a = b.get("anchor_id")
            if a:
                old_index[a] = block_sig(b)
                old_components[a] = block_sig_components(b)
    deltas = []
    current_anchors = set()
    for s in new.get("reflowed_sections", new.get("sections", [])):
        for b in s.get("reflowed_json", {}).get("blocks", []):
            a = b.get("anchor_id")
            if not a:
                continue
            current_anchors.add(a)
            sig = block_sig(b)
            if a not in old_index:
                deltas.append({"anchor_id": a, "change_type": "added", "changed_fields": []})
            elif old_index[a] != sig:
                oldc = old_components.get(a, {})
                newc = block_sig_components(b)
                changed = []
                old_text = oldc.get("text")
                new_text = newc.get("text")
                if _normalize_text(old_text) != _normalize_text(new_text):
                    changed.append("text_changed")
                if oldc.get("columns") != newc.get("columns"):
                    changed.append("columns_changed")
                if oldc.get("rows_hash") != newc.get("rows_hash"):
                    changed.append("rows_changed")
                if _normalize_text(oldc.get("caption")) != _normalize_text(newc.get("caption")):
                    changed.append("caption_changed")
                if not changed:
                    changed.append("structure_changed")
                entry = {"anchor_id": a, "change_type": "modified", "changed_fields": changed}
                if "text_changed" in changed:
                    entry["prev_snippet"] = _snippet(old_text)
                    entry["new_snippet"] = _snippet(new_text)
                if "caption_changed" in changed and not entry.get("prev_snippet"):
                    entry["prev_snippet"] = _snippet(oldc.get("caption"))
                    entry["new_snippet"] = _snippet(newc.get("caption"))
                deltas.append(entry)
    for a in old_index.keys() - current_anchors:
        deltas.append({"anchor_id": a, "change_type": "removed", "changed_fields": []})
    out_dir = output_dir / "07m_version_diff" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir / "07m_deltas.json"
    outp.write_text(json.dumps({"deltas": deltas, "deterministic": True, "hash_component": "07m"}, indent=2))
    logger.success(f"07m: wrote {outp} (changes={len(deltas)})")


if __name__ == "__main__":
    app()
# DEPRECATED: use deterministic hashes + orchestrator manifest for diff/report.
