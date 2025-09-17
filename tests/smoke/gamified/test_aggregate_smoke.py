import json
import os
import time
from pathlib import Path

from extractor.pipeline.utils.gamified_contracts import Scorecard


def test_aggregate_only_with_synthetic_iter(tmp_path: Path, monkeypatch):
    # Create synthetic run_id and instance structure
    run_id = time.strftime("%Y%m%d-%H%M%S")
    inst_root = Path("workspace/runs") / run_id / "instances"
    (inst_root).mkdir(parents=True, exist_ok=True)
    alpha = inst_root / "codex_01_alpha"
    beta = inst_root / "codex_02_beta"
    alpha.mkdir(parents=True, exist_ok=True)
    beta.mkdir(parents=True, exist_ok=True)

    # Write minimal iter_01.json into each
    alpha_iter = {
        "approach": "alpha",
        "correctness": {"S": True, "M": False, "L": False},
        "timings_ms": {"S": 0.05, "M": float("inf"), "L": float("inf")},
        "robust": True,
        "loc": 10,
    }
    beta_iter = {
        "approach": "beta",
        "correctness": {"S": False, "M": False, "L": False},
        "timings_ms": {"S": float("inf"), "M": float("inf"), "L": float("inf")},
        "robust": False,
        "loc": 30,
    }
    (alpha / "iter_01.json").write_text(json.dumps(alpha_iter))
    (beta / "iter_01.json").write_text(json.dumps(beta_iter))

    # Aggregate via CLI
    cmd = (
        f"PYTHONPATH=./src python scripts/gamified.py run --codebase . --run-id {run_id} --aggregate-only --no-autostart-backend --no-start-dashboard"
    )
    rc = os.system(cmd)
    assert rc == 0

    # Validate scorecard
    sc_path = Path(f"workspace/runs/{run_id}/scorecard.json")
    assert sc_path.exists()
    sc = Scorecard.model_validate_json(sc_path.read_text())
    sc.validate_winner()
    assert sc.winner in sc.approaches
