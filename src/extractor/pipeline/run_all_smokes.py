#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
SMOKES_DIR = ROOT / "scripts" / "smokes" / "pipeline"
ARTIFACTS_DIR = ROOT / "scripts" / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def discover_smokes():
    # Run all top-level smoke_*.py files in lexicographic order (aligns with stage numbers)
    return sorted(SMOKES_DIR.glob("smoke_*.py"))

def run(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout, proc.stderr

def main():
    py = os.environ.get("PYTHON", sys.executable)
    results = []
    failures = 0

    smokes = discover_smokes()
    if not smokes:
        print("No smoke_*.py files found.", file=sys.stderr)
        return 1

    print(f"Discovered {len(smokes)} smoke tests.\n")

    for smoke in smokes:
        rel = smoke.relative_to(ROOT)
        print(f"==> Running {rel}")
        code, out, err = run([py, str(smoke)], ROOT)
        status = "PASS" if code == 0 else "FAIL"
        print(f"[{status}] {rel}\n")

        if code != 0:
            failures += 1

        results.append({
            "name": str(rel),
            "exit_code": code,
            "status": status,
            "stdout": out[-4000:],  # tail to keep artifact small
            "stderr": err[-4000:],
        })

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = ARTIFACTS_DIR / f"smokes_summary_{ts}.json"
    with summary_path.open("w") as f:
        json.dump({
            "total": len(results),
            "failures": failures,
            "passes": len(results) - failures,
            "results": results,
        }, f, indent=2)

    print(f"\nSummary: {len(results)} total, {len(results)-failures} passed, {failures} failed")
    print(f"Artifact: {summary_path}")

    return 0 if failures == 0 else failures

if __name__ == "__main__":
    sys.exit(main())