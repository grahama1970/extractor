#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Smoke: Stage 14 RTM v0 emission

Creates a minimal results tree with a Stage 10 flattened JSON, runs Stage 14 CLI,
and verifies that rtm_v0.json is written and non-empty.

Artifacts:
- scripts/artifacts/rtm_v0_smoke.json
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys
import typer

app = typer.Typer(add_completion=False)


def _make_results_tree(root: Path) -> Path:
    flat_dir = root / "10_arangodb_exporter" / "json_output"
    flat_dir.mkdir(parents=True, exist_ok=True)
    data = [
        {"_key": "obj-0001", "doc_id": "doc-synth", "section_id": "sec-1", "text_content": "Requirement A"},
        {"_key": "obj-0002", "doc_id": "doc-synth", "section_id": "sec-2", "text_content": "Requirement B"},
    ]
    flat_path = flat_dir / "10_flattened_data.json"
    flat_path.write_text(json.dumps(data, indent=2))
    return flat_path


@app.command()
def main(out_dir: Path = Path("scripts/artifacts/rtm_smoke")):
    out_dir.mkdir(parents=True, exist_ok=True)
    _make_results_tree(out_dir)
    # Invoke Stage 14 CLI to generate final report artifacts
    cmd = [
        sys.executable,
        "src/extractor/pipeline/steps/14_report_generator.py",
        "run",
        str(out_dir),
    ]
    proc = subprocess.run(cmd)
    rtm_path = out_dir / "rtm_v0.json"
    ok = (proc.returncode == 0) and rtm_path.exists() and rtm_path.stat().st_size > 10
    summary = {"ok": ok, "rtm": str(rtm_path), "size": rtm_path.stat().st_size if rtm_path.exists() else 0}
    Path("scripts/artifacts/rtm_v0_smoke.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    app()

