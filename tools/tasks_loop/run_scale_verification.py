#!/usr/bin/env python3
"""
run_scale_verification.py

Batch runner for Scale Testing.
1. Generates N unique PDFs using generate_scale_fixture.py (seeded).
2. Runs pipeline on each.
3. Verifies robustness using verify_ground_truth.py.
4. Aggregates stats.

Usage:
  python3 run_scale_verification.py --iterations 10 --pages 20
"""

import argparse
import subprocess
import shutil
import sys
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class RunResult:
    seed: int
    pdf_path: Path
    pipeline_ok: bool
    verify_ok: bool
    verify_score: float
    warnings: int
    error_msg: str = ""


def run_command(cmd: list, cwd: Path = None) -> bool:
    print(f"CMD: {' '.join(str(c) for c in cmd)}")
    res = subprocess.run(cmd, cwd=cwd)
    return res.returncode == 0


def capture_verify_score(json_path: Path) -> tuple[bool, float, int]:
    # Parse verify output JSON or parse stdout?
    # verify_ground_truth.py outputs to stdout, but we can capture output of subprocess if we want score.
    # Currently verify_ground_truth prints textual report.
    # It exits 0 on Pass/Conditional, 1 on Fail.
    # To get score, we might need to parse logs or update verify to dump a json report.
    # For now, we trust exit code.
    # But wait, verify_ground_truth DOES exit 0 for Conditional.
    # We want to know if it was CLEAN pass or Conditional.
    # Maybe we can grep stdout.
    return True, 100.0, 0  # Placeholder if we don't parse


def run_scale_test(iterations: int, pages: int, profile: Path):
    # __file__ = tools/tasks_loop/run_scale_verification.py
    # P1=tasks_loop, P2=tools, P3=extractor (ROOT)
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    TOOLS_ROOT = PROJECT_ROOT / "tools/tasks_loop"
    SCALE_OUT = PROJECT_ROOT / "data/results/scale_run"
    SCALE_OUT.mkdir(parents=True, exist_ok=True)

    # Scripts
    GEN_SCRIPT = TOOLS_ROOT / "utils/generate_scale_fixture.py"
    PIPE_SCRIPT = PROJECT_ROOT / "src/extractor/pipeline/run_pipeline.py"
    VERIFY_SCRIPT = TOOLS_ROOT / "utils/verify_ground_truth.py"

    results: List[RunResult] = []

    # Ensure profile
    if not profile:
        profile = TOOLS_ROOT / "fixtures/twin_profile.yml"

    print(f"--- Starting Scale Verification (N={iterations}, Pages={pages}) ---")
    print(f"Profile: {profile}")

    for i in range(iterations):
        seed = i
        run_id = f"run_{i:03d}"
        print(f"\n[{i+1}/{iterations}] Running Seed {seed}...")

        pdf_path = SCALE_OUT / f"{run_id}.pdf"
        exp_path = SCALE_OUT / f"{run_id}_expected.json"

        # 1. Cleanup Pipeline Output Directory (Ensure Hygiene)
        pipeline_out = PROJECT_ROOT / "data/results/pipeline"
        if pipeline_out.exists():
            if pipeline_out.is_symlink():
                pipeline_out.unlink()
            else:
                shutil.rmtree(pipeline_out)

        # 2. Generate
        cmd_gen = [
            "python3",
            str(GEN_SCRIPT),
            str(pdf_path),
            "--pages",
            str(pages),
            "--config",
            str(profile),
            "--seed",
            str(seed),
        ]
        if not run_command(cmd_gen, cwd=PROJECT_ROOT):
            results.append(RunResult(seed, pdf_path, False, False, 0.0, 0, "Gen Failed"))
            continue

        # 3. Pipeline
        # Note: uv run usage
        cmd_pipe = ["uv", "run", str(PIPE_SCRIPT), str(pdf_path)]
        # We assume pipeline overwrites/appends to data/results/pipeline
        if not run_command(cmd_pipe, cwd=PROJECT_ROOT):
            results.append(RunResult(seed, pdf_path, False, False, 0.0, 0, "Pipeline Failed"))
            continue

        # 4. Verify
        # Capture stdout to parse decision
        db_path = PROJECT_ROOT / "data/results/pipeline/pipeline.duckdb"
        cmd_verify = [
            "uv",
            "run",
            str(VERIFY_SCRIPT),
            "--actual",
            str(db_path),
            "--expected",
            str(exp_path),
            "--json",
        ]

        proc = subprocess.run(cmd_verify, cwd=PROJECT_ROOT, capture_output=True, text=True)

        # Default Fail
        verify_ok = False
        score = 0.0
        warnings = 0

        try:
            v_data = json.loads(proc.stdout)
            decision = v_data.get("decision", "REJECTED")
            verify_ok = decision in ["ACCEPTED", "CONDITIONALLY ACCEPTED"]

            # Extract Metrics
            metrics = v_data.get("metrics", {})
            warnings = metrics.get("warnings", 0)

            # Score (We need to synthesize a score or extract from JSON if we added it?)
            # verify_ground_truth passes back a list of details["passed"] with scores.
            # We can calculate average or just use a proxy.
            if decision == "ACCEPTED":
                score = 100.0
            elif decision == "CONDITIONALLY ACCEPTED":
                score = 90.0
            else:
                score = 0.0

        except json.JSONDecodeError:
            print(f"Verify Failed to produce JSON: {proc.stdout}")
            print(f"Stderr: {proc.stderr}")

        results.append(
            RunResult(
                seed,
                pdf_path,
                True,
                verify_ok,
                score,
                warnings,
                "" if verify_ok else "Verify Rejected",
            )
        )

    # Report
    print("\n--- Scale Verification Report ---")
    print(f"{'Seed':<5} | {'Pipe':<6} | {'Verify':<8} | {'Score':<6} | {'Warnings':<9} | {'Notes'}")
    print("-" * 60)
    for r in results:
        pipe_str = "OK" if r.pipeline_ok else "FAIL"
        ver_str = "PASS" if r.verify_ok else "FAIL"
        print(
            f"{r.seed:<5} | {pipe_str:<6} | {ver_str:<8} | {r.verify_score:<6} | {r.warnings:<9} | {r.error_msg}"
        )

    pass_count = len([r for r in results if r.verify_ok])
    print(f"\nPass Rate: {pass_count}/{iterations} ({pass_count/iterations*100:.1f}%)")

    # Save Report to JSON
    report_path = SCALE_OUT / "scale_report.json"
    report_data = [{"seed": r.seed, "ok": r.verify_ok, "score": r.verify_score} for r in results]
    report_path.write_text(json.dumps(report_data, indent=2))

    if pass_count == iterations:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--pages", type=int, default=20)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()

    run_scale_test(args.iterations, args.pages, args.profile)
