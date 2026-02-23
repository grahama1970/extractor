#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Root is 2 levels up from tools/tasks_loop/run_pipeline.py
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
GATES_DIR = SCRIPT_DIR / "gates"

# Import manifest for dependency-aware preflight
sys.path.insert(0, str(SCRIPT_DIR / "utils"))
sys.path.insert(0, str(ROOT / "src"))  # Allow importing extractor modules
from sanity_manifest import run_step_preflight  # noqa: E402

# Step Configuration
# Ordered list of steps.
# NOTE: "data/results/pipeline" is a placeholder that will be replaced at runtime
STEPS: List[Dict[str, Any]] = [
    {
        "id": "s01",
        "description": "Annotation Processor",
        "module": "extractor.pipeline.steps.s01_annotation_processor",
        "args": [
            "--pipeline-dir",
            "data/results/pipeline",
            "--pdf",
            "data/input/pipeline/BHT_CV32A65X_test.pdf",
        ],
        "gate": "gate_s01.py",
        "clean": [
            "data/results/pipeline/01_*"
        ],  # Basic cleanup pattern if needed, though mostly handled by steps
    },
    {
        "id": "s02",
        "description": "Marker Extractor",
        "module": "extractor.pipeline.steps.s02_marker_extractor",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s02.py",
    },
    {
        "id": "s03",
        "description": "Suspicious Headers",
        "module": "extractor.pipeline.steps.s03_suspicious_headers",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s03.py",
    },
    {
        "id": "s04",
        "description": "Section Builder",
        "module": "extractor.pipeline.steps.s04_section_builder",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s04.py",
    },
    {
        "id": "s04a",
        "description": "Layout Audit",
        "module": "extractor.pipeline.steps.s04a_layout_audit",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s04a.py",
    },
    {
        "id": "s05",
        "description": "Table Extractor",
        "module": "extractor.pipeline.steps.s05_table_extractor",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s05.py",
    },
    {
        "id": "s05b",
        "description": "Table Describer",
        "module": "extractor.pipeline.steps.s05b_table_describer",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s05b.py",
    },
    {
        "id": "s05c",
        "description": "Table Merger",
        "module": "extractor.pipeline.steps.s05c_table_merger",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s05c.py",
    },
    {
        "id": "s06",
        "description": "Figure Extractor",
        "module": "extractor.pipeline.steps.s06_figure_extractor",
        "args": [
            "--pipeline-dir",
            "data/results/pipeline",
            "--pdf-dir",
            "data/results/pipeline/01_annotation_processor",
        ],
        "gate": "gate_s06.py",
    },
    {
        "id": "s06b",
        "description": "Figure Describer",
        "module": "extractor.pipeline.steps.s06b_figure_describer",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s06b.py",
    },
    {
        "id": "s07",
        "description": "DuckDB Ingest",
        "module": "extractor.pipeline.steps.s07_duckdb_ingest",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s07.py",
    },
    {
        "id": "s07b",
        "description": "Text Cleaner",
        "module": "extractor.pipeline.steps.s07b_text_cleaner",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s07b.py",
    },
    {
        "id": "s08",
        "description": "Extract Requirements",
        "module": "extractor.pipeline.steps.s08_extract_requirements",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s08.py",
    },
    {
        "id": "s09",
        "description": "Section Summarizer",
        "module": "extractor.pipeline.steps.s09_section_summarizer",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s09.py",
    },
    {
        "id": "s10",
        "description": "Markdown Exporter",
        "module": "extractor.pipeline.steps.s10_markdown_exporter",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s10.py",
    },
    {
        "id": "s14",
        "description": "Report Generator",
        "module": "extractor.pipeline.steps.s14_report_generator",
        "args": ["--pipeline-dir", "data/results/pipeline"],
        "gate": "gate_s14.py",
        "clean": ["data/results/pipeline/14_*"],
    },
]

from retry_utils import retry_subprocess  # noqa: E402


@retry_subprocess(attempts=3, delay=1.0)
def run_command(cmd: List[str], cwd: Path) -> bool:
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd)
    if res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, cmd)
    return True


def run_sanity():
    print("== Running Sanity Checks ==")
    sanity_driver = SCRIPT_DIR / "run_sanity_checks.py"
    if not sanity_driver.exists():
        print(f"❌ Sanity driver not found: {sanity_driver}")
        sys.exit(1)

    cmd = [sys.executable, str(sanity_driver)]
    if not run_command(cmd, ROOT):
        print("❌ Sanity Checks Failed")
        sys.exit(1)
    print("✅ Sanity Checks Passed\n")


def run_step(
    step: Dict[str, Any], dry_run: bool = False, preflight: bool = False, fixture: str = None
) -> bool:
    desc = f"{step['id'].upper()} ({step['description']})"
    print(f"== Running {desc} ==")

    # 1. Run step-specific preflight if requested
    if preflight:
        if not run_step_preflight(step["id"]):
            print(f"❌ FAIL: {desc} preflight failed")
            return False

    # 2. Run Module
    if dry_run:
        print(f"[Dry Run] python -m {step['module']} {' '.join(step['args'])}")
    else:
        cmd = [sys.executable, "-m", step["module"]] + step["args"]
        if not run_command(cmd, ROOT):
            print(f"❌ FAIL: {desc} execution failed")
            return False

    # 3. Run Gate
    gate_script = GATES_DIR / step["gate"]
    if not gate_script.exists():
        print(f"⚠️ WARNING: Gate {step['gate']} not found. Skipping verification.")
        return True

    if dry_run:
        fixture_arg = f" --fixture {fixture}" if fixture else ""
        print(f"[Dry Run] python {gate_script}{fixture_arg}")
    else:
        cmd = [sys.executable, str(gate_script)]
        if fixture:
            cmd.extend(["--fixture", fixture])
        if not run_command(cmd, ROOT):
            print(f"❌ FAIL: {desc} gate failed")
            return False

    print(f"✅ PASS: {desc}\n")
    return True


def update_status(
    run_id: str,
    output_root: Path,
    current_step: str,
    status: str,
    error: str = None,
    fixture: str = None,
):
    """Write machine-readable status file for headless agents."""
    status_file = output_root / "status.json"
    data = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "current_step": current_step,
        "status": status,
        "error": error,
        "fixture": fixture,  # Needed for S08 profile loading
    }
    status_file.write_text(json.dumps(data, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Run Extractor Pipeline Steps")
    parser.add_argument("step", nargs="?", help="Step ID to run (e.g., s01, s14) or 'all'")
    parser.add_argument(
        "--from-start", action="store_true", help="Run all steps from start up to the target step"
    )
    parser.add_argument(
        "--sanity", action="store_true", help="Run ALL sanity checks first (global)"
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run step-specific preflight checks (dependency-aware)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running")
    parser.add_argument(
        "--fixture", default="BHT_CV32A65X_test", help="Fixture name for contract verification"
    )
    parser.add_argument("--run-id", help="Explicit run ID (default: auto-generated timestamp)")
    args = parser.parse_args()

    # Determine execution plan
    if not args.step and not args.sanity:
        parser.print_help()
        sys.exit(1)

    # 0. Setup Run Context
    # --------------------
    if args.run_id:
        run_id = args.run_id
    else:
        # Use diagnostics utility if available or simple fallback
        try:
            import uuid
            from datetime import datetime

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            short_uuid = str(uuid.uuid4())[:8]
            run_id = f"run_{ts}_{short_uuid}"
        except ImportError:
            run_id = "run_fallback"

    # Define Output Root
    # We replace the legacy "data/results/pipeline" with "data/results/{run_id}"
    legacy_root = "data/results/pipeline"
    output_root = ROOT / "data/results" / run_id
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"🚀 Starting Run: {run_id}")
    print(f"📂 Output Dir: {output_root}")

    # Update 'latest' symlink
    latest_link = ROOT / "data/results/latest"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(output_root)
    print(f"🔗 Linked 'latest' -> {run_id}")

    # Shim: Update 'data/results/pipeline' symlink for Legacy Gates
    # Gates hardcode 'data/results/pipeline', so we point it to the current run.
    pipeline_shim = ROOT / "data/results/pipeline"
    if pipeline_shim.exists() and not pipeline_shim.is_symlink():
        # It's a real directory, back it up
        backup = ROOT / "data/results/pipeline_backup"
        if backup.exists():
            import shutil

            shutil.rmtree(backup)
        pipeline_shim.rename(backup)
        print(f"📦 Moved legacy output to {backup}")

    if pipeline_shim.is_symlink():
        pipeline_shim.unlink()

    pipeline_shim.symlink_to(output_root)
    print(f"🔗 Shimmed 'data/results/pipeline' -> {run_id}\n")

    # Inject Run ID into Environment for steps that might need it
    import os

    os.environ["PIPELINE_RUN_ID"] = run_id
    os.environ["EXTRACTOR_OUTPUT_ROOT"] = str(output_root)

    # Ensure subprocesses can find the 'extractor' package
    current_path = os.environ.get("PYTHONPATH", "")
    src_path = str(ROOT / "src")
    if src_path not in current_path:
        os.environ["PYTHONPATH"] = f"{src_path}:{current_path}" if current_path else src_path

    # Dynamically update STEPS args
    for step in STEPS:
        new_args = []
        for arg in step["args"]:
            # naive string replacement for the root path
            new_args.append(arg.replace(legacy_root, str(output_root)))
        step["args"] = new_args

        # Also clean patterns if present
        if "clean" in step:
            step["clean"] = [p.replace(legacy_root, str(output_root)) for p in step["clean"]]

    if args.sanity:
        run_sanity()
        if not args.step:
            sys.exit(0)

    # Auto-compile contracts if needed
    # We check the SPEC.md for the target fixture
    fixture_dir = SCRIPT_DIR / "fixtures" / args.fixture
    spec_file = fixture_dir / "SPEC.md"
    if spec_file.exists():
        contracts_dir = fixture_dir / "contracts"
        need_compile = False
        if not contracts_dir.exists():
            need_compile = True
        else:
            # Check if any contract is older than SPEC.md
            spec_mtime = spec_file.stat().st_mtime
            for c in contracts_dir.glob("*.json"):
                if c.stat().st_mtime < spec_mtime:
                    need_compile = True
                    break

        if need_compile:
            print(f"📦 SPEC.md changed. Recompiling contracts for {args.fixture}...")
            compiler = SCRIPT_DIR / "utils" / "compile_contracts.py"
            if not run_command([sys.executable, str(compiler), "--fixture", args.fixture], ROOT):
                print("❌ Contract compilation failed")
                sys.exit(1)
            print("✅ Contracts updated")

    # Resolve Input PDF from Fixture
    pdf_path = fixture_dir / "source.pdf"
    if not pdf_path.exists():
        # Fallback for legacy BHT location
        if args.fixture == "BHT_CV32A65X_test":
            pdf_path = ROOT / "data/input/pipeline/BHT_CV32A65X_test.pdf"

    if not pdf_path.exists():
        print(f"❌ Input PDF not found for fixture {args.fixture}")
        print(f"   Checked: {pdf_path}")
        sys.exit(1)

    # Update S01 arguments to use the correct PDF
    # Find S01 in STEPS (it's usually index 0, but safety first)
    for s in STEPS:
        if s["id"] == "s01":
            # Preserve pipeline-dir (which is now dynamic), update pdf
            # We look for the --pdf arg and update the next item
            current_args = s["args"]
            if "--pdf" in current_args:
                idx = current_args.index("--pdf")
                if idx + 1 < len(current_args):
                    current_args[idx + 1] = str(pdf_path)
            else:
                # It might have been hardcoded for BHT, so we fallback to append
                s["args"].extend(["--pdf", str(pdf_path)])
            break

    target_id = args.step.lower()

    # Find start/end index
    start_idx = 0
    end_idx = 0

    if target_id == "all":
        end_idx = len(STEPS) - 1
    else:
        found = False
        for i, s in enumerate(STEPS):
            if s["id"] == target_id:
                end_idx = i
                found = True
                break
        if not found:
            print(f"❌ Unknown step: {target_id}")
            print(f"Available steps: {[s['id'] for s in STEPS]}")
            sys.exit(1)

    if not args.from_start and target_id != "all":
        start_idx = end_idx  # Just run the single step

    # Execute
    update_status(run_id, output_root, "START", "RUNNING", fixture=args.fixture)

    for i in range(start_idx, end_idx + 1):
        step = STEPS[i]
        step_id = step["id"]
        update_status(run_id, output_root, step_id, "RUNNING", fixture=args.fixture)

        if not run_step(step, args.dry_run, args.preflight, args.fixture):
            update_status(
                run_id,
                output_root,
                step_id,
                "FAILED",
                error="Step Execution Failed",
                fixture=args.fixture,
            )
            sys.exit(1)

    update_status(run_id, output_root, "COMPLETE", "SUCCESS", fixture=args.fixture)

    print("🎉 Pipeline Run Complete 🎉")


if __name__ == "__main__":
    main()
