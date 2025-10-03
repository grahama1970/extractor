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
import re
import unicodedata

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

    # Thresholds from env (defaults per guidance)
    h_threshold = float(os.getenv("CROSS_FORMAT_HEADING_OVERLAP", "0.8"))
    t_threshold = float(os.getenv("CROSS_FORMAT_TABLE_PARITY", "0.8"))
    f_threshold = float(os.getenv("CROSS_FORMAT_FIGURE_CAPTIONS", "0.8"))
    enforce_paragraphs = os.getenv("CROSS_FORMAT_ENFORCE_PARAGRAPHS", "0").lower() in {"1", "true", "yes"}
    p_threshold = float(os.getenv("CROSS_FORMAT_PARAGRAPH_PARITY", "0.2"))

    # Build top-2 heading sets directly from docs
    _PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
    _WS = re.compile(r"\s+", flags=re.UNICODE)

    def _heading_key(s: str) -> str:
        if not s:
            return ""
        s_norm = unicodedata.normalize("NFKD", s)
        s_norm = _PUNCT.sub(" ", s_norm)
        s_norm = _WS.sub(" ", s_norm).strip().lower()
        return s_norm

    def top2_titles(doc) -> List[str]:
        out = []
        for b in getattr(doc, "blocks", []) or []:
            t = str(getattr(b, "type", "")).split(".")[-1]
            if t == "HEADING":
                level = 9
                if getattr(b, "metadata", None) and getattr(b.metadata, "attributes", None):
                    try:
                        level = int(b.metadata.attributes.get("level", 9))
                    except Exception:
                        level = 9
                if level <= 2 and isinstance(getattr(b, "content", None), str):
                    out.append(_heading_key(b.content))
        return out

    top2 = {k: top2_titles(d) for k, d in docs.items()}

    # Basic counts for additional parity checks
    def count_type(dist: Dict[str, int], name: str) -> int:
        return dist.get(name.upper(), 0)

    pairs: List[Tuple[str, str]] = [("md", "html"), ("md", "docx"), ("html", "docx")]
    ok = True
    reasons = []

    for a, b in pairs:
        # Heading overlap on top-2 levels
        h_sim = _overlap(top2[a], top2[b])
        if h_sim < h_threshold:
            ok = False
            reasons.append(f"headings<{h_threshold}({a},{b})={h_sim:.2f}")

        # Table parity: counts within ±1 in at least t_threshold fraction
        ta, tb = count_type(dists[a], "TABLE"), count_type(dists[b], "TABLE")
        t_parity = 1.0 if abs(ta - tb) <= 1 else 0.0
        if t_parity < t_threshold:
            ok = False
            reasons.append(f"tables_parity<{t_threshold}({a},{b})={t_parity:.2f}")

        # Figure caption presence parity (presence counts approximated by FIGURE blocks)
        fa, fb = count_type(dists[a], "FIGURE"), count_type(dists[b], "FIGURE")
        f_parity = 1.0 if (fa == fb or (fa == 0 and fb == 0)) else (1.0 if min(fa, fb) / max(fa, fb) >= f_threshold else 0.0)
        if f_parity < f_threshold:
            ok = False
            reasons.append(f"figures_parity<{f_threshold}({a},{b})={f_parity:.2f}")

        # Optional: Paragraph count parity within ±p_threshold of max count
        if enforce_paragraphs:
            pa, pb = count_type(dists[a], "PARAGRAPH"), count_type(dists[b], "PARAGRAPH")
            denom = max(pa, pb, 1)
            p_div = abs(pa - pb) / denom
            if p_div > p_threshold:
                ok = False
                reasons.append(f"paragraphs_diff>{p_threshold}({a},{b})={p_div:.2f}")

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
