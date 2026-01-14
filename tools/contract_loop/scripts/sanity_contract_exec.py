#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import subprocess

from tools.contract_loop.env_utils import ROOT, env_with_pythonpath


SCHEMA = ROOT / "tools" / "contract_loop" / "judges" / "contract_sanity.schema.json"


def main() -> int:
    if not SCHEMA.exists():
        raise SystemExit(f"Missing schema: {SCHEMA}")

    prompt = 'Return {"ok": true, "notes": "contract sanity"} as JSON.'

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)

    cmd = [
        "codex",
        "exec",
        "--json",
        "--color",
        "never",
        "--output-schema",
        str(SCHEMA),
        "--output-last-message",
        str(out_path),
        "-C",
        str(ROOT),
    ]

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            env=env_with_pythonpath(),
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit("codex exec sanity timed out")

    if result.returncode != 0:
        raise SystemExit(f"codex exec sanity failed (rc={result.returncode})")

    try:
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse codex exec output: {exc}")

    if payload.get("ok") is not True:
        raise SystemExit(f"codex exec sanity did not return ok=true: {payload}")

    print("OK: codex exec JSON harness produced valid schema output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
