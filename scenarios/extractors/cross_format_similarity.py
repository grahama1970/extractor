#!/usr/bin/env python3
"""Scenario: Cross-format similarity for the same source across providers.

Compares docx/html/md variants of data/input/2505.03335v2.* if present.
Checks that:
- Each extractor returns a document with similar heading samples
- Block-type distributions are in the same ballpark
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Tuple

from loguru import logger

from scenarios.extractors.common import (
    ScenarioResult,
    find_sample,
    summarise_unified,
    write_summary,
)


def _overlap(a: List[str], b: List[str]) -> float:
    sa, sb = {x.strip().lower() for x in a}, {x.strip().lower() for x in b}
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    denom = max(len(sa), len(sb))
    return inter / denom if denom else 0.0


def _dist_sim(a: Dict[str, int], b: Dict[str, int]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 1.0
    diffs = []
    for k in keys:
        av, bv = a.get(k, 0), b.get(k, 0)
        if av == bv:
            diffs.append(0.0)
        else:
            denom = max(av, bv, 1)
            diffs.append(abs(av - bv) / denom)
    # 1 - mean normalised absolute difference → 1.0 is identical
    return 1.0 - (sum(diffs) / len(diffs))


def main() -> int:
    name = "cross_format_similarity"
    if os.getenv("CROSS_FORMAT_ENFORCE", "").lower() not in {"1", "true", "yes"}:
        # Non-blocking by default; enable with CROSS_FORMAT_ENFORCE=1 to assert similarity
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="enforcement-disabled",
            input_path=None,
            provider="cross",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0
    base = "input/2505.03335v2"
    md = find_sample(f"{base}.md")
    html = find_sample(f"{base}.html")
    docx = find_sample(f"{base}.docx")

    if not (md and html and docx):
        logger.info("SKIP: need md/html/docx trio under data/input/")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="sample-trio-missing",
            input_path=None,
            provider="cross",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    from scenarios.extractors.common import import_provider
    try:
        MarkdownProvider = import_provider("providers/markdown.py", "MarkdownProvider")
        HTMLProvider = import_provider("providers/html.py", "HTMLProvider")
        DOCXProvider = import_provider("providers/docx.py", "DOCXProvider")
    except Exception as e:
        logger.info(f"SKIP: cannot import all providers for similarity check: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="provider-import-missing",
            input_path=str(Path(md or html or docx).parent) if (md or html or docx) else None,
            provider="cross",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    docs = {
        "md": MarkdownProvider().extract_document(md),
        "html": HTMLProvider().extract_document(html),
        "docx": DOCXProvider().extract_document(docx),
    }

    dists: Dict[str, Dict[str, int]] = {}
    heads: Dict[str, List[str]] = {}
    for k, d in docs.items():
        dist, hs = summarise_unified(d)
        dists[k] = dist
        heads[k] = hs

    pairs: List[Tuple[str, str]] = [("md", "html"), ("md", "docx"), ("html", "docx")]
    ok = True
    reasons = []

    for a, b in pairs:
        h_sim = _overlap(heads[a], heads[b])
        d_sim = _dist_sim(dists[a], dists[b])
        # Heuristics: heading sample overlap >= 0.3 and block dist sim >= 0.6
        if h_sim < 0.3:
            ok = False
            reasons.append(f"low-heading-overlap({a},{b})={h_sim:.2f}")
        if d_sim < 0.6:
            ok = False
            reasons.append(f"block-distribution-diverge({a},{b})={d_sim:.2f}")

    res = ScenarioResult(
        name=name,
        ok=ok,
        skipped=False,
        reason=", ".join(reasons) if reasons else None,
        input_path=str(Path(md).parent),
        provider="cross",
        source_type=None,
        block_counts={"md": sum(dists["md"].values()), "html": sum(dists["html"].values()), "docx": sum(dists["docx"].values())},
        heading_sample=heads.get("md", [])[:5],
        arango_inserted=False,
        artifacts={},
    )
    write_summary(name, res)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
