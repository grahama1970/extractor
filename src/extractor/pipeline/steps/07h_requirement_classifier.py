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

import scillm
from extractor.pipeline.utils.scillm_env import provider_fields_for_model

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
    records: List[Dict[str, Any]] = []
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
            records.append(rec)

    # optional LLM confirmation for heuristic positives
    if enable_llm:
        llm_model = model or os.getenv("REQUIREMENTS_LLM_MODEL", "")
        timeout_env = float(os.getenv("STAGE07H_TIMEOUT", os.getenv("STAGE07_REQUEST_TIMEOUT", "120")))
        retries_env = int(os.getenv("STAGE07H_RETRIES", os.getenv("STAGE07_NUM_RETRIES", "2")))
    if enable_llm and llm_model:
        idx_map: List[int] = []
        req_list: List[Dict[str, Any]] = []
        prov = provider_fields_for_model(llm_model)
        for i, rec in enumerate(records):
            if rec["heuristic"] in ("requirement", "definition"):
                idx_map.append(i)
                req_list.append(
                    {
                        "model": llm_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "You are a JSON generator. Return strictly valid JSON only. No prose or markdown.",
                                    }
                                ],
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": (
                                            "Classify requirement text. Respond in English."
                                            " Return JSON: {\\\"label\\\": \\\"requirement|definition|other\\\"}."
                                            " Return 'requirement' ONLY if it states an obligation, constraint, or bound.\n\nText: "
                                            + (rec.get("text") or "")[:2000]
                                        ),
                                    }
                                ],
                            },
                        ],
                        "kwargs": {
                            **prov,
                            "response_mode": "schema_first",
                            "json_schema": {
                                "name": "reqLabel",
                                "schema": {
                                    "type": "object",
                                    "properties": {"label": {"type": "string", "enum": ["requirement", "definition", "other"]}},
                                    "required": ["label"],
                                },
                            },
                            "retry_enabled": True,
                            "honor_retry_after": True,
                            "timeout": int(timeout_env),
                            "temperature": 0,
                        },
                    }
                )
        if req_list:
            import asyncio
            router = scillm.Router()
            out = asyncio.run(router.parallel_acompletions(req_list, max_concurrency=max(1, int(concurrency))))
            for j, irec in enumerate(idx_map):
                lab = records[irec]["heuristic"]
                try:
                    content = out[j].get("choices", [{}])[0].get("message", {}).get("content")  # type: ignore[index]
                    data = json.loads(content or "{}") if isinstance(content, str) else {}
                    if data.get("label") in ("requirement", "definition", "other"):
                        lab = data["label"]
                except Exception:
                    pass
                records[irec]["final_label"] = lab
    for r in records:
        r.setdefault("final_label", r["heuristic"])
    # add formal_status default and schema version
    for r in records:
        if r.get("final_label") == "requirement" and not r.get("formal_status"):
            r["formal_status"] = "unproved"
    # Assign requirement ids
    counter = 1
    for r in records:
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
        "requirements": records,
        "deterministic": not enable_llm,
        "hash_component": "07h"
    }, indent=2))
    logger.success(f"07h: wrote {outp} (total={len(reqs)})")


if __name__ == "__main__":
    app()
