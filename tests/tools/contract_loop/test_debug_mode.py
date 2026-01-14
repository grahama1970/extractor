import json
import zipfile
from types import SimpleNamespace
from pathlib import Path

import pytest

from tools.contract_loop.adapters.base import BaseAdapter
from tools.contract_loop.core import Step, run_contract_loop
from tools.contract_loop.utils import ContractLoopError, compose_collaboration_bundle
from tools.contract_loop.verify_pipeline_contract import validate_debug_args


class DummyAdapter(BaseAdapter):
    def build_steps(self, args, fixture):
        return [
            Step(
                "sample_step",
                "tests.tools.contract_loop.sample_step",
                lambda out, _args: ["--pipeline-dir", str(out)],
                output_paths=("sample_step",),
            )
        ]


def _base_args(out_dir: Path, pdf_path: Path, debug: bool) -> SimpleNamespace:
    return SimpleNamespace(
        pdf=pdf_path,
        out=out_dir,
        fixture=None,
        mode="deterministic",
        verify_only=False,
        max_tries=1,
        llm_judge=False,
        llm_judge_model=None,
        min_requirements=1,
        skip_lean4=True,
        no_clean_downstream=False,
        no_rerun_upstream=False,
        start_step=None,
        debug=debug,
        bundle_warn_mb=50,
        bundle_max_mb=100,
        clarify_timeout=900,
    )


def test_validate_debug_args_enforces_flags():
    args = SimpleNamespace(debug=True, no_clean_downstream=True, no_rerun_upstream=False)
    with pytest.raises(ValueError):
        validate_debug_args(args)

    args = SimpleNamespace(debug=True, no_clean_downstream=False, no_rerun_upstream=True)
    with pytest.raises(ValueError):
        validate_debug_args(args)

    args = SimpleNamespace(debug=True, no_clean_downstream=False, no_rerun_upstream=False)
    validate_debug_args(args)


def test_debug_mode_writes_logs_and_manifest(tmp_path):
    pdf = tmp_path / "dummy.pdf"
    pdf.write_text("pdf", encoding="utf-8")
    out_dir = tmp_path / "run"
    args = _base_args(out_dir, pdf, debug=True)
    adapter = DummyAdapter()

    rc = run_contract_loop(args, adapter)
    assert rc == 0

    attempt_dir = out_dir / "sample_step" / "attempt_1"
    stdout_log = attempt_dir / "stdout.log"
    stderr_log = attempt_dir / "stderr.log"
    assert stdout_log.exists()
    assert stderr_log.exists()
    assert "sample step running" in stdout_log.read_text()
    assert "sample stderr line" in stderr_log.read_text()

    debug_md = out_dir / "debug.md"
    assert debug_md.exists()
    assert "sample_step" in debug_md.read_text()

    manifest_data = json.loads((out_dir / "manifest.json").read_text())
    assert manifest_data["debug"]["enabled"] is True
    step_entry = manifest_data["steps"][0]
    assert any("attempt_1" in art for art in step_entry["artifacts"])


class FailingAdapter(BaseAdapter):
    def build_steps(self, args, fixture):
        return [
            Step(
                "failing_step",
                "tests.tools.contract_loop.failing_step",
                lambda out, _args: ["--pipeline-dir", str(out)],
                output_paths=("failing_step",),
            )
        ]

    def questions_for_step(self, step_name: str):
        return []


def test_bundle_created_on_failure(tmp_path):
    pdf = tmp_path / "dummy.pdf"
    pdf.write_text("pdf", encoding="utf-8")
    out_dir = tmp_path / "run"
    args = _base_args(out_dir, pdf, debug=True)
    args.max_tries = 1
    adapter = FailingAdapter()

    rc = run_contract_loop(args, adapter)
    assert rc == 2

    bundle = out_dir / "bundles" / "failing_step_attempt_1.zip"
    assert bundle.exists()

    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert any(name.startswith("failing_step/attempt_1/") for name in names)

    manifest_data = json.loads((out_dir / "manifest.json").read_text())
    step_entry = manifest_data["steps"][0]
    assert step_entry["status"] == "failed"
    assert any("bundles/failing_step_attempt_1.zip" in art for art in step_entry["artifacts"])


def test_compose_bundle_warns_and_fails(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "manifest.json").write_text("{}", encoding="utf-8")
    attempt_dir = out_dir / "step" / "attempt_1"
    attempt_dir.mkdir(parents=True)
    log_path = attempt_dir / "stdout.log"
    log_path.write_text("hello", encoding="utf-8")
    judge = out_dir / "step" / "judge_output.json"
    judge.write_text("{}", encoding="utf-8")

    info = compose_collaboration_bundle(
        out_dir,
        "step",
        1,
        warn_bytes=1,
        fail_bytes=10 * 1024 * 1024,
    )
    assert info.warned is True
    assert info.path.exists()

    with pytest.raises(ContractLoopError):
        compose_collaboration_bundle(
            out_dir,
            "step",
            1,
            warn_bytes=1,
            fail_bytes=1,
        )
