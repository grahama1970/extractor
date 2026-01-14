from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cli = root / "tools" / "contacts_cli.py"
    inp = root / "tools" / "sample_contacts.jsonl"
    exp_path = root / "tools" / "expected_contacts.json"
    out_path = root / "out_cli.json"

    # Check help
    rc, out = _run([sys.executable, str(cli), "--help"])
    if rc != 0:
        print("FAIL: --help non-zero")
        print(out)
        return 1
    if "usage:" not in out.lower():
        print("FAIL: help missing 'usage:'")
        print(out)
        return 1

    # Check missing input file error
    rc, out = _run([sys.executable, str(cli), "nope.jsonl", str(out_path)])
    if rc == 0:
        print("FAIL: expected non-zero for missing input file")
        return 1

    # Run happy path
    rc, out = _run([sys.executable, str(cli), str(inp), str(out_path)])
    if rc != 0:
        print("FAIL: CLI run non-zero")
        print(out)
        return 1

    got = json.loads(out_path.read_text(encoding="utf-8"))
    exp = json.loads(exp_path.read_text(encoding="utf-8"))
    if got != exp:
        print("FAIL: output mismatch")
        print("GOT:", got)
        print("EXPECTED:", exp)
        return 1

    print("OK: gate_contacts_cli")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
