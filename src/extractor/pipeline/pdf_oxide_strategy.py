"""pdf_oxide pipeline strategy — replaces S00-S06 with a single Rust call.

When STAGE02_EXTRACTOR=pdf_oxide, the pipeline calls this module instead of
running S00+S01+S02+S03+S04+S04a+S06 separately. After this module writes
compatible output files, the pipeline picks up at S05 (Camelot tables) and
then common stages (S07+).

Usage:
    from extractor.pipeline.pdf_oxide_strategy import run_pdf_oxide_strategy
    rc = run_pdf_oxide_strategy(pdf, out, args)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


def run_pdf_oxide_strategy(
    pdf: Path,
    out: Path,
    manifest: Any,
    stage_latencies: Dict[str, int],
    args: Any,
) -> int:
    """Run pdf_oxide extraction, then hand off to tables + common stages.

    Replaces: S00, S01, S02, S03, S04, S04a, S06.
    Preserves: S05 (Camelot tables), S05b/c, S06b (VLM), S07+.

    Returns exit code (0 = success).
    """
    from extractor.pipeline.steps.s02_pdf_oxide_adapter import run as oxide_run

    results: Dict[str, Any] = {}
    served_model = {
        "text": os.getenv("CHUTES_TEXT_MODEL", ""),
        "vlm": os.getenv("CHUTES_VLM_MODEL", ""),
    }

    # --- Single pdf_oxide call replaces S00+S02+S03+S04+S04a+S06 ---
    t0 = time.monotonic()
    try:
        s02_path_str = oxide_run(pdf, out)
        dt_ms = int((time.monotonic() - t0) * 1000)
        stage_latencies["pdf_oxide_extract"] = dt_ms
        logger.info(f"pdf_oxide: all stages complete in {dt_ms}ms")
    except Exception as e:
        logger.error(f"pdf_oxide extraction failed: {e}")
        if getattr(args, "stop_on_fail", False):
            return 1
        return 1

    s02_path = Path(s02_path_str)

    # Record stages in manifest
    for stage_name in [
        "00_profile_detector",
        "02_marker_extractor",
        "03_suspicious_headers",
        "04_section_builder",
        "04a_layout_audit",
        "06_figure_extractor",
    ]:
        manifest.record_stage(
            stage_name,
            "Completed",
            {"engine": "pdf_oxide", "latency_ms": dt_ms},
        )

    # Load S04 path and S06 path for downstream use
    s04_path = out / "04_section_builder" / "json_output" / "04_sections.json"
    s06_path = out / "06_figure_extractor" / "json_output" / "06_figures.json"

    results["02"] = s02_path
    results["03"] = s02_path  # S03 output is same blocks with header validation
    results["04"] = s04_path
    results["06"] = s06_path

    # Load preset config from profile
    preset_config = {}
    try:
        profile_path = out / "00_profile_detector" / "profile.json"
        if profile_path.exists():
            profile = json.loads(profile_path.read_text())
            preset_config = {"domain": profile.get("domain", "general")}
    except Exception:
        pass

    # --- S01 annotation processor (still Python — reads annotation objects) ---
    try:
        from extractor.pipeline.steps import s01_annotation_processor as s01

        a01 = _run_step(
            "01_annotation_processor",
            s01.run,
            pdf,
            out,
            args,
            stage_latencies,
        )
        results["01"] = a01
    except ImportError:
        logger.warning("S01 annotation processor not available, skipping")
    except Exception as e:
        logger.warning(f"S01 annotation processor failed: {e}")

    # --- S05 table extraction (Camelot — stays Python) ---
    try:
        from extractor.pipeline.steps import (
            s05_table_extractor as s05,
            s05b_table_describer as s05b,
            s05c_table_merger as s05c,
        )

        skip_tables = getattr(args, "skip_tables05", False)

        if skip_tables:
            stub_dir = out / "05_table_extractor" / "json_output"
            stub_dir.mkdir(parents=True, exist_ok=True)
            stub = {
                "timestamp": int(time.time()),
                "tables": [],
                "diagnostics": [{"severity": "info", "reason": "skip_tables05 flag"}],
            }
            stub_path = stub_dir / "05_tables.json"
            stub_path.write_text(json.dumps(stub, indent=2))
            results["05"] = stub_path
        else:
            a05 = _run_step(
                "05_table_extractor",
                s05.run,
                s04_path,
                out / "01_annotation_processor",
                out,
                args,
                stage_latencies,
            )
            results["05"] = a05

        # S05b table descriptions
        a05b = _run_step(
            "05b_table_describer",
            s05b.run,
            out / "05_table_extractor",
            out,
            args,
            stage_latencies,
            skip_descriptions=bool(getattr(args, "summary_only", False))
            or skip_tables
            or bool(getattr(args, "skip_table_descriptions", False)),
        )
        results["05b"] = a05b

        # S05c table merger
        a05c = _run_step(
            "05c_table_merger",
            s05c.run,
            out,
            out,
            args,
            stage_latencies,
        )
        results["05c"] = a05c

    except ImportError as e:
        logger.warning(f"Table extraction steps not available: {e}")
    except Exception as e:
        logger.warning(f"Table extraction failed: {e}")

    # --- S06b figure descriptions (VLM — stays Python) ---
    try:
        from extractor.pipeline.steps import s06b_figure_describer as s06b

        a06b = _run_step(
            "06b_figure_describer",
            s06b.run,
            out / "06_figure_extractor",
            out,
            args,
            stage_latencies,
            skip_descriptions=getattr(args, "skip_fig_descriptions", False),
        )
        if a06b:
            results["06b"] = a06b
    except ImportError:
        logger.info("S06b figure describer not available, skipping")
    except Exception as e:
        logger.warning(f"S06b figure describer failed: {e}")

    # --- Common downstream stages (S07-S14) ---
    from extractor.pipeline.run_pipeline import _run_common_stages

    return _run_common_stages(
        out,
        args,
        manifest,
        results,
        stage_latencies,
        served_model,
        pdf=pdf,
        preset_config=preset_config,
    )


def _run_step(
    name: str,
    fn,
    *fargs,
    args: Any = None,
    stage_latencies: Optional[Dict[str, int]] = None,
    **fkw,
) -> Optional[Path]:
    """Lightweight step runner (subset of run_pipeline._step)."""
    t0 = time.monotonic()
    try:
        rv = fn(*fargs, **fkw)
        dt_ms = int((time.monotonic() - t0) * 1000)
        if stage_latencies is not None:
            stage_latencies[name] = dt_ms
        path_like = rv[0] if isinstance(rv, (list, tuple)) and rv else rv
        if path_like is None:
            logger.warning(f"{name}: returned no result")
            return None
        logger.info(f"{name}: ok in {dt_ms}ms")
        return Path(path_like) if path_like is not None else None
    except Exception as e:
        logger.warning(f"{name}: failed — {e}")
        return None
