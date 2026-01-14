from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Optional

import duckdb

from ..core import Step
from ..utils import ContractLoopError, assert_helping, check_json_file_valid, ensure_text
from .base import BaseAdapter


class ExtractorAdapter(BaseAdapter):
    name = "extractor"

    def build_steps(self, args: argparse.Namespace, fixture: Optional[dict]) -> list[Step]:
        steps = [
            Step(
                "01_annotation_processor",
                "extractor.pipeline.steps.s01_annotation_processor",
                _args_s01,
                output_paths=("01_annotation_processor",),
            ),
            Step(
                "02_marker_extractor",
                "extractor.pipeline.steps.s02_marker_extractor",
                _args_base,
                output_paths=("02_marker_extractor",),
            ),
            Step(
                "03_suspicious_headers",
                "extractor.pipeline.steps.s03_suspicious_headers",
                _args_base,
                output_paths=("03_suspicious_headers",),
            ),
            Step(
                "04_section_builder",
                "extractor.pipeline.steps.s04_section_builder",
                _args_base,
                output_paths=("04_section_builder",),
            ),
            Step(
                "04a_layout_audit",
                "extractor.pipeline.steps.s04a_layout_audit",
                _args_base,
                verify_cli=False,
                custom_verify=lambda o, _a: _verify_04a(o),
                output_paths=("04a_layout_audit",),
            ),
            Step(
                "05_table_extractor",
                "extractor.pipeline.steps.s05_table_extractor",
                _args_base,
                output_paths=("05_table_extractor",),
            ),
            Step(
                "05b_table_describer",
                "extractor.pipeline.steps.s05b_table_describer",
                _args_base,
                enabled=lambda a: a.mode == "full",
                output_paths=("05b_table_describer",),
            ),
            Step(
                "05c_table_merger",
                "extractor.pipeline.steps.s05c_table_merger",
                _args_base,
                output_paths=("05c_table_merger",),
            ),
            Step(
                "06_figure_extractor",
                "extractor.pipeline.steps.s06_figure_extractor",
                _args_s06,
                output_paths=("06_figure_extractor",),
            ),
            Step(
                "06b_figure_describer",
                "extractor.pipeline.steps.s06b_figure_describer",
                _args_base,
                enabled=lambda a: a.mode == "full",
                output_paths=("06b_figure_describer",),
            ),
            Step(
                "07_assemble_corpus",
                "extractor.pipeline.steps.s07_duckdb_ingest",
                _args_base,
                verify_cli=False,
                custom_verify=lambda o, _a: _verify_07(o),
                output_paths=(),
            ),
            Step(
                "08_extract_requirements",
                "extractor.pipeline.steps.s08_extract_requirements",
                _args_base,
                verify_cli=False,
                custom_verify=lambda o, a: _verify_08(o, a.min_requirements),
                enabled=lambda a: a.mode == "full",
                output_paths=("08_extract_requirements",),
            ),
            Step(
                "09_section_summarizer",
                "extractor.pipeline.steps.s09_section_summarizer",
                _args_base,
                enabled=lambda a: a.mode == "full",
                output_paths=("09_section_summarizer",),
            ),
            Step(
                "10_markdown_exporter",
                "extractor.pipeline.steps.s10_markdown_exporter",
                _args_base,
                output_paths=("10_markdown_exporter",),
            ),
            Step(
                "14_report_generator",
                "extractor.pipeline.steps.s14_report_generator",
                _args_base,
                output_paths=("14_report_generator",),
            ),
        ]

        has_lean4 = bool(fixture and (fixture.get("steps") or {}).get("08_lean4_theorem_prover"))
        if has_lean4 and args.mode == "full" and not args.skip_lean4:
            lean4_step = Step(
                "08_lean4_theorem_prover",
                "extractor.pipeline.steps.s08_lean4_theorem_prover",
                _args_base,
                verify_cli=False,
                custom_verify=lambda _o, _a: None,
                enabled=lambda a: a.mode == "full",
                execute=False,
                output_paths=("08_lean4_theorem_prover",),
            )
            insert_at = next(
                (i for i, s in enumerate(steps) if s.name == "08_extract_requirements"), None
            )
            if insert_at is None:
                steps.append(lean4_step)
            else:
                steps.insert(insert_at + 1, lean4_step)

        return steps

    def clean_downstream(
        self,
        out: Path,
        steps: list[Step],
        start_index: int,
        index_by_name: dict[str, int],
    ) -> None:
        for step in steps[start_index:]:
            for rel in step.output_paths:
                target = out / rel
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                elif target.exists():
                    try:
                        target.unlink()
                    except Exception:
                        pass

        db_path = out / "pipeline.duckdb"
        idx_07 = index_by_name.get("07_assemble_corpus")
        idx_08 = index_by_name.get("08_extract_requirements")
        idx_09 = index_by_name.get("09_section_summarizer")
        idx_lean4 = index_by_name.get("08_lean4_theorem_prover")

        if idx_07 is not None and start_index <= idx_07:
            if db_path.exists():
                try:
                    db_path.unlink()
                except Exception:
                    pass
        else:
            if idx_08 is not None and start_index <= idx_08:
                _clear_requirements(db_path)
            if idx_lean4 is not None and start_index <= idx_lean4:
                _clear_lean4(db_path)
            if idx_09 is not None and start_index <= idx_09:
                _clear_section_summaries(db_path)

        for extra in ("manifest.json", "timings.jsonl", "timings_summary.json"):
            target = out / extra
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass
        # NOTE: judge_index.jsonl persists across retries for auditability.

    def verify_fixture_step(self, step_name: str, out: Path, fixture: dict) -> None:
        steps = fixture.get("steps", {})
        expected = steps.get(step_name)
        if not expected:
            return

        if step_name == "08_lean4_theorem_prover":
            min_proofs = int(expected.get("min_proofs", 1))
            db_path = out / "pipeline.duckdb"
            assert_helping(db_path.exists(), f"pipeline.duckdb exists at {db_path}")
            _check_table_has_rows(db_path, "lean4_proofs", min_rows=min_proofs)
            return

        rel_path = expected.get("json")
        if not rel_path:
            return
        json_path = out / rel_path
        keys = expected.get("keys") or []
        data = check_json_file_valid(json_path, key_check=keys)

        if step_name == "01_annotation_processor":
            annots = data.get("annotations", [])
            min_annots = int(expected.get("min_annotations", 0))
            assert_helping(len(annots) >= min_annots, f"S01 annotations >= {min_annots}")
            clean_pdf = Path(data.get("clean_pdf_path", ""))
            assert_helping(clean_pdf.exists(), f"S01 clean PDF exists at {clean_pdf}")
            return

        if step_name == "02_marker_extractor":
            block_count = int(data.get("block_count", 0) or 0)
            min_blocks = int(expected.get("min_blocks", 1))
            assert_helping(block_count >= min_blocks, f"S02 block_count >= {min_blocks}")
            return

        if step_name == "03_suspicious_headers":
            blocks = data.get("blocks", [])
            min_verified = int(expected.get("min_verified_blocks", 0))
            assert_helping(len(blocks) >= min_verified, f"S03 verified blocks >= {min_verified}")
            return

        if step_name == "04_section_builder":
            sections = data.get("sections", [])
            min_sections = int(expected.get("min_sections", 1))
            assert_helping(len(sections) >= min_sections, f"S04 sections >= {min_sections}")
            return

    def verify_visuals(
        self,
        step_name: str,
        out: Path,
        args: argparse.Namespace,
        _fixture: Optional[dict],
    ) -> None:
        if not args.debug:
            return
        if step_name in REQUIREMENT_LOCATION_STEPS:
            _assert_requirement_locations(out)
            return
        if step_name not in VISUAL_REQUIRED_STEPS:
            return
        _ensure_visual_symlink(out, step_name)
        _assert_visual_mapping(step_name, out)

    def collect_llm_samples(self, step_name: str, out: Path, fixture: dict) -> list[str]:
        expected = (fixture.get("steps") or {}).get(step_name) or {}
        judge = expected.get("judge") or {}
        min_chars = int(judge.get("min_chars", 40))
        sample_size = int(judge.get("sample_size", 3))

        if step_name == "05b_table_describer":
            json_path = out / expected.get("json", "")
            data = check_json_file_valid(json_path, key_check=["tables"])
            tables = data.get("tables", [])
            texts = [t.get("llm_description") or t.get("llm_title") for t in tables]
            return _select_samples(texts, sample_size, min_chars)

        if step_name == "06b_figure_describer":
            json_path = out / expected.get("json", "")
            data = check_json_file_valid(json_path, key_check=["figures"])
            figs = data.get("figures", [])
            texts = [f.get("llm_description") or f.get("llm_title") for f in figs]
            return _select_samples(texts, sample_size, min_chars)

        if step_name == "08_extract_requirements":
            db_path = out / "pipeline.duckdb"
            con = duckdb.connect(str(db_path), read_only=True)
            try:
                rows = con.execute(
                    "SELECT text, citation_snippet FROM requirements WHERE text IS NOT NULL ORDER BY id LIMIT 50"
                ).fetchall()
            finally:
                con.close()
            texts = []
            for text, cite in rows:
                chunk = f"{text}\nCitation: {cite}" if cite else str(text)
                texts.append(chunk)
            return _select_samples(texts, sample_size, min_chars)

        if step_name == "09_section_summarizer":
            db_path = out / "pipeline.duckdb"
            con = duckdb.connect(str(db_path), read_only=True)
            try:
                rows = con.execute(
                    "SELECT llm_summary FROM sections WHERE llm_summary IS NOT NULL ORDER BY id LIMIT 50"
                ).fetchall()
            finally:
                con.close()
            texts = [r[0] for r in rows]
            return _select_samples(texts, sample_size, min_chars)

        return []

    def questions_for_step(self, step_name: str):
        questions = {
            "01_annotation_processor": [
                "Is the input PDF path correct and readable?",
                "Does the output dir contain a *_clean.pdf after S01?",
                "Are there any errors in 01_annotation_processor/stage_01.log?",
            ],
            "02_marker_extractor": [
                "Does 01_annotation_processor contain a *_clean.pdf?",
                "Are block_count and blocks non-zero in 02_marker_blocks.json?",
                "Any errors in 02_marker_extractor/stage.log?",
            ],
            "03_suspicious_headers": [
                "Are there suspicious_header candidates in 02_marker_blocks.json?",
                "Is LLM verification enabled/available (CHUTES_* env)?",
                "Any errors in 03_suspicious_headers/stage.log?",
            ],
            "04_section_builder": [
                "Do blocks in 03_verified_blocks.json have bbox/page data?",
                "Is the section_count > 0 in 04_sections.json?",
                "Any errors in 04_section_builder/stage.log?",
            ],
            "04a_layout_audit": [
                "Which sections are reported out of order in 04a_layout_audit.json?",
                "Are bbox coordinates consistent and normalized?",
            ],
            "05_table_extractor": [
                "Is camelot installed and returning tables for this PDF?",
                "Are tables empty or filtered out by heuristics?",
                "Any errors in 05_table_extractor/stage.log?",
            ],
            "05b_table_describer": [
                "Are table images present under 05_table_extractor/visual_output?",
                "Are LLM credentials set (CHUTES_API_KEY / CHUTES_TEXT_MODEL)?",
                "Do any tables have llm_description fields?",
            ],
            "05c_table_merger": [
                "Does 05b_tables.json or 05_tables.json exist?",
                "Are table headers/columns aligned for merge detection?",
            ],
            "06_figure_extractor": [
                "Are figure images being written to 06_figure_extractor/visual_output?",
                "Do figures in 06_figures.json have bbox/page values?",
            ],
            "06b_figure_describer": [
                "Are figure images present for LLM description?",
                "Are LLM credentials set and reachable?",
            ],
            "07_assemble_corpus": [
                "Does pipeline.duckdb exist after S07?",
                "Are sections/tables/figures tables populated in DuckDB?",
            ],
            "08_extract_requirements": [
                "Are requirements rows being inserted into DuckDB?",
                "Do citations match source text?",
                "Are LLM credentials set and valid?",
            ],
            "08_lean4_theorem_prover": [
                "Are there requirements in DuckDB to prove?",
                "Is certainly/lean4 available and reachable?",
            ],
            "09_section_summarizer": [
                "Are sections present in DuckDB?",
                "Are llm_summary fields populated?",
                "Are LLM credentials set and valid?",
            ],
            "10_markdown_exporter": [
                "Does pipeline.duckdb exist and contain merged_content?",
                "Is 10_markdown_exporter/markdown_output/full_document.md non-empty?",
            ],
            "14_report_generator": [
                "Is 14_report_generator/json_output/final_report.json created?",
                "Any errors in 14_report_generator/stage.log?",
            ],
        }
        return questions.get(step_name, ["What specific contract check is failing?"])


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VISUAL_REQUIRED_STEPS = {
    "01_annotation_processor",
    "02_marker_extractor",
    "03_suspicious_headers",
    "04_section_builder",
    "04a_layout_audit",
    "05_table_extractor",
    "05c_table_merger",
    "06_figure_extractor",
    "09_section_summarizer",
}

REQUIREMENT_LOCATION_STEPS = {"08_extract_requirements"}

VISUAL_SPECS = {
    "01_annotation_processor": {
        "json": "01_annotation_processor/json_output/01_annotations.json",
        "key": "annotations",
        "path_fields": ("image_path",),
    },
    "02_marker_extractor": {
        "json": "02_marker_extractor/json_output/02_marker_blocks.json",
        "key": "blocks",
        "path_fields": ("visual_path",),
    },
    "03_suspicious_headers": {
        "json": "03_suspicious_headers/json_output/03_verified_blocks.json",
        "key": "blocks",
        "path_fields": ("context_image_path", "visual_path", "image_path"),
    },
    "04_section_builder": {
        "json": "04_section_builder/json_output/04_sections.json",
        "key": "sections",
        "path_fields": ("visual_path",),
    },
    "04a_layout_audit": {
        "json": "04a_layout_audit/json_output/04a_layout_audit.json",
        "key": "visuals",
        "path_fields": ("visual_path",),
    },
    "05_table_extractor": {
        "json": "05_table_extractor/json_output/05_tables.json",
        "key": "tables",
        "path_fields": ("table_image_path", "image_path"),
    },
    "05c_table_merger": {
        "json": "05c_table_merger/json_output/05c_tables.json",
        "key": "tables",
        "path_fields": ("visual_path", "table_image_path", "image_path"),
    },
    "06_figure_extractor": {
        "json": "06_figure_extractor/json_output/06_figures.json",
        "key": "figures",
        "path_fields": ("image_path", "img_path"),
    },
    "09_section_summarizer": {
        "json": "09_section_summarizer/json_output/09_section_summaries.json",
        "key": "visuals",
        "path_fields": ("visual_path",),
    },
}


def _filter_s03(item: dict) -> bool:
    return bool(
        item.get("llm_verification")
        or item.get("requires_verification")
        or item.get("suspicious_header")
    )


VISUAL_FILTERS = {
    "03_suspicious_headers": _filter_s03,
}


def _visual_dir(out: Path, step_name: str) -> Path:
    return out / step_name / "visual_output"


def _list_images(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return [
        p
        for p in path.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]


def _resolve_visual_path(out: Path, raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(str(raw))
    if path.is_absolute():
        return path
    candidate = out / path
    if candidate.exists():
        return candidate
    fallback = out.parent / path
    if fallback.exists():
        return fallback
    return candidate


def _assert_visual_mapping(step_name: str, out: Path) -> None:
    spec = VISUAL_SPECS.get(step_name)
    if not spec:
        raise ContractLoopError(f"{step_name}: missing visual spec mapping")
    data = _load_json(out, spec["json"])
    items = data.get(spec["key"]) or []
    assert_helping(isinstance(items, list), f"{step_name}: {spec['key']} must be a list")
    filter_fn = VISUAL_FILTERS.get(step_name)
    if filter_fn:
        items = [item for item in items if isinstance(item, dict) and filter_fn(item)]
    visual_dir = _visual_dir(out, step_name)
    expected_count = len(items)
    images = _list_images(visual_dir)
    actual = len(images)
    if expected_count == 0:
        assert_helping(
            actual == 0,
            f"{step_name}: expected 0 visuals but found {actual} in {visual_dir}",
        )
        return
    assert_helping(visual_dir.exists(), f"{step_name}: visual_output missing at {visual_dir}")
    assert_helping(
        actual == expected_count,
        (
            f"{step_name}: visual_output count mismatch. "
            f"expected {expected_count}, found {actual} in {visual_dir}"
        ),
    )

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ContractLoopError(f"{step_name}: item {idx} is not a dict")
        found_path = None
        for field in spec["path_fields"]:
            candidate = _resolve_visual_path(out, item.get(field))
            if candidate:
                found_path = candidate
                break
        if not found_path:
            raise ContractLoopError(
                f"{step_name}: missing visual path for item {idx} ({spec['path_fields']})"
            )
        if not found_path.exists():
            raise ContractLoopError(
                f"{step_name}: visual path missing on disk: {found_path}"
            )
        try:
            found_path.relative_to(visual_dir)
        except Exception:
            raise ContractLoopError(
                f"{step_name}: visual path not under visual_output: {found_path}"
            )


def _ensure_visual_symlink(out: Path, step_name: str) -> None:
    visual_dir = _visual_dir(out, step_name)
    if not visual_dir.exists():
        return
    symlink_root = out / "visuals"
    symlink_root.mkdir(parents=True, exist_ok=True)
    target = symlink_root / step_name
    if target.exists() or target.is_symlink():
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            import shutil
            shutil.rmtree(target, ignore_errors=True)
    try:
        target.symlink_to(visual_dir, target_is_directory=True)
    except Exception:
        pass


def _load_json(out: Path, rel_path: str, *, keys: list[str] | None = None) -> dict:
    json_path = out / rel_path
    return check_json_file_valid(json_path, key_check=keys)


def _count_db_rows(db_path: Path, query: str, params: Optional[list] = None) -> int:
    assert_helping(db_path.exists(), f"pipeline.duckdb exists at {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        row = con.execute(query, params or []).fetchone()
        return int(row[0]) if row else 0
    finally:
        con.close()


def _assert_requirement_locations(out: Path) -> None:
    db_path = out / "pipeline.duckdb"
    assert_helping(db_path.exists(), f"pipeline.duckdb exists at {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT id, page, y0, metadata_json FROM requirements ORDER BY id"
        ).fetchall()
    finally:
        con.close()

    if not rows:
        raise ContractLoopError("08_extract_requirements: no requirements found in DuckDB")

    missing = []
    invalid = []
    bad_source = []
    for req_id, page, y0, metadata_json in rows:
        if page is None or y0 is None:
            missing.append(req_id)
            continue
        if not metadata_json:
            invalid.append(req_id)
            continue
        try:
            data = json.loads(metadata_json)
        except Exception:
            invalid.append(req_id)
            continue
        bbox = data.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            invalid.append(req_id)
            continue
        source = data.get("bbox_source")
        if source not in {"block", "table"}:
            bad_source.append(req_id)

    if missing:
        raise ContractLoopError(
            f"08_extract_requirements: missing page/y0 for {len(missing)} requirements"
        )
    if invalid:
        raise ContractLoopError(
            f"08_extract_requirements: missing or invalid metadata_json for {len(invalid)} requirements"
        )
    if bad_source:
        raise ContractLoopError(
            f"08_extract_requirements: bbox_source not block/table for {len(bad_source)} requirements"
        )


def _args_base(out: Path, _args: argparse.Namespace) -> list[str]:
    return ["--pipeline-dir", str(out)]


def _args_s01(out: Path, args: argparse.Namespace) -> list[str]:
    return ["--pipeline-dir", str(out), "--pdf", str(args.pdf)]


def _args_s06(out: Path, _args: argparse.Namespace) -> list[str]:
    return ["--pipeline-dir", str(out), "--pdf-dir", str(out / "01_annotation_processor")]


def _check_table_has_rows(
    db_path: Path,
    table_name: str,
    min_rows: int = 1,
    con: Optional[duckdb.DuckDBPyConnection] = None,
) -> int:
    should_close = False
    if con is None:
        if not db_path.exists():
            raise ContractLoopError(f"Database not found: {db_path}")
        con = duckdb.connect(str(db_path), read_only=True)
        should_close = True
    try:
        count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        if count < min_rows:
            raise ContractLoopError(
                f"Table '{table_name}' has {count} rows, expected at least {min_rows}."
            )
        return count
    finally:
        if should_close:
            con.close()


def _verify_04a(out: Path) -> None:
    audit_path = out / "04a_layout_audit" / "json_output" / "04a_layout_audit.json"
    data = check_json_file_valid(audit_path, key_check=["ok", "errors"])
    ok = bool(data.get("ok"))
    errors = int(data.get("errors", 0) or 0)
    assert_helping(ok and errors == 0, f"04a_layout_audit ok={ok} errors={errors}")


def _verify_07(out: Path) -> None:
    db_path = out / "pipeline.duckdb"
    if db_path.exists():
        try:
            con = duckdb.connect(str(db_path), read_only=True)
            con.close()
        except Exception:
            try:
                db_path.unlink()
            except Exception:
                pass

    assert_helping(db_path.exists(), f"pipeline.duckdb exists at {db_path}")
    for table in ("sections", "blocks", "tables", "figures", "merged_content"):
        min_rows = 1 if table == "merged_content" else 0
        _check_table_has_rows(db_path, table, min_rows=min_rows)


def _verify_08(out: Path, min_requirements: int) -> None:
    db_path = out / "pipeline.duckdb"
    assert_helping(db_path.exists(), f"pipeline.duckdb exists at {db_path}")
    _check_table_has_rows(db_path, "requirements", min_rows=min_requirements)


def _clear_requirements(db_path: Path) -> None:
    if not db_path.exists():
        return
    con = duckdb.connect(str(db_path))
    try:
        con.execute("DELETE FROM requirements")
    except Exception:
        pass
    finally:
        con.close()


def _clear_lean4(db_path: Path) -> None:
    if not db_path.exists():
        return
    con = duckdb.connect(str(db_path))
    try:
        con.execute("DELETE FROM lean4_proofs")
    except Exception:
        pass
    finally:
        con.close()


def _clear_section_summaries(db_path: Path) -> None:
    if not db_path.exists():
        return
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "UPDATE sections SET llm_summary = NULL, llm_key_concepts = NULL, llm_metadata = NULL"
        )
    except Exception:
        pass
    finally:
        con.close()


def _select_samples(items, limit: int, min_chars: int) -> list[str]:
    samples = []
    for item in items:
        s = ensure_text(item)
        if len(s) < min_chars:
            continue
        samples.append(s)
        if len(samples) >= limit:
            break
    return samples
