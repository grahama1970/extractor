import json
import os
import sys
from pathlib import Path


def _runs_set():
    return set(p.parent.name for p in Path("workspace/runs").glob("*/instances"))


def test_three_codex_instances_end_to_end(tmp_path: Path):
    # Craft a minimal 3-variant prompt for deterministic names
    prompt = tmp_path / "prompt_3x.md"
    prompt.write_text(
        "\n".join(
            [
                "## Gamified Run Spec — 3x",
                "## Codebase",
                "repo_root: .",
                "## Approaches",
                "- name: mul_shift_add",
                "- name: mul_karatsuba",
                "- name: mul_chunked",
                "## Runner",
                "type: python_benchmark",
                "entry: prototypes/gamified/bench/multiply_benchmark.py",
                "create_if_missing: true",
                "## Scoring",
                "plateau: { epsilon: 0.15, window: 3 }",
                "## Execution",
                "max_iters: 1",
                "api_base: http://localhost:8000",
            ]
        )
    )

    before = _runs_set()
    env = os.environ.copy()
    env["GAMIFIED_FAST_BENCH"] = "1"
    # Use Codex default path; instances=3
    cmd = [
        sys.executable,
        "-m",
        "prototypes.gamified.cli",
        "run",
        "--codebase",
        ".",
        "--prompt-file",
        str(prompt),
        "--instances",
        "3",
        "--instance-timeout-s",
        "60",
        "--idle-timeout-s",
        "60",
        "--no-autostart-backend",
        "--no-start-dashboard",
    ]
    rc = os.system(" ".join(cmd))
    assert rc == 0

    after = _runs_set()
    added = list(after - before)
    assert added, "no new run created"
    rid = added[-1]
    root = Path("workspace/runs") / rid
    # Instance dirs should exist for all three variants
    inst = root / "instances"
    assert (inst / "codex_01_mul_shift_add").exists()
    assert (inst / "codex_02_mul_karatsuba").exists()
    assert (inst / "codex_03_mul_chunked").exists()
    # Scorecard must exist with a winner
    sc = root / "scorecard.json"
    assert sc.exists(), "missing scorecard.json"
    js = json.loads(sc.read_text())
    assert js.get("winner"), "winner not set"
    # Approaches should include the three variants
    appr = js.get("approaches") or {}
    for k in ("mul_shift_add", "mul_karatsuba", "mul_chunked"):
        assert k in appr
