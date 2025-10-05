#!/usr/bin/env python3
from __future__ import annotations

"""
07h: Requirement Classifier (heuristics + optional LLM confirm)
"""

import json
import os
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List

import typer
from loguru import logger

try:
    from extractor.pipeline.utils.litellm_call import litellm_call
except Exception:
    litellm_call = None

app = typer.Typer(help="Requirement classifier stage.")

REQ_MODAL = re.compile(r"\b(shall|must|should|will|may|shall\s+not|must\s+not|should\s+not)\b", re.I)


def heuristic_label(text: str) -> str:
    if REQ_MODAL.search(text or ""):
        if len((text or "").split()) <= 150:
            return "requirement"
    if re.search(r"\b(is|are)\s+(defined|the)\b", (text or "").lower()):
        return "definition"
    return "other"


@app.command()
def run(
    reflow_json: Path = typer.Option(..., "--reflow", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
    enable_llm: bool = typer.Option(False, "--llm"),
    model: str = typer.Option("", "--model"),
    concurrency: int = typer.Option(2, "--concurrency"),
):
    doc = json.loads(reflow_json.read_text())
    reqs: List[Dict[str, Any]] = []
    for sec in doc.get("reflowed_sections", doc.get("sections", [])):
        for blk in sec.get("reflowed_json", {}).get("blocks", []):
            if blk.get("type") != "paragraph":
                continue
            text = blk.get("text") or ""
            hlabel = heuristic_label(text)
            rec = {
                "anchor_id": blk.get("anchor_id"),
                "section_id": sec.get("id") or sec.get("section_id"),
                "text": text,
                "heuristic": hlabel,
            }
            reqs.append(rec)

    # optional LLM confirmation for heuristic positives
    if enable_llm:
        llm_model = model or os.getenv("REQUIREMENTS_LLM_MODEL", "")
        timeout_env = float(os.getenv("STAGE07H_TIMEOUT", os.getenv("STAGE07_REQUEST_TIMEOUT", "120")))
        retries_env = int(os.getenv("STAGE07H_RETRIES", os.getenv("STAGE07_NUM_RETRIES", "2")))
    if enable_llm and llm_model and litellm_call:
        prompts = []
        idx = []
        for i, r in enumerate(reqs):
            if r["heuristic"] in ("requirement", "definition"):
                idx.append(i)
                prompts.append(
                    {
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Classify requirement text. JSON only: {\\\"label\\\": \\\"requirement|definition|other\\\"}. Return 'requirement' ONLY if it states an obligation, constraint, or bound (modal verbs).",
                                    }
                                ],
                            },
                            {"role": "user", "content": [{"type": "text", "text": r["text"][:2000]}]},
                        ],
                        "kwargs": {"temperature": 0},
                    }
                )
        if prompts:
            out = __import__("asyncio").run(
                litellm_call(
                    prompts,
                    wrap_json=True,
                    concurrency=concurrency,
                    desc="07h_requirement_classifier",
                    request_timeout=timeout_env,
                    num_retries=retries_env,
                )
            )
            for j, irec in enumerate(idx):
                lab = reqs[irec]["heuristic"]
                try:
                    data = json.loads(out[j].content or "{}")
                    if data.get("label") in ("requirement", "definition", "other"):
                        lab = data["label"]
                except Exception:
                    pass
                reqs[irec]["final_label"] = lab
    for r in reqs:
        r.setdefault("final_label", r["heuristic"])
    # add formal_status default and schema version
    for r in reqs:
        if r.get("final_label") == "requirement" and not r.get("formal_status"):
            r["formal_status"] = "unproved"
    # Assign requirement ids
    counter = 1
    for r in reqs:
        if r["final_label"] == "requirement":
            rid = f"{r.get('section_id')}-R{counter:03d}"
            r["requirement_id"] = rid
            r["hash"] = hashlib.sha256((r.get("text") or "").encode()).hexdigest()
            counter += 1

    out_dir = output_dir / "07h_requirement_classifier" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir / "07h_requirements.json"
    outp.write_text(json.dumps({
        "schema_version": 1,
        "requirements": reqs,
        "deterministic": not enable_llm,
        "hash_component": "07h"
    }, indent=2))
    logger.success(f"07h: wrote {outp} (total={len(reqs)})")


if __name__ == "__main__":
    app()
