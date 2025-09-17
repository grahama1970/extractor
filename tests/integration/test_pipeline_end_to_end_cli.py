import json
import subprocess
from pathlib import Path


def test_pipeline_cli_end_to_end_until_8(tmp_path: Path):
    """Runs the CLI runner through Stage 08 and asserts key artifacts exist.

    Uses the small sample PDF in data/input/pipeline to keep runtime reasonable.
    Heavy stages (05–08) are included; later stages are skipped to avoid external
    service dependencies.
    """
    repo_root = Path.cwd()
    pdf = repo_root / "data/input/pipeline/BHT_CV32A65X_marked.pdf"
    assert pdf.exists(), "Sample PDF not found"

    # Run until stage 8 with heavy stages enabled
    cmd = [
        "python",
        "-m",
        "extractor.pipeline.tools.run_and_validate",
        "--pdf",
        str(pdf),
        "--until",
        "8",
        "--no-skip-heavy",
    ]
    env = {**dict(**subprocess.os.environ), "PYTHONPATH": str(repo_root / "src")}
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"runner failed (code {proc.returncode})\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}"
    )

    results_dir = repo_root / "data/results/pipeline"
    run_report = results_dir / "run_report.md"
    assert run_report.exists(), "run_report.md not found"
    text = run_report.read_text()
    # Check lines for stages 05–08
    for stage in (
        "05_table_extractor",
        "06_figure_extractor",
        "07_reflow_section",
        "08_lean4_theorem_prover",
    ):
        assert stage in text, f"{stage} missing from run_report.md"

    # Verify Stage 07 output schema basics
    s07 = results_dir / "07_reflow_section/json_output/07_reflowed.json"
    assert s07.exists(), "Stage 07 output missing"
    data = json.loads(s07.read_text())
    assert data.get("section_count", 0) >= 1
    assert isinstance(data.get("reflowed_sections", []), list)



def test_pipeline_cli_stage_14_offline(tmp_path: Path):
    """Runs the CLI runner through Stage 14 in offline mode and checks final report artifacts.

    This uses --offline so that Stage 11 is skipped cleanly and Arango/FAISS are not required.
    """
    repo_root = Path.cwd()
    pdf = repo_root / "data/input/pipeline/BHT_CV32A65X_marked.pdf"
    assert pdf.exists(), "Sample PDF not found"

    cmd_pre = [
        "python",
        "-m",
        "extractor.pipeline.tools.run_and_validate",
        "--pdf",
        str(pdf),
        "--until",
        "8",
        "--no-skip-heavy",
    ]
    env = {**dict(**subprocess.os.environ), "PYTHONPATH": str(repo_root / "src")}
    proc_pre = subprocess.run(cmd_pre, env=env, capture_output=True, text=True)
    assert proc_pre.returncode == 0, (
        f"pre-runner failed (code {proc_pre.returncode})\n"
        f"STDOUT:\n{proc_pre.stdout}\n"
        f"STDERR:\n{proc_pre.stderr}"
    )

    cmd14 = [
        "python",
        str(repo_root / "src/extractor/pipeline/steps/14_report_generator.py"),
        "run",
        str(repo_root / "data/results/pipeline"),
    ]
    proc14 = subprocess.run(cmd14, env=env, capture_output=True, text=True)
    assert proc14.returncode == 0, (
        f"stage 14 failed (code {proc14.returncode})\n"
        f"STDOUT:\n{proc14.stdout}\n"
        f"STDERR:\n{proc14.stderr}"
    )

    results_dir = repo_root / "data/results/pipeline"
    # Final report artifacts exist
    final_json = results_dir / "final_report.json"
    final_md = results_dir / "final_report.md"
    assert final_json.exists(), "final_report.json missing"
    assert final_md.exists(), "final_report.md missing"
    data = json.loads(final_json.read_text())
    assert data.get("success") is True
    assert "content_summary" in data
