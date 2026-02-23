#!/usr/bin/env python3
import argparse
import json
import subprocess
import os
import sys
import yaml
from pathlib import Path

# P1=tasks_loop, P2=tools, P3=extractor (ROOT)
FILE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = FILE_ROOT.parent.parent.parent
TOOLS_ROOT = FILE_ROOT

# Scripts
ANALYZE_SCRIPT = TOOLS_ROOT / "utils/analyze_pdf_style.py"
PREVIEW_SCRIPT = TOOLS_ROOT / "utils/preview_mimic.py"


def run_analysis(pdf_path: Path) -> dict:
    """Run analysis script and capture JSON output."""
    print(f"Analysing {pdf_path.name}...")
    cmd = ["python3", str(ANALYZE_SCRIPT), str(pdf_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Analysis Failed!")
        print(result.stderr)
        sys.exit(1)

    try:
        data = json.loads(result.stdout)
        return data
    except json.JSONDecodeError as e:
        print(f"Failed to parse analysis JSON: {e}")
        print(f"Stdout was: {result.stdout}")
        return {}


def main():
    parser = argparse.ArgumentParser(description="Mimic Wizard: Clone a PDF's style")
    parser.add_argument("target_pdf", type=Path, help="Real PDF to mimic")
    args = parser.parse_args()

    target_path = args.target_pdf.resolve()
    if not target_path.exists():
        print(f"Not found: {target_path}")
        sys.exit(1)

    project_name = target_path.stem.lower().replace(" ", "_")
    config_path = TOOLS_ROOT / f"fixtures/{project_name}_mimic.yml"

    print(f"--- Mimic Wizard: {project_name} ---")

    # 1. Analyze
    style_data = run_analysis(target_path)
    print("Analysis Complete.")

    # 2. Create/Update Config
    if not config_path.exists():
        print(f"Creating new config: {config_path}")
        # Base Template
        new_config = {
            "style": style_data.get("style", {}),
            "chaos": {
                "hyphenation_probability": 0.15,
                "ligature_map": {"fi": "ﬁ", "fl": "ﬂ"},
                "mojibake_probability": 0.01,
            },
            "critical_content": [
                {
                    "id": "REQ-001",
                    "text": "The system must behave exactly like the target document.",
                    "type": "Requirement",
                    "strict_verification": True,
                }
            ],
        }
        config_path.write_text(yaml.dump(new_config, sort_keys=False))
    else:
        print(f"Using existing config: {config_path}")

    # 3. Interactive Loop
    while True:
        print("\n--- Actions ---")
        print("[p]review  : Generate Mimic PDF & Report")
        print("[e]dit     : Edit Config (Chaos/Style)")
        print("[a]nalyze  : Re-run analysis on Target")
        print("[q]uit     : Done")

        choice = input("Select [p/e/a/q]: ").lower().strip()

        if choice == "q":
            break

        elif choice == "e":
            editor = os.environ.get("EDITOR", "nano")
            subprocess.call([editor, str(config_path)])

        elif choice == "a":
            style_data = run_analysis(target_path)
            # Update config? Merging is tricky. Just show user.
            print("Analysis re-run. Update config manually if needed.")

        elif choice == "p":
            print("Generating Preview...")
            cmd = [
                "python3",
                str(PREVIEW_SCRIPT),
                "--config",
                str(config_path),
                "--name",
                f"{project_name}_v1",
            ]
            subprocess.run(cmd)

            # Show report path
            # PREVIEW_SCRIPT prints it.
            print("\nCheck artifacts for MIMIC_PREVIEW_REPORT.md")


if __name__ == "__main__":
    main()
