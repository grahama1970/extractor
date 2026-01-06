#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "duckdb>=0.9.0",
# ]
# ///
"""Fail-fast pipeline contract verifier with a Ralph-style retry loop."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

import duckdb

from extractor.pipeline.utils import ralph


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "results" / "pipeline_contract"
JUDGE_SCHEMA = ROOT / "contracts" / "judges" / "llm_judge.schema.json"


def _env_with_pythonpath() -> dict:
    env = os.environ.copy()
    src_root = str(ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_root if not existing else f"{src_root}{os.pathsep}{existing}"
    return env


def _run_cmd(cmd: list[str], env: dict) -> int:
    print(">>", " ".join(cmd))
    return subprocess.run(cmd, env=env).returncode


def _load_fixture(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Fixture file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _judge_with_codex(prompt: str, model: Optional[str]) -> dict:
    if not JUDGE_SCHEMA.exists():
        raise FileNotFoundError(f"Judge schema missing: {JUDGE_SCHEMA}")
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)
    cmd = [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--output-schema",
        str(JUDGE_SCHEMA),
        "--output-last-message",
        str(out_path),
        "-C",
        str(ROOT),
    ]
    if model:
        cmd.extend(["--model", model])
    rc = subprocess.run(cmd, input=prompt, text=True, env=_env_with_pythonpath()).returncode
    if rc != 0:
        raise RuntimeError(f"codex exec failed (rc={rc})")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    return data


def _verify_04a(out: Path) -> None:
    audit_path = out / "04a_layout_audit" / "json_output" / "04a_layout_audit.json"
    data = ralph.check_json_file_valid(audit_path, key_check=["ok", "errors"])
    ok = bool(data.get("ok"))
    errors = int(data.get("errors", 0) or 0)
    ralph.assert_helping(ok and errors == 0, f"04a_layout_audit ok={ok} errors={errors}")


def _verify_07(out: Path) -> None:
    db_path = out / "pipeline.duckdb"
    ralph.assert_helping(db_path.exists(), f"pipeline.duckdb exists at {db_path}")
    for table in ("sections", "blocks", "tables", "figures", "merged_content"):
        min_rows = 1 if table == "merged_content" else 0
        ralph.check_table_has_rows(db_path, table, min_rows=min_rows)


def _verify_08(out: Path, min_requirements: int) -> None:
    db_path = out / "pipeline.duckdb"
    ralph.assert_helping(db_path.exists(), f"pipeline.duckdb exists at {db_path}")
    ralph.check_table_has_rows(db_path, "requirements", min_rows=min_requirements)


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


def _clean_downstream(
    out: Path,
    steps: list["Step"],
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


def _verify_fixture_step(step_name: str, out: Path, fixture: dict) -> None:
    steps = fixture.get("steps", {})
    expected = steps.get(step_name)
    if not expected:
        return

    if step_name == "08_lean4_theorem_prover":
        min_proofs = int(expected.get("min_proofs", 1))
        db_path = out / "pipeline.duckdb"
        ralph.assert_helping(db_path.exists(), f"pipeline.duckdb exists at {db_path}")
        ralph.check_table_has_rows(db_path, "lean4_proofs", min_rows=min_proofs)
        return

    rel_path = expected.get("json")
    if not rel_path:
        return
    json_path = out / rel_path
    keys = expected.get("keys") or []
    data = ralph.check_json_file_valid(json_path, key_check=keys)

    if step_name == "01_annotation_processor":
        annots = data.get("annotations", [])
        min_annots = int(expected.get("min_annotations", 0))
        ralph.assert_helping(len(annots) >= min_annots, f"S01 annotations >= {min_annots}")
        clean_pdf = Path(data.get("clean_pdf_path", ""))
        ralph.assert_helping(clean_pdf.exists(), f"S01 clean PDF exists at {clean_pdf}")
        return

    if step_name == "02_marker_extractor":
        block_count = int(data.get("block_count", 0) or 0)
        min_blocks = int(expected.get("min_blocks", 1))
        ralph.assert_helping(block_count >= min_blocks, f"S02 block_count >= {min_blocks}")
        return

    if step_name == "03_suspicious_headers":
        blocks = data.get("blocks", [])
        min_verified = int(expected.get("min_verified_blocks", 0))
        ralph.assert_helping(len(blocks) >= min_verified, f"S03 verified blocks >= {min_verified}")
        return

    if step_name == "04_section_builder":
        sections = data.get("sections", [])
        min_sections = int(expected.get("min_sections", 1))
        ralph.assert_helping(len(sections) >= min_sections, f"S04 sections >= {min_sections}")
        return


def _select_samples(items: Sequence[str], limit: int, min_chars: int) -> list[str]:
    samples = []
    for item in items:
        s = str(item or "").strip()
        if len(s) < min_chars:
            continue
        samples.append(s)
        if len(samples) >= limit:
            break
    return samples


def _collect_llm_samples(step_name: str, out: Path, fixture: dict) -> list[str]:
    expected = (fixture.get("steps") or {}).get(step_name) or {}
    judge = expected.get("judge") or {}
    min_chars = int(judge.get("min_chars", 40))
    sample_size = int(judge.get("sample_size", 3))

    if step_name == "05b_table_describer":
        json_path = out / expected.get("json", "")
        data = ralph.check_json_file_valid(json_path, key_check=["tables"])
        tables = data.get("tables", [])
        texts = [t.get("llm_description") or t.get("llm_title") for t in tables]
        return _select_samples(texts, sample_size, min_chars)

    if step_name == "06b_figure_describer":
        json_path = out / expected.get("json", "")
        data = ralph.check_json_file_valid(json_path, key_check=["figures"])
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


def _judge_llm_step(step_name: str, out: Path, fixture: dict, model: Optional[str]) -> None:
    expected = (fixture.get("steps") or {}).get(step_name) or {}
    judge = expected.get("judge") or {}
    if not judge.get("enabled", False):
        return

    samples = _collect_llm_samples(step_name, out, fixture)
    min_samples = int(judge.get("min_samples", 1))
    ralph.assert_helping(len(samples) >= min_samples, f"{step_name}: samples >= {min_samples}")

    disallow = judge.get("disallow") or []
    for s in samples:
        low = s.lower()
        for phrase in disallow:
            if phrase.lower() in low:
                raise ralph.RalphError(f"{step_name}: disallowed phrase '{phrase}' found")

    prompt = judge.get("prompt", "").strip()
    if not prompt:
        prompt = (
            "You are evaluating LLM outputs from a PDF extraction pipeline. "
            "Decide if the samples are coherent, relevant, and non-placeholder. "
            "Return JSON only."
        )
    sample_block = "\n\n".join([f"Sample {i+1}:\n{txt}" for i, txt in enumerate(samples)])
    full_prompt = f"{prompt}\n\n{sample_block}\n\nReturn JSON with fields ok, score, issues."
    result = _judge_with_codex(full_prompt, model)
    ok = bool(result.get("ok"))
    if not ok:
        issues = result.get("issues")
        raise ralph.RalphError(f"{step_name}: codex judge failed ({issues})")


@dataclass(frozen=True)
class Step:
    name: str
    module: str
    build_run_args: Callable[[Path, argparse.Namespace], list[str]]
    verify_cli: bool = True
    custom_verify: Optional[Callable[[Path, argparse.Namespace], None]] = None
    enabled: Optional[Callable[[argparse.Namespace], bool]] = None
    execute: bool = True
    output_paths: tuple[str, ...] = ()

    def is_enabled(self, args: argparse.Namespace) -> bool:
        return True if self.enabled is None else bool(self.enabled(args))


def _args_base(out: Path, _args: argparse.Namespace) -> list[str]:
    return ["--pipeline-dir", str(out)]


def _args_s01(out: Path, args: argparse.Namespace) -> list[str]:
    return ["--pipeline-dir", str(out), "--pdf", str(args.pdf)]


def _args_s06(out: Path, _args: argparse.Namespace) -> list[str]:
    return ["--pipeline-dir", str(out), "--pdf-dir", str(out / "01_annotation_processor")]


def _run_step(step: Step, out: Path, args: argparse.Namespace, env: dict, fixture: Optional[dict]) -> bool:
    if args.verify_only:
        return _verify_step(step, out, args, env, fixture)

    if step.execute:
        base_cmd = [sys.executable, "-m", step.module]
        run_args = step.build_run_args(out, args)
        run_rc = _run_cmd(base_cmd + run_args, env)
        if run_rc != 0:
            print(f"!! {step.name} execution failed (rc={run_rc})")
            return False
    else:
        print(f"-- {step.name}: execution skipped (verify-only step)")
    return _verify_step(step, out, args, env, fixture)


def _verify_step(
    step: Step,
    out: Path,
    args: argparse.Namespace,
    env: dict,
    fixture: Optional[dict],
) -> bool:
    if step.verify_cli:
        base_cmd = [sys.executable, "-m", step.module]
        verify_args = step.build_run_args(out, args) + ["--verify-only"]
        verify_rc = _run_cmd(base_cmd + verify_args, env)
        if verify_rc != 0:
            print(f"!! {step.name} verification failed (rc={verify_rc})")
            return False
        if fixture:
            try:
                _verify_fixture_step(step.name, out, fixture)
                if args.llm_judge:
                    _judge_llm_step(step.name, out, fixture, args.llm_judge_model)
            except Exception as exc:
                print(f"!! {step.name} fixture check failed: {exc}")
                return False
        return True

    if step.custom_verify is None:
        print(f"!! {step.name} has no verification hook")
        return False

    try:
        step.custom_verify(out, args)
        if fixture:
            _verify_fixture_step(step.name, out, fixture)
            if args.llm_judge:
                _judge_llm_step(step.name, out, fixture, args.llm_judge_model)
        return True
    except Exception as exc:
        print(f"!! {step.name} verification failed: {exc}")
        return False


def _print_questions_for_step(step_name: str) -> None:
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
            "Are table images present under 05_table_extractor/image_output?",
            "Are LLM credentials set (CHUTES_API_KEY / CHUTES_TEXT_MODEL)?",
            "Do any tables have llm_description fields?",
        ],
        "05c_table_merger": [
            "Does 05b_tables.json or 05_tables.json exist?",
            "Are table headers/columns aligned for merge detection?",
        ],
        "06_figure_extractor": [
            "Are figure images being written to 06_figure_extractor/image_output?",
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
    for q in questions.get(step_name, ["What specific contract check is failing?"]):
        print(f"- {q}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Fail-fast contract verifier for pipeline steps.")
    ap.add_argument("--pdf", type=Path, help="Input PDF path (required unless --verify-only)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Pipeline output directory")
    ap.add_argument("--fixture", type=Path, help="Fixture expectations JSON (optional)")
    ap.add_argument(
        "--mode",
        choices=["deterministic", "full"],
        default="deterministic",
        help="deterministic skips LLM steps; full runs all steps",
    )
    ap.add_argument("--max-tries", type=int, default=3, help="Max attempts per step")
    ap.add_argument(
        "--min-requirements",
        type=int,
        default=1,
        help="Minimum requirements rows when running S08 (full mode)",
    )
    ap.add_argument("--verify-only", action="store_true", help="Verify existing outputs only")
    ap.add_argument("--llm-judge", action="store_true", help="Use codex exec to judge LLM outputs")
    ap.add_argument("--llm-judge-model", type=str, help="Model for codex judge")
    ap.add_argument("--skip-lean4", action="store_true", help="Skip Lean4 verification step")
    ap.add_argument(
        "--no-rerun-upstream",
        action="store_true",
        help="Do not rerun upstream steps on each attempt",
    )
    ap.add_argument(
        "--no-clean-downstream",
        action="store_true",
        help="Do not delete downstream outputs before retries",
    )
    args = ap.parse_args()

    if not args.verify_only and not args.pdf:
        ap.error("--pdf is required unless --verify-only is set")

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    env = _env_with_pythonpath()
    fixture = _load_fixture(args.fixture) if args.fixture else None

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
            output_paths=(),
        ),
        Step(
            "09_section_summarizer",
            "extractor.pipeline.steps.s09_section_summarizer",
            _args_base,
            enabled=lambda a: a.mode == "full",
            output_paths=(),
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
        insert_at = next((i for i, s in enumerate(steps) if s.name == "08_extract_requirements"), None)
        if insert_at is None:
            steps.append(lean4_step)
        else:
            steps.insert(insert_at + 1, lean4_step)

    enabled_steps = [s for s in steps if s.is_enabled(args)]
    index_by_name = {s.name: i for i, s in enumerate(enabled_steps)}

    if args.verify_only:
        for step in enabled_steps:
            print(f"== {step.name} ==")
            if not _run_step(step, out, args, env, fixture):
                print(f"!! {step.name} verification failed")
                return 1
        print("✅ Contract verification complete.")
        return 0

    for target_index, target_step in enumerate(enabled_steps):
        print(f"== {target_step.name} ==")
        success = False
        for attempt in range(1, args.max_tries + 1):
            print(f"-- attempt {attempt}/{args.max_tries}")
            if not args.no_clean_downstream:
                _clean_downstream(out, enabled_steps, target_index, index_by_name)

            ok = True
            start_idx = 0
            end_idx = target_index
            if args.no_rerun_upstream:
                start_idx = target_index

            for idx in range(start_idx, end_idx + 1):
                step = enabled_steps[idx]
                print(f"-- running {step.name}")
                if not _run_step(step, out, args, env, fixture):
                    ok = False
                    break

            if ok:
                success = True
                break
            if attempt < args.max_tries:
                print(f"!! retrying {target_step.name}")

        if not success:
            print(f"!! {target_step.name} failed after {args.max_tries} attempts")
            print("ACTION REQUIRED: provide clarifying answers before proceeding.")
            _print_questions_for_step(target_step.name)
            return 2

    print("✅ Contract verification complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
