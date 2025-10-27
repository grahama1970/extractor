#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///

"""
Lightweight import-and-call smoke for stages: 01 → 04? → 05 → 06a → 06b → 07 (summary-only) → 07_requirements_miner.

- Creates minimal placeholder JSONs when later-stage inputs are missing.
- Produces a concise JSON summary with per-stage status and artifact paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

OUT = Path(os.getenv("PIPELINE_SMOKE_OUT", "data/results/pipeline_smoke_ic"))
OUT.mkdir(parents=True, exist_ok=True)

PDF_DEFAULT = Path(
    os.getenv(
        "PIPELINE_SMOKE_PDF",
        "data/input/pipeline/BHT_CV32A65X_with_requirements.pdf",
    )
)


def write_json(p: Path, obj: Any) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    return p


def main() -> None:
    summary = {"stages": []}
    # Import step modules directly from file paths to avoid alias issues
    import importlib.util as _ilu
    def _load(step_file: str, as_name: str):
        p = Path('src/extractor/pipeline/steps') / step_file
        modname = f"smoke.{as_name}"
        spec = _ilu.spec_from_file_location(modname, str(p))
        if not spec or not spec.loader:
            raise RuntimeError(f"spec load failed for {p}")
        mod = _ilu.module_from_spec(spec)
        import sys as _sys
        _sys.modules[modname] = mod
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        return mod
    s01  = _load('01_annotation_processor.py', 's01')
    s04  = _load('04_section_builder.py', 's04')
    s05  = _load('05_table_extractor.py', 's05')
    s06a = _load('06a_title_caption_enricher.py', 's06a')
    s06b = _load('06b_layout_sketcher.py', 's06b')
    s07  = _load('07_reflow_section.py', 's07')
    s07rm= _load('07_requirements_miner.py', 's07rm')

    # Stage 01
    s01_dir = OUT / "01_annotation_processor" / "json_output"
    s01_out = s01_dir / "01_annotations.json"
    try:
        if not s01_out.exists():
            path = s01.run(PDF_DEFAULT, OUT)
            s01_out = Path(path)
        summary["stages"].append({"stage": "01", "status": "ok", "out": str(s01_out)})
    except Exception as e:
        summary["stages"].append({"stage": "01", "status": "fail", "error": str(e)})

    # Stage 04 (from Stage 02/03 artifacts if available; else try fallback with a blocks JSON if present)
    s04_dir = OUT / "04_section_builder" / "json_output"
    s04_out = s04_dir / "04_sections.json"
    try:
        if not s04_out.exists():
            # Prefer verified blocks from Stage 03 if present, else Stage 02 blocks
            v03 = OUT / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
            b02 = OUT / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
            if v03.exists():
                s04.run(v03, OUT / "01_annotation_processor", OUT, debug=False, fallback_heuristics=False)
            elif b02.exists():
                s04.run(b02, OUT / "01_annotation_processor", OUT, debug=False, fallback_heuristics=True)
        if s04_out.exists():
            summary["stages"].append({"stage": "04", "status": "ok", "out": str(s04_out)})
        else:
            summary["stages"].append({"stage": "04", "status": "skip", "reason": "missing inputs"})
    except Exception as e:
        summary["stages"].append({"stage": "04", "status": "fail", "error": str(e)})

    # Stage 05 (requires 04)
    s05_dir = OUT / "05_table_extractor" / "json_output"
    s05_out = s05_dir / "05_tables.json"
    try:
        if s04_out.exists() and not s05_out.exists():
            s05.run(s04_out, OUT / "01_annotation_processor", OUT)
        if s05_out.exists():
            summary["stages"].append({"stage": "05", "status": "ok", "out": str(s05_out)})
        else:
            summary["stages"].append({"stage": "05", "status": "skip", "reason": "missing 04"})
    except Exception as e:
        summary["stages"].append({"stage": "05", "status": "fail", "error": str(e)})

    # Prepare minimal figures json if 06 output missing
    s06_fig_dir = OUT / "06_figure_extractor" / "json_output"
    s06_fig = s06_fig_dir / "06_figures.json"
    if not s06_fig.exists():
        write_json(s06_fig, {"figures": [], "timestamp": ""})

    # Stage 06a
    s06a_dir = OUT / "06a_title_caption_enricher" / "json_output"
    try:
        if s05_out.exists():
            s06a.run(s05_out, s06_fig, sections_json=s04_out if s04_out.exists() else None, output_dir=OUT)
            s06a_tables = s06a_dir / "05_tables.enriched.json"
            s06a_figs = s06a_dir / "06_figures.enriched.json"
            summary["stages"].append({
                "stage": "06a",
                "status": "ok",
                "tables": str(s06a_tables),
                "figures": str(s06a_figs),
            })
        else:
            summary["stages"].append({"stage": "06a", "status": "skip", "reason": "missing 05"})
    except Exception as e:
        summary["stages"].append({"stage": "06a", "status": "fail", "error": str(e)})

    # Stage 06b (deterministic, requires 04)
    try:
        if s04_out.exists():
            s06b.main(results_dir=OUT)
            outp = OUT / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch.json"
            status = "ok" if outp.exists() else "skip"
            summary["stages"].append({"stage": "06b", "status": status, "out": str(outp)})
        else:
            summary["stages"].append({"stage": "06b", "status": "skip", "reason": "missing 04"})
    except Exception as e:
        summary["stages"].append({"stage": "06b", "status": "fail", "error": str(e)})

    # Stage 07 (summary-only; disable images)
    s07_dir = OUT / "07_reflow_section" / "json_output"
    s07_out = s07_dir / "07_reflowed.json"
    try:
        if s04_out.exists() and s05_out.exists() and s06_fig.exists():
            s07.run(
                sections_json=s04_out,
                tables_json=s05_out,
                figures_json=s06_fig,
                annotations_json=None,
                output_dir=OUT,
                summary_only=True,
                include_images=False,
                allow_fallback=True,
                bundle=None,
                llm_timeout=30,
                mode="strict",
            )
        if s07_out.exists():
            summary["stages"].append({"stage": "07", "status": "ok", "out": str(s07_out)})
        else:
            summary["stages"].append({"stage": "07", "status": "skip", "reason": "missing inputs"})
    except Exception as e:
        summary["stages"].append({"stage": "07", "status": "fail", "error": str(e)})

    # Stage 07 requirements miner
    try:
        if s07_out.exists():
            s07rm.run(s07_out, OUT)
            outp = OUT / "07_requirements_miner" / "json_output" / "07_requirements.json"
            summary["stages"].append({"stage": "07rm", "status": "ok", "out": str(outp)})
        else:
            summary["stages"].append({"stage": "07rm", "status": "skip", "reason": "missing 07"})
    except Exception as e:
        summary["stages"].append({"stage": "07rm", "status": "fail", "error": str(e)})

    out_summary = OUT / "smokes" / "import_call_summary.json"
    write_json(out_summary, summary)
    print(str(out_summary))


if __name__ == "__main__":
    main()
