#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.contract_loop.utils import compose_collaboration_bundle


def _write_fixture(out_dir: Path) -> None:
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({"ok": True}, indent=2), encoding="utf-8")
    attempt_dir = out_dir / "demo_step" / "attempt_1"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "stdout.log").write_text("hello\n", encoding="utf-8")
    (attempt_dir / "stderr.log").write_text("", encoding="utf-8")
    clar_dir = out_dir / "clarifications"
    clar_dir.mkdir(parents=True, exist_ok=True)
    (clar_dir / "demo_step.json").write_text("{}", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        _write_fixture(out_dir)
        info = compose_collaboration_bundle(out_dir, "demo_step", 1)
        if not info.path.exists():
            raise SystemExit("Bundle was not created")
        if info.size_bytes <= 0:
            raise SystemExit("Bundle size is zero")
        print(f"OK: bundle created at {info.path} ({info.size_bytes} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
