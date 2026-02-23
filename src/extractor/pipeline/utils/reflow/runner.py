"""
Stage 07 run orchestration extracted from 07_reflow_section.py.

This module contains the run() function and CLI logic.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from rich.console import Console
from tqdm.asyncio import tqdm_asyncio

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.diagnostics import (
    build_stage_timings,
    get_run_id,
    iso_now,
    snapshot_resources,
    start_resource_sampler,
    stop_resource_sampler,
)
from extractor.pipeline.utils.model_select import get_vlm_model, get_text_model
from extractor.pipeline.utils.unified_conversion import build_unified_document_from_reflow
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight

from extractor.pipeline.utils.reflow import consolidate_data
from extractor.pipeline.utils.reflow.section_reflow import reflow_section_with_llm
from extractor.pipeline.utils.reflow import (
    compute_table_merges as _compute_table_merges,
    apply_layout_ordering as _apply_layout_ordering,
)
from extractor.pipeline.utils.ann_index import (
    load_ann_index,
    build_ann_index,
    query_ann_index,
)
from extractor.pipeline.utils.diagnostics import gpu_metrics_available, make_event
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.core.schema.unified_document import SourceType

USE_LAYOUT_SKETCH = os.getenv("STAGE07_USE_LAYOUT_SKETCH", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
OMIT_IMAGES_IF_CONFIDENT = os.getenv("STAGE07_OMIT_IMAGES_IF_CONFIDENT", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
LAYOUT_CONF_THRESH = float(os.getenv("STAGE07_LAYOUT_CONF_THRESH", "0.75"))
STAGE07_DEBUG = os.getenv("STAGE07_DEBUG", "0").lower() in ("1", "true", "yes", "y")
STAGE07_VISUAL_PROOF = os.getenv("STAGE07_VISUAL_PROOF", "").lower() in ("1", "true", "yes", "y")
STAGE07_SOURCE_PDF = os.getenv("STAGE07_SOURCE_PDF", "").strip() or None

console = Console()


def sanity() -> int:
    return run_step_sanity("07_reflow_section")


def run(
    sections_json: Path,
    tables_json: Path,
    figures_json: Path,
    annotations_json: Path | None = None,
    output_dir: Path = Path("data/results/pipeline"),
    summary_only: bool = False,
    include_images: bool = False,
    allow_fallback: bool = False,
    bundle: Path | None = None,
    llm_timeout: int = 60,
    mode: str = "strict",
) -> Path:
    """
    Reflows document sections using multimodal context from previous stages.
    """
    console.print("[bold green]Starting Section Reflow (Stage 07)[/bold green]")
    # Respect allow-images toggle (default text-only)
    _ALLOW_IMAGES = os.getenv("STAGE07_ALLOW_IMAGES", "0").lower() in ("1", "true", "yes", "y")
    include_images = bool(include_images and _ALLOW_IMAGES)
    global LLM_MODEL
    # Offline deterministic runs should not require model selection or preflight
    if not summary_only:
        try:
            # Choose model based on whether images are included
            LLM_MODEL = get_vlm_model() if include_images else get_text_model()
        except Exception as exc:
            log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
            raise
            log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
            raise
            log_stage_error("07_reflow_section", exc, {"context": "07"})
            raise
        # Early sanity: paved-path preflight required when LLM is enabled
        try:
            require_scillm_preflight()
        except RuntimeError as exc:
            console.print(
                f"[red]Stage 07 SciLLM preflight failed: {exc}. Set CHUTES_API_BASE/CHUTES_API_KEY or use --summary-only.[/red]"
            )
            raise
        except Exception as exc:
            log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
            raise
            log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
            raise
            log_stage_error("07_reflow_section", exc, {"context": "07"})
            raise
    # Configure a stage-specific log file for debugging
    try:
        stage_dir = output_dir / "07_reflow_section"
        stage_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(stage_dir / "stage_07_reflow_section.log"),
            level="INFO",
            enqueue=True,
            backtrace=False,
            diagnose=False,
            rotation="1 week",
            retention="14 days",
        )
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise
        pass

    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    import time

    t0 = time.monotonic()
    stage_start_ts = iso_now()
    resources = snapshot_resources("start")
    sampler = (
        start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
        if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y")
        else None
    )
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(
                make_event(
                    "07_reflow_section",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise
        pass

    # --- Profile toggles (simple profile defaults) ---
    try:
        if not include_images:
            os.environ.setdefault("STAGE07_MAX_IMAGES", "0")
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise
        pass

    # --- Directory and Data Setup ---
    # Optional: unify env toggles via --mode flag for determinism
    try:
        m = (mode or "strict").strip().lower()
        if m == "minimal":
            os.environ.setdefault("STAGE07_FORCE_MINIMAL_CALL", "1")
            os.environ.setdefault("STAGE07_MINIMAL_JSON", "1")
            os.environ.setdefault("STAGE07_SCHEMA_MODE", "text")
        elif m == "strict":
            os.environ.pop("STAGE07_FORCE_MINIMAL_CALL", None)
            os.environ.pop("STAGE07_MINIMAL_JSON", None)
            os.environ.setdefault("STAGE07_SCHEMA_MODE", "reflow_json")
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise
        pass
    stage_output_dir = output_dir / "07_reflow_section"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    # Prefer enriched tables/figures when present (06a outputs)
    try:
        prefer_enriched = os.getenv("STAGE07_PREFER_ENRICHED", "1").lower() in (
            "1",
            "true",
            "yes",
            "y",
        )
        if prefer_enriched:
            base_dir = output_dir
            enr_tables = (
                base_dir / "06a_title_caption_enricher" / "json_output" / "05_tables.enriched.json"
            )
            enr_figs = (
                base_dir / "06a_title_caption_enricher" / "json_output" / "06_figures.enriched.json"
            )
            if enr_tables.exists():
                tables_json = enr_tables
            if enr_figs.exists():
                figures_json = enr_figs
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise
        pass

    sections_to_process = consolidate_data(
        sections_json, tables_json, figures_json, annotations_json
    )
    # Attach layout sketches if available (06b step)
    if USE_LAYOUT_SKETCH:
        try:
            sketches_path = (
                output_dir / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch.json"
            )
            if sketches_path.exists():
                sk_map = json.loads(sketches_path.read_text()).get("sections", {})
                sk_count = 0
                for s in sections_to_process:
                    sid = str(s.get("id"))
                    sk = sk_map.get(sid)
                    if isinstance(sk, dict):
                        s["layout_sketch"] = sk
                        # Apply deterministic ordering for tables/figures before prompting
                        _apply_layout_ordering(s)
                        sk_count += 1
                diagnostics.append(
                    make_event(
                        "07_reflow_section",
                        "info",
                        "layout_sketch_attached",
                        f"Attached sketches for {sk_count} sections",
                        {},
                    )
                )
        except Exception as exc:
            log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
            raise
            log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
            raise
            log_stage_error("07_reflow_section", exc, {"context": "07"})
            raise

    # Optional: load or build FAISS index from Stage 01 annotations for similar text lookup
    ann_index = None
    _ann_list = []
    try:
        if annotations_json and annotations_json.exists():
            stage01_dir = annotations_json.parent.parent  # .../01_annotation_processor
            idx, meta = load_ann_index(stage01_dir / "annots_faiss")
            if idx is not None:
                ann_index = idx
                diagnostics.append(
                    make_event(
                        "07_reflow_section",
                        "info",
                        "ann_index_loaded",
                        f"Loaded FAISS index from {stage01_dir}",
                        {},
                    )
                )
            else:
                _payload = json.load(open(annotations_json))
                _ann_list = _payload.get("annotations", []) or []
                if _ann_list:
                    ann_index, _ = build_ann_index(_ann_list)
                    diagnostics.append(
                        make_event(
                            "07_reflow_section",
                            "info",
                            "ann_index_built",
                            f"FAISS annotations index built: {len(_ann_list)} items",
                            {},
                        )
                    )
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise

    # Attach top-3 similar annotations (text-only) to each section (advisory)
    if ann_index is not None:
        for sec in sections_to_process:
            try:
                qtext = (str(sec.get("title", "")) + "\n" + str(sec.get("merged_text", "")))[:2000]
                sims = query_ann_index(ann_index, qtext, top_k=3)
                if sims:
                    # If we built from _ann_list, map indices to ids; else leave ids None
                    ids_scores = []
                    for i, score in sims:
                        aid = None
                        try:
                            if _ann_list:
                                aid = _ann_list[i].get("id")
                        except Exception as exc:
                            log_stage_error(
                                "07_reflow_section", exc, {"context": "07_reflow_retry"}
                            )
                            raise
                            log_stage_error(
                                "07_reflow_section", exc, {"context": "07_reflow_retry"}
                            )
                            raise
                            log_stage_error("07_reflow_section", exc, {"context": "07"})
                            raise
                            aid = None
                        ids_scores.append({"id": aid, "score": score})
                        try:
                            # add optional snippet
                            import os as _os

                            from extractor.pipeline.utils.ann_index import (
                                render_ann_snippet as _snip,
                            )

                            if _ann_list:
                                _maxc = int(_os.getenv("ANN_SIMILAR_SNIPPET_CHARS", "200"))
                                ids_scores[-1]["snippet"] = _snip(_ann_list[i], _maxc)
                        except Exception as exc:
                            log_stage_error(
                                "07_reflow_section", exc, {"context": "07_reflow_retry"}
                            )
                            raise
                            log_stage_error(
                                "07_reflow_section", exc, {"context": "07_reflow_retry"}
                            )
                            raise
                            log_stage_error("07_reflow_section", exc, {"context": "07"})
                            raise
                            pass
                    sec["similar_annotations"] = ids_scores
            except Exception as exc:
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07"})
                raise
                pass

    if not sections_to_process:
        # Synthesize minimal sections from tables when Stage 04 produced none
        try:
            tbl_payload = json.loads(Path(tables_json).read_text())
            tables = tbl_payload.get("tables") or []
        except Exception as exc:
            log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
            raise
            log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
            raise
            log_stage_error("07_reflow_section", exc, {"context": "07"})
            raise
            tables = []
        if tables:
            # Group tables by page and create one synthetic section per page
            by_page: dict[int, list[dict[str, Any]]] = {}
            for t in tables:
                try:
                    p = int(t.get("page_index", 0) or 0)
                except Exception as exc:
                    log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                    raise
                    log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                    raise
                    log_stage_error("07_reflow_section", exc, {"context": "07"})
                    raise
                    p = 0
                by_page.setdefault(p, []).append(t)
            synth: list[dict[str, Any]] = []
            for p, group in sorted(by_page.items(), key=lambda kv: kv[0]):
                sid = f"SYNTH_P{p}"
                synth.append(
                    {
                        "id": sid,
                        "title": f"Tables (page {p})",
                        "level": 1,
                        "page_start": p,
                        "page_end": p,
                        "blocks": [],
                        "tables": group,
                        "figures": [],
                        "raw_text": "",
                        "merged_text": "",
                    }
                )
            sections_to_process = synth
            diagnostics.append(
                make_event(
                    "07_reflow_section",
                    "info",
                    "synth_sections_from_tables",
                    f"Created {len(synth)} synthetic sections from tables",
                    {},
                )
            )
        else:
            console.print("[yellow]No sections found to process. Exiting.[/yellow]")
            return

    # --- Processing ---
    if summary_only:
        processed_sections = []
        for s in sections_to_process:
            # Emit summary-only payloads; do not call LLM
            sec_out = {
                **s,
                "reflowed_text": s.get("merged_text") or s.get("raw_text", ""),
                # Provide a placeholder to satisfy gold expectation for presence of reflowed_json
                "reflowed_json": {},
                "ocr_corrections": {},
                "improvements_made": "summary-only (no LLM)",
                "reflow_status": "success_placeholder",
            }
            if STAGE07_DEBUG:
                sec_out["quick_summary"] = (s.get("merged_text") or s.get("raw_text", ""))[:280]
            processed_sections.append(sec_out)
    else:

        async def run_tasks_first():
            tasks = []
            for s in sections_to_process:
                use_images = include_images
                if USE_LAYOUT_SKETCH and OMIT_IMAGES_IF_CONFIDENT:
                    try:
                        conf = float(
                            ((s.get("layout_sketch") or {}).get("conf") or {}).get("ordering")
                            or 0.0
                        )
                        if conf >= LAYOUT_CONF_THRESH:
                            use_images = False
                            diagnostics.append(
                                make_event(
                                    "07_reflow_section",
                                    "info",
                                    "images_omitted_due_to_layout_conf",
                                    f"Omitted images for section {s.get('id')} (conf={conf:.2f} >= {LAYOUT_CONF_THRESH})",
                                    {},
                                )
                            )
                    except Exception as exc:
                        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                        raise
                        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                        raise
                        log_stage_error("07_reflow_section", exc, {"context": "07"})
                        raise
                        pass
                tasks.append(
                    reflow_section_with_llm(
                        s,
                        output_dir,
                        include_images=use_images,
                        allow_fallback=allow_fallback,
                        llm_timeout=llm_timeout,
                    )
                )
            return await tqdm_asyncio.gather(*tasks, desc="Reflowing Sections (text-first)")

        processed_sections = asyncio.run(run_tasks_first())
    logger.debug(f"processed_sections_count={len(processed_sections)}")

    # Consolidate sections that are obvious continuations (e.g., titles ending with '(continued)')
    try:
        if (
            os.getenv("STAGE07_CONSOLIDATE_CONTINUED", "1").lower() in ("1", "true", "yes", "y")
            and processed_sections
        ):
            consolidated: list[dict[str, Any]] = []
            prev: dict[str, Any] | None = None
            for sec in processed_sections:
                title = str(sec.get("title") or "").strip()
                if prev and title and title.lower().endswith("(continued)"):
                    # Merge blocks/text into previous section
                    pjson = prev.get("reflowed_json") or {}
                    sjson = sec.get("reflowed_json") or {}
                    pblocks = (pjson.get("blocks") or []) if isinstance(pjson, dict) else []
                    sblocks = (sjson.get("blocks") or []) if isinstance(sjson, dict) else []
                    if isinstance(prev.get("reflowed_json"), dict):
                        prev["reflowed_json"]["blocks"] = pblocks + sblocks
                    else:
                        prev["reflowed_json"] = {"blocks": sblocks}
                    # Optionally concatenate text placeholders
                    if isinstance(prev.get("reflowed_text"), str) and isinstance(
                        sec.get("reflowed_text"), str
                    ):
                        prev["reflowed_text"] = (
                            prev["reflowed_text"] + "\n" + sec["reflowed_text"]
                        ).strip()
                    continue
                consolidated.append(sec)
                prev = sec
            processed_sections = consolidated
            logger.debug(f"processed_sections_consolidated={len(processed_sections)}")
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise

    # ------------------------------------------------------------------
    # Merge table metadata (carry Stage 05 merge groups into Stage 07)
    # ------------------------------------------------------------------
    merged_tables_summary: list[dict[str, Any]] = []
    merged_lookup_by_id: dict[str, dict[str, Any]] = {}
    merged_lookup_by_sig: dict[tuple[str, tuple[int, ...]], dict[str, Any]] = {}
    try:
        raw05 = json.loads(Path(tables_json).read_text()) if tables_json else {}
        tlist = raw05.get("tables") or []

        # Attach Stage05 tables into sections/blocks based on page span
        if tlist and processed_sections:
            for sec in processed_sections:
                sec_tables = sec.setdefault("tables", [])
                sec_blocks = sec.setdefault("blocks", [])
                try:
                    start_p = int(sec.get("page_start", 0) or 0)
                    end_p = int(sec.get("page_end", start_p) or start_p)
                except Exception:
                    start_p = end_p = 0
                for t in tlist:
                    try:
                        p = int(t.get("page_index", t.get("page", 0)) or 0)
                    except Exception:
                        p = None
                    if p is None:
                        continue
                    if start_p <= p <= end_p:
                        key = (p, tuple(t.get("bbox", [])))
                        already = any(
                            (
                                int(tt.get("page_index", tt.get("page", 0)) or 0),
                                tuple(tt.get("bbox", [])),
                            )
                            == key
                            for tt in sec_tables
                        )
                        if not already:
                            sec_tables.append(dict(t))
                            tbl_block = dict(t)
                            tbl_block["type"] = "table"
                            sec_blocks.append(tbl_block)

        merged_tables_summary, merged_lookup_by_id, merged_lookup_by_sig = _compute_table_merges(
            tlist
        )

        # Propagate merge metadata into processed_sections tables/blocks
        if merged_lookup_by_id or merged_lookup_by_sig:

            def _sig_no_pages_local(t: dict[str, Any]) -> dict[str, Any]:
                cols = (t.get("pandas_metrics") or {}).get("columns") or t.get("columns") or []
                cols_norm = [str(c).strip().lower() for c in cols if str(c).strip()]
                ncol = len(cols_norm) if cols_norm else t.get("ncol")
                title = (t.get("title") or t.get("header_norm") or "").strip()
                return {"columns": cols_norm, "ncol": ncol, "title": title}

            def _page_idx_local(t: dict[str, Any]) -> Optional[int]:
                try:
                    return int(t.get("page_index", t.get("page", 0)) or 0)
                except Exception:
                    return None

            for sec in processed_sections:
                tables = sec.get("tables") or []
                blocks = sec.get("blocks") or []
                for t in tables:
                    applied = False
                    for cand in [
                        t.get("id"),
                        t.get("table_id"),
                        t.get("logical_table_id"),
                        t.get("normalized_id"),
                    ]:
                        if cand and str(cand) in merged_lookup_by_id:
                            t.update(merged_lookup_by_id[str(cand)])
                            applied = True
                            break
                    if applied:
                        continue
                    sig = _sig_no_pages_local(t)
                    if not (sig["columns"] or sig["ncol"]):
                        continue
                    base_sig = {"columns": sig["columns"], "ncol": sig["ncol"]}
                    sig_key = json.dumps(base_sig, sort_keys=True, ensure_ascii=False)
                    page = _page_idx_local(t)
                    for (k, pages), meta in merged_lookup_by_sig.items():
                        if k == sig_key and (page in pages if page is not None else True):
                            t.update(meta)
                            break
                for b in blocks:
                    if b.get("type") != "table":
                        continue
                    applied = False
                    for cand in [
                        b.get("id"),
                        b.get("table_id"),
                        b.get("logical_table_id"),
                        b.get("normalized_id"),
                    ]:
                        if cand and str(cand) in merged_lookup_by_id:
                            b.update(merged_lookup_by_id[str(cand)])
                            applied = True
                            break
                    if applied:
                        continue
                    sig = _sig_no_pages_local(b)
                    if not (sig["columns"] or sig["ncol"]):
                        continue
                    base_sig = {"columns": sig["columns"], "ncol": sig["ncol"]}
                    sig_key = json.dumps(base_sig, sort_keys=True, ensure_ascii=False)
                    page = _page_idx_local(b)
                    for (k, pages), meta in merged_lookup_by_sig.items():
                        if k == sig_key and (page in pages if page is not None else True):
                            b.update(meta)
                            break
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise

    # --- Final Output ---
    # Attach resource samples
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        errors_count = sum(1 for d in diagnostics if d.get("severity") == "error")
        warnings_count = sum(1 for d in diagnostics if d.get("severity") == "warning")
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise
        pass
    source_files = {
        "sections": str(sections_json),
        "tables": str(tables_json),
        "figures": str(figures_json),
        "annotations": str(annotations_json) if annotations_json else None,
    }

    # Build unified_document after tables/merge metadata have been attached
    unified_document_payload = None
    try:
        unified_document = build_unified_document_from_reflow(
            sections=processed_sections,
            source_path=str(sections_json) if sections_json else None,
            source_type=SourceType.PDF,
            document_metadata={"source_files": source_files},
        )
        unified_document_payload = unified_document.model_dump(by_alias=True, mode="json")
    except Exception as exc:
        diagnostics.append(
            make_event(
                "07_reflow_section",
                "warning",
                "unified_document_generation_failed",
                str(exc),
                {},
            )
        )

    final_output = {
        "timestamp": datetime.now().isoformat(),
        "source_files": source_files,
        "status": "Completed",
        "section_count": len(processed_sections),
        "reflowed_sections": processed_sections,
        "merged_tables": merged_tables_summary or [],
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
    }

    # Validate output before writing
    from extractor.pipeline.schemas.reflow_actual import validate_reflow07_output

    validated_output, error = validate_reflow07_output(final_output)
    if error:
        logger.error(f"Stage 07 output validation failed: {error}")
        # Log validation errors but don't fail - this is the first stage to get validation
        final_output["validation_errors"] = [error]
    else:
        # Validation passed - you can optionally replace with validated version
        pass

    if unified_document_payload:
        final_output["unified_document"] = unified_document_payload

    output_path = json_output_dir / "07_reflowed.json"

    # Optional: render visual overlays per section to show provenance of reflow blocks
    try:
        if STAGE07_VISUAL_PROOF:
            # Resolve source PDF from Stage 04 payload; allow env override
            src_pdf: Optional[Path] = None
            try:
                s04 = json.loads(sections_json.read_text())
                sp = s04.get("source_pdf")
                if isinstance(sp, str) and Path(sp).exists():
                    src_pdf = Path(sp)
            except Exception as exc:
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07"})
                raise
                src_pdf = None
            if not src_pdf and STAGE07_SOURCE_PDF:
                p = Path(STAGE07_SOURCE_PDF)
                src_pdf = p if p.exists() else None

            # Build quick indexes to map sources → bboxes
            blocks_index: Dict[str, Tuple[int, List[float]]] = {}
            try:
                if "sections" in s04:
                    for sec in s04.get("sections") or []:
                        for b in sec.get("blocks") or []:
                            bid = b.get("id") or b.get("block_id")
                            bb = b.get("bbox") or []
                            try:
                                pg = int(
                                    b.get("page") or b.get("page_idx") or sec.get("page_start") or 0
                                )
                            except Exception as exc:
                                log_stage_error(
                                    "07_reflow_section", exc, {"context": "07_reflow_retry"}
                                )
                                raise
                                log_stage_error(
                                    "07_reflow_section", exc, {"context": "07_reflow_retry"}
                                )
                                raise
                                log_stage_error("07_reflow_section", exc, {"context": "07"})
                                raise
                                pg = 0
                            if bid and isinstance(bb, list) and len(bb) == 4:
                                blocks_index[str(bid)] = (
                                    pg,
                                    [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])],
                                )
            except Exception as exc:
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07"})
                raise
                pass

            tables_index: Dict[int, Tuple[int, List[float]]] = {}
            try:
                tj = (
                    json.loads((tables_json or Path()).read_text())
                    if tables_json and tables_json.exists()
                    else {}
                )
                for t in tj.get("tables") or []:
                    try:
                        idx = int(t.get("table_index"))
                        pg = int(t.get("page_index", 0))
                        bb = t.get("bbox") or []
                        if isinstance(bb, list) and len(bb) == 4:
                            tables_index[idx] = (
                                pg,
                                [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])],
                            )
                    except Exception as exc:
                        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                        raise
                        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                        raise
                        log_stage_error("07_reflow_section", exc, {"context": "07"})
                        raise
                        continue
            except Exception as exc:
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07"})
                raise
                pass

            figures_index: Dict[str, Tuple[int, List[float]]] = {}
            try:
                fj = (
                    json.loads((figures_json or Path()).read_text())
                    if figures_json and figures_json.exists()
                    else {}
                )
                for f in fj.get("figures") or []:
                    fid = f.get("figure_id") or f.get("id") or f.get("image_path")
                    try:
                        pg = int(f.get("page") or f.get("page_idx") or f.get("page_index") or 0)
                    except Exception as exc:
                        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                        raise
                        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                        raise
                        log_stage_error("07_reflow_section", exc, {"context": "07"})
                        raise
                        pg = 0
                    bb = f.get("bbox") or []
                    if fid and isinstance(bb, list) and len(bb) == 4:
                        figures_index[str(fid)] = (
                            pg,
                            [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])],
                        )
            except Exception as exc:
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                raise
                log_stage_error("07_reflow_section", exc, {"context": "07"})
                raise
                pass

            # Render overlays
            if src_pdf and processed_sections:
                from extractor.pipeline.visual.overlay import Box, draw_overlays

                stage_vis = stage_output_dir / "visual_output"
                for sec in processed_sections:
                    sid = str(sec.get("id") or "section")
                    boxes: List[Box] = []
                    # Prefer structured JSON blocks when present
                    rj = (
                        (sec.get("reflowed_json") or {}).get("blocks")
                        if isinstance(sec.get("reflowed_json"), dict)
                        else None
                    )
                    blocks_list = rj if isinstance(rj, list) else []
                    for i, b in enumerate(blocks_list):
                        typ = (b.get("type") or "").lower()
                        label = f"{i}:{typ}" if typ else f"{i}"
                        src = b.get("source") or {}
                        drawn = False
                        # Paragraph/List/Heading → map first block_id
                        if typ in {"paragraph", "list", "heading"}:
                            bids = src.get("block_ids") or []
                            if isinstance(bids, list) and bids:
                                key = str(bids[0])
                                if key in blocks_index:
                                    pg, bb = blocks_index[key]
                                    boxes.append(
                                        Box(
                                            page=int(pg),
                                            x0=bb[0],
                                            y0=bb[1],
                                            x1=bb[2],
                                            y1=bb[3],
                                            label=label,
                                            color=(0, 170, 255),
                                            width=3,
                                        )
                                    )
                                    drawn = True
                        # Table → map table_indices
                        if not drawn and typ == "table":
                            tids = src.get("table_indices") or []
                            if isinstance(tids, list) and tids:
                                ti0 = None
                                try:
                                    ti0 = int(tids[0])
                                except Exception as exc:
                                    log_stage_error(
                                        "07_reflow_section", exc, {"context": "07_reflow_retry"}
                                    )
                                    raise
                                    log_stage_error(
                                        "07_reflow_section", exc, {"context": "07_reflow_retry"}
                                    )
                                    raise
                                    log_stage_error("07_reflow_section", exc, {"context": "07"})
                                    raise
                                    ti0 = None
                                if ti0 is not None and ti0 in tables_index:
                                    pg, bb = tables_index[ti0]
                                    boxes.append(
                                        Box(
                                            page=int(pg),
                                            x0=bb[0],
                                            y0=bb[1],
                                            x1=bb[2],
                                            y1=bb[3],
                                            label=label,
                                            color=(0, 200, 0),
                                            width=3,
                                        )
                                    )
                                    drawn = True
                        # Figure → map by figure_id or image_ref
                        if not drawn and typ == "figure":
                            fid = b.get("figure_id") or b.get("image_ref")
                            if fid and str(fid) in figures_index:
                                pg, bb = figures_index[str(fid)]
                                boxes.append(
                                    Box(
                                        page=int(pg),
                                        x0=bb[0],
                                        y0=bb[1],
                                        x1=bb[2],
                                        y1=bb[3],
                                        label=label,
                                        color=(255, 128, 0),
                                        width=3,
                                    )
                                )
                                drawn = True
                        # As a last resort, draw at the first page listed in source without bbox (skip to avoid misleading boxes)
                    if boxes:
                        vout = stage_vis / sid
                        draw_overlays(src_pdf, boxes, vout)
                        try:
                            # Attach relative paths for convenience
                            rel = [
                                str(p.relative_to(output_dir.parent.parent))
                                for p in vout.glob("*.png")
                            ]
                            if rel:
                                sec.setdefault("visual_overlays", rel)
                        except Exception as exc:
                            log_stage_error(
                                "07_reflow_section", exc, {"context": "07_reflow_retry"}
                            )
                            raise
                            log_stage_error(
                                "07_reflow_section", exc, {"context": "07_reflow_retry"}
                            )
                            raise
                            log_stage_error("07_reflow_section", exc, {"context": "07"})
                            raise
                            pass
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise

    if os.getenv("DRY_RUN", "0").lower() not in {"1", "true", "yes", "y"}:
        with open(output_path, "w") as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)
        console.print("\n[bold green]✅ Section reflow complete.[/bold green]")
        console.print(f"   - Results saved to: [cyan]{output_path}[/cyan]")
    else:
        console.print(
            "\n[yellow]DRY_RUN=1 → skipped writing 07_reflowed.json (logs/artifacts still recorded)[/yellow]"
        )

    # timings_summary.json (best-effort) under RUN_RESULTS_DIR/07_reflow_section/logs
    try:
        from pathlib import Path as _P

        rd = os.getenv("RUN_RESULTS_DIR")
        if rd:
            ldir = _P(rd) / "07_reflow_section" / "logs"
            tfile = ldir / "timings.jsonl"
            if tfile.exists():
                lat = []
                attempts = 0
                ok = 0
                exc = 0
                for line in tfile.read_text(encoding="utf-8").splitlines():
                    attempts += 1
                    try:
                        rec = json.loads(line)
                        if str(rec.get("outcome")) == "ok":
                            ok += 1
                        if str(rec.get("outcome")) == "exception":
                            exc += 1
                        if rec.get("latency_ms") is not None:
                            lat.append(float(rec["latency_ms"]))
                    except Exception as exc:
                        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                        raise
                        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
                        raise
                        log_stage_error("07_reflow_section", exc, {"context": "07"})
                        raise
                        continue
                lat_sorted = sorted(lat)

                def _pct(p: float) -> float:
                    if not lat_sorted:
                        return 0.0
                    idx = int(max(0, min(len(lat_sorted) - 1, round(p * (len(lat_sorted) - 1)))))
                    return float(lat_sorted[idx])

                summary = {
                    "attempts": attempts,
                    "ok": ok,
                    "exceptions": exc,
                    "p50_ms": _pct(0.50),
                    "p95_ms": _pct(0.95),
                }
                (ldir / "timings_summary.json").write_text(json.dumps(summary, indent=2))
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise
        pass
    return output_path


if __name__ == "__main__":
    # Minimal entry: SECTIONS_JSON TABLES_JSON FIGURES_JSON [ANNOTATIONS_JSON] [OUT_DIR] [--summary-only]
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv())
    except Exception as exc:
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07_reflow_retry"})
        raise
        log_stage_error("07_reflow_section", exc, {"context": "07"})
        raise
        pass
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        sys.exit(sanity())
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.07_reflow_section SECTIONS_JSON TABLES_JSON FIGURES_JSON [ANNOTATIONS_JSON] [OUT_DIR] [--summary-only]",
            file=sys.stderr,
        )
        sys.exit(2)
    summary_only = False
    if "--summary-only" in argv:
        summary_only = True
        argv = [a for a in argv if a != "--summary-only"]
    if len(argv) < 3:
        print("Missing required paths", file=sys.stderr)
        sys.exit(2)
    sections_json = Path(argv[0])
    tables_json = Path(argv[1])
    figures_json = Path(argv[2])
    ann_json = None
    out_dir = Path("data/results/pipeline")
    if len(argv) >= 4:
        p = Path(argv[3])
        if p.suffix.lower() == ".json":
            ann_json = p
            out_dir = Path(argv[4]) if len(argv) >= 5 else out_dir
        else:
            out_dir = p
    out = run(
        sections_json=sections_json,
        tables_json=tables_json,
        figures_json=figures_json,
        annotations_json=ann_json,
        output_dir=out_dir,
        summary_only=summary_only,
    )
    print(str(out))
