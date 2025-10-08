#!/usr/bin/env python3
from __future__ import annotations

"""
07l: Confidence scoring aggregator.
"""

import json, os
from pathlib import Path
from typing import Any, Dict

import typer
from loguru import logger

app = typer.Typer(help="Compute confidence scores for blocks.")


@app.command()
def run(
    reflow_json: Path = typer.Option(..., "--reflow", exists=True),
    cross_refs_json: Path = typer.Option(..., "--refs", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
):
    reflow = json.loads(reflow_json.read_text())
    refs = json.loads(cross_refs_json.read_text()).get("references", [])
    ref_map = {}
    for r in refs:
        ref_map.setdefault(r.get("source_paragraph"), 0)
        ref_map[r.get("source_paragraph")] += 1

    scores: Dict[str, float] = {}
    # optional requirement status weighting
    req_status = {}
    req_path = os.getenv("REQUIREMENTS_STATUS_JSON")
    if req_path and Path(req_path).exists():
        try:
            rj = json.loads(Path(req_path).read_text()).get("requirements", [])
            for r in rj:
                if r.get("anchor_id"):
                    req_status[r["anchor_id"]] = r.get("final_label"), r.get("formal_status", r.get("final_label"))
        except Exception:
            pass
    for sec in reflow.get("reflowed_sections", reflow.get("sections", [])):
        for blk in sec.get("reflowed_json", {}).get("blocks", []):
            anchor = blk.get("anchor_id")
            if not anchor:
                continue
            base = 0.5
            if blk.get("type") == "table":
                dens = (blk.get("confidence") or {}).get("density") or 0
                base = 0.4 + min(0.6, float(dens))
            elif blk.get("type") == "figure":
                base = 0.55
            elif blk.get("type") == "paragraph":
                refs_count = int(ref_map.get(anchor, 0))
                base = 0.45 + min(0.25, refs_count * 0.05)
            bump = 0.0
            if anchor in req_status:
                _, fstatus = req_status[anchor]
                if fstatus == "proved":
                    bump = 0.08
                elif fstatus == "sorry":
                    bump = 0.04
                elif fstatus == "ambiguous":
                    bump = -0.05
            final = max(0.0, min(1.0, base + bump))
            scores[anchor] = round(final, 3)

    out_dir = output_dir / "07l_confidence_scorer" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir / "07l_confidence.json"
    outp.write_text(json.dumps({"scores": scores, "deterministic": True, "hash_component": "07l"}, indent=2))
    logger.success(f"07l: wrote {outp} (scored={len(scores)})")


if __name__ == "__main__":
    app()
