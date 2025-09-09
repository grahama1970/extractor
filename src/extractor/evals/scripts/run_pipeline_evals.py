#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from extractor.evals.extraction.compare_tables import (
    load_json,
    best_table_match_for_annotation,
    extract_table_columns_rows,
    compare_extracted_to_gold,
)
from extractor.evals.extraction.retune_camelot import retune_strategies_for_page
import importlib.util
import os


def _load_camelot_strategies() -> Dict[str, Dict[str, Any]]:
    """Dynamically load CAMELOT_STRATEGIES from Stage 05 to ensure alignment.

    Avoids importing a module with a leading numeric filename by using importlib.
    """
    here = Path(__file__).resolve()
    mod_path = here.parents[3] / "extractor" / "pipeline" / "steps" / "05_table_extractor.py"
    if not mod_path.exists():
        raise FileNotFoundError(f"Cannot find 05_table_extractor.py at {mod_path}")
    spec = importlib.util.spec_from_file_location("table_extractor05", str(mod_path))
    if spec is None or spec.loader is None:
        raise ImportError("Failed to prepare spec for 05_table_extractor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    strategies = getattr(module, "CAMELOT_STRATEGIES", None)
    if not isinstance(strategies, dict):
        raise AttributeError("CAMELOT_STRATEGIES not found or invalid in 05_table_extractor.py")
    return strategies


app = typer.Typer(help="Run pipeline evals across multiple PDFs (tables first)")


def _run(cmd: List[str], cwd: Optional[Path] = None) -> int:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    return proc.returncode


def _now_ts() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _slug_from_pdf(pdf: Path) -> str:
    return pdf.stem[:50].lower()


def _parse_human_note(note: Optional[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not note or not isinstance(note, str):
        return out
    for ln in [x.strip() for x in note.strip().splitlines() if x.strip()]:
        if '=' in ln and not ln.startswith('#'):
            k, v = ln.split('=', 1)
            out[k.strip()] = v.strip()
    return out


@app.command()
def run(
    registry: Path = typer.Option(Path("src/extractor/evals/datasets/docs_registry.json"), help="Docs registry JSON"),
    out: Path = typer.Option(Path("data/evals"), help="Base output directory for eval artifacts"),
    row_tol: float = typer.Option(0.2, help="Row count tolerance fraction"),
    retune_on_fail: bool = typer.Option(True, help="Try Stage 05 Camelot strategies per failing table and report best match"),
):
    data = json.loads(registry.read_text(encoding="utf-8"))
    strategies = _load_camelot_strategies()
    docs = data.get("docs") or []
    ts = _now_ts()
    run_root = out / "runs" / ts / "docs"
    run_root.mkdir(parents=True, exist_ok=True)

    overall: List[Dict[str, Any]] = []

    for doc in docs:
        pdf = Path(doc.get("pdf") or "")
        slug = doc.get("slug") or _slug_from_pdf(pdf)
        tasks = doc.get("tasks") or ["tables"]
        if not pdf.exists():
            typer.secho(f"Missing PDF: {pdf}", fg=typer.colors.RED)
            continue
        doc_root = run_root / slug
        pipe_root = doc_root / "pipeline"
        pipe_root.mkdir(parents=True, exist_ok=True)

        # Stage 01: Annotations → JSON
        typer.echo(f"[doc={slug}] Stage 01: annotations")
        rc = _run([
            sys.executable,
            "src/extractor/pipeline/steps/01_annotation_processor.py",
            "run", str(pdf), "-o", str(doc_root), "--images", "--include-freetext"
        ])
        if rc != 0:
            typer.secho(f"Stage 01 failed for {slug}", fg=typer.colors.RED)
            continue

        if "tables" in tasks:
            # Stage 05: Table extraction
            typer.echo(f"[doc={slug}] Stage 05: tables")
            # Prepare debug bundle with empty sections and the clean PDF from Stage 01 output
            ann_stage_dir = doc_root / "01_annotation_processor"
            try:
                clean_pdf = next(ann_stage_dir.glob("*_clean.pdf"))
            except StopIteration:
                typer.secho(f"No clean PDF found in {ann_stage_dir}", fg=typer.colors.RED)
                continue
            bundle_path = doc_root / "05_bundle.json"
            bundle_path.write_text(json.dumps({
                "sections": [{"id": "_all", "bbox": [0,0,0,0], "page_start": 0, "page_end": 100000}],
                "clean_pdf": str(clean_pdf)
            }, indent=2))
            rc = _run([
                sys.executable,
                "src/extractor/pipeline/steps/05_table_extractor.py",
                "debug-bundle", str(bundle_path), "-o", str(doc_root)
            ])
            if rc != 0:
                typer.secho(f"Stage 05 failed for {slug}", fg=typer.colors.RED)
                continue

            # Load outputs
            ann_path = doc_root / "01_annotation_processor" / "json_output" / "01_annotations.json"
            tab_path = doc_root / "05_table_extractor" / "json_output" / "05_tables.json"
            if not ann_path.exists() or not tab_path.exists():
                typer.secho(f"Missing outputs for {slug}", fg=typer.colors.RED)
                continue
            ann_data = load_json(ann_path)
            tables_data = load_json(tab_path)
            anno_list = ann_data.get("annotations") or []
            tables_list = tables_data.get("tables") or []

            # For each Box with a machine-readable FreeText human_note
            doc_results: List[Dict[str, Any]] = []
            for a in anno_list:
                try:
                    if (a.get("type") or "").lower() == "freetext":
                        continue
                    note = a.get("human_note")
                    parsed = _parse_human_note(note)
                    if not parsed.get("id") or parsed.get("type") != "table" or not parsed.get("expected_json"):
                        continue
                    gold_path = Path(parsed["expected_json"]).resolve()
                    if not gold_path.exists():
                        doc_results.append({"id": parsed.get("id"), "error": f"gold_json_missing: {gold_path}"})
                        continue
                    gold = load_json(gold_path)
                    page_index = int(a.get("page", 1)) - 1
                    ann_rect = a.get("original_rect") or a.get("expanded_rect") or [0,0,0,0]
                    match = best_table_match_for_annotation(tables_list, page_index, ann_rect)
                    if not match:
                        entry: Dict[str, Any] = {"id": parsed.get("id"), "error": "no_extracted_table_match"}
                        if retune_on_fail:
                            best = retune_strategies_for_page(pdf, page_index, ann_rect, strategies=strategies)
                            entry["retune_best"] = best
                        doc_results.append(entry)
                        continue
                    ex_cols, ex_rows = extract_table_columns_rows(match)
                    cmp = compare_extracted_to_gold(ex_cols, ex_rows, gold, row_tol=row_tol)
                    result_entry: Dict[str, Any] = {
                        "id": parsed.get("id"),
                        "page": a.get("page"),
                        "gold": parsed.get("expected_json"),
                        "match": cmp,
                    }
                    if retune_on_fail and not cmp.get("ok"):
                        best = retune_strategies_for_page(pdf, page_index, ann_rect, strategies=strategies)
                        result_entry["retune_best"] = best
                    doc_results.append(result_entry)
                except Exception as e:
                    doc_results.append({"id": a.get("id"), "error": f"exception: {e}"})

            # Save per-doc summary
            (doc_root / "summary_tables.json").write_text(json.dumps(doc_results, indent=2, ensure_ascii=False))
            overall.append({"doc": slug, "tables": doc_results})

    # Save overall summary
    out_sum = run_root / "summary.json"
    out_sum.write_text(json.dumps(overall, indent=2, ensure_ascii=False))
    typer.echo(f"Wrote eval summary: {out_sum}")


if __name__ == "__main__":
    app()
