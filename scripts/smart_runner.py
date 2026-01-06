#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "duckdb>=0.9.0",
#   "rich",
# ]
# ///
"""
The Smart Runner: Atomic Step Execution with Downstream Invalidation.

Usage:
  python scripts/smart_runner.py --pdf <PDF> --step <STEP_NAME>
  python scripts/smart_runner.py --pdf <PDF> --step 05c_table_merger

Behavior:
  1. Checks if upstream steps exist (Pre-flight).
  2. Invalidates (deletes) the target step's output.
  3. Invalidates (deletes) ALL downstream steps' output (preventing stale data).
  4. Runs the target step.
  5. Verifies the target step against CONTRACT.md.
"""
from __future__ import annotations

import argparse
import sys
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional, List

# Re-use contract helper
from extractor.pipeline.utils import ralph

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "results" / "pipeline_contract"

@dataclass
class StepDef:
    name: str
    module: str
    out_dir_name: str  # e.g. "05_table_extractor"
    depends_on: List[str]  # e.g. ["04_section_builder"]

# === PIPELINE DAG DEFINITION ===
# Order matters! This list defines the execution sequence.
PIPELINE_DAG: List[StepDef] = [
    StepDef("01_annotation_processor", "extractor.pipeline.steps.s01_annotation_processor", "01_annotation_processor", []),
    StepDef("02_marker_extractor", "extractor.pipeline.steps.s02_marker_extractor", "02_marker_extractor", ["01_annotation_processor"]),
    StepDef("03_suspicious_headers", "extractor.pipeline.steps.s03_suspicious_headers", "03_suspicious_headers", ["02_marker_extractor"]),
    StepDef("04_section_builder", "extractor.pipeline.steps.s04_section_builder", "04_section_builder", ["03_suspicious_headers"]),
    StepDef("04a_layout_audit", "extractor.pipeline.steps.s04a_layout_audit", "04a_layout_audit", ["04_section_builder"]),
    StepDef("05_table_extractor", "extractor.pipeline.steps.s05_table_extractor", "05_table_extractor", ["04_section_builder"]),
    # 05b (LLM) skipped in deterministic/smart runner for now or added if needed
    StepDef("05c_table_merger", "extractor.pipeline.steps.s05c_table_merger", "05c_table_merger", ["05_table_extractor"]), 
    StepDef("06_figure_extractor", "extractor.pipeline.steps.s06_figure_extractor", "06_figure_extractor", ["01_annotation_processor"]),
    # 06b skipped...
    StepDef("07_assemble_corpus", "extractor.pipeline.steps.s07_duckdb_ingest", "pipeline.duckdb", ["04_section_builder", "05c_table_merger", "06_figure_extractor"]),
    # 08, 09 skipped...
    StepDef("10_markdown_exporter", "extractor.pipeline.steps.s10_markdown_exporter", "10_markdown_exporter", ["07_assemble_corpus"]),
    StepDef("14_report_generator", "extractor.pipeline.steps.s14_report_generator", "14_report_generator", ["10_markdown_exporter"]),
]

def _get_step_index(name: str) -> int:
    for i, s in enumerate(PIPELINE_DAG):
        if name in s.name:
            return i
    return -1

def _check_upstream(step: StepDef, out_root: Path) -> bool:
    """Verify strictly required upstream artifacts exist."""
    print(f">> 🔍 Checking upstream dependencies for {step.name}...")
    for dep_name in step.depends_on:
        dep_idx = _get_step_index(dep_name)
        if dep_idx == -1:
            print(f"!! Warning: Dependency {dep_name} not found in DAG.")
            continue
        
        dep_def = PIPELINE_DAG[dep_idx]
        dep_path = out_root / dep_def.out_dir_name
        
        # DuckDB Exception
        if dep_def.name == "07_assemble_corpus":
             dep_path = out_root / "pipeline.duckdb"
             
        if not dep_path.exists():
            print(f"!! ❌ Missing dependency: {dep_def.name} (expected at {dep_path})")
            return False
            
    print(">> ✅ Upstream dependencies satisfied.")
    return True

def _invalidate_downstream(target_idx: int, out_root: Path):
    """Nuke the target step output AND all subsequent steps."""
    print(f">> 🧹 Invalidating downstream starting from index {target_idx}...")
    
    # We invalidate everything from target_idx onwards
    for i in range(target_idx, len(PIPELINE_DAG)):
        step = PIPELINE_DAG[i]
        path = out_root / step.out_dir_name
        
        # Special case for DuckDB which is a file, not a dir
        if step.name == "07_assemble_corpus":
             path = out_root / "pipeline.duckdb"
             
        if path.exists():
            print(f"   - Deleting {step.name} output: {path.name}")
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        else:
             print(f"   - (Already clean) {step.name}")

def _run_step_cmd(step: StepDef, out_root: Path, pdf: Path) -> int:
    """Construct and run the CLI command for the step."""
    base = [sys.executable, "-m", step.module, "--pipeline-dir", str(out_root)]
    
    # Special args
    if step.name == "01_annotation_processor":
        base += ["--pdf", str(pdf)]
    elif step.name == "06_figure_extractor":
        base += ["--pdf-dir", str(out_root / "01_annotation_processor")]

    print(f">> 🚀 Running {step.name}...")
    return subprocess.run(base).returncode

def _verify_step(step: StepDef, out_root: Path, pdf: Path) -> bool:
    """Run the verify_pipeline_contract logic (via CLI --verify-only or custom check)."""
    # For simplicity, we re-use the --verify-only flag if the step supports it.
    # Most steps (S01, S05c, S06, S07, etc) support it.
    
    # S04a, S07, S14 might need custom args or wrappers, but let's try standard Ralph CLI first.
    base = [sys.executable, "-m", step.module, "--pipeline-dir", str(out_root), "--verify-only"]
    
    if step.name == "01_annotation_processor":
         base += ["--pdf", str(pdf)]
    elif step.name == "06_figure_extractor":
         base += ["--pdf-dir", str(out_root / "01_annotation_processor")]

    print(f">> 🧪 Verifying {step.name} contract...")
    res = subprocess.run(base)
    return res.returncode == 0


def main():
    ap = argparse.ArgumentParser(description="Smart Runner: Atomic Pipeline Execution")
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--step", type=str, required=True, help="Partial or full name of step to run (e.g. '05c')")
    args = ap.parse_args()
    
    out_root = args.out
    
    # 1. Identify Step
    target_idx = -1
    for i, s in enumerate(PIPELINE_DAG):
        if args.step in s.name:
            target_idx = i
            break
            
    if target_idx == -1:
        print(f"❌ Unknown step: {args.step}")
        print("Available steps:")
        for s in PIPELINE_DAG:
            print(f"  - {s.name}")
        sys.exit(1)
        
    target_step = PIPELINE_DAG[target_idx]
    print(f"== Smart Runner: {target_step.name} ==")
    
    # 2. Check Upstream
    if not _check_upstream(target_step, out_root):
        print("!! Upstream dependencies missing. Please run upstream steps first.")
        sys.exit(1)
        
    # 3. Invalidate Downstream
    _invalidate_downstream(target_idx, out_root)
    
    # 4. Run
    # Ensure dir exists (in case we nuked parent?)
    out_root.mkdir(parents=True, exist_ok=True)
    
    rc = _run_step_cmd(target_step, out_root, args.pdf)
    if rc != 0:
        print(f"!! {target_step.name} execution failed (rc={rc})")
        sys.exit(1)
        
    # 5. Verify
    if not _verify_step(target_step, out_root, args.pdf):
        print(f"!! {target_step.name} verification failed.")
        sys.exit(1)
        
    print(f"✅ Smart Run Complete for {target_step.name}")
    print("   Output and downstream caches validated/cleared.")

if __name__ == "__main__":
    main()
