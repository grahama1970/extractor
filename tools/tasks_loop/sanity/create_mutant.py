#!/usr/bin/env python3
"""
create_mutant.py - Generate a Mutant Twin by scanning BHT and injecting an equation.

Workflow:
1. Scan BHT_CV32A65X_test.pdf -> spec.json
2. Inject EQUATION on Page 5.
3. Generate BHT_Mutant_Eq fixture.
"""

import sys
import json
import shutil
from pathlib import Path
import subprocess

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
TASKS_LOOP = SCRIPT_DIR.parent
UTILS = TASKS_LOOP / "utils"

def run_command(cmd, cwd=ROOT):
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd, text=True)
    if res.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        sys.exit(1)

def main():
    # 1. Setup Paths
    bht_pdf = ROOT / "data/input/pipeline/BHT_CV32A65X_test.pdf"
    output_spec = TASKS_LOOP / "fixtures" / "temp_bht_spec.json"
    mutant_name = "BHT_Mutant_Eq"
    
    # 2. Scan Real PDF
    print(f"== Scanning {bht_pdf.name} ==")
    run_command([
        sys.executable, str(UTILS / "fixture_scanner.py"),
        "--pdf", str(bht_pdf),
        "--output", str(output_spec)
    ])
    
    # 3. Inject Equation
    print(f"== Injecting Mutation (Equation on Page 5) ==")
    spec = json.loads(output_spec.read_text())
    
    # Find a section on Page 5 (index 4)
    target_section = None
    for sec in spec["sections"]:
        # Naive check: if section starts on page 4 or has content on page 4
        # Just append to the last section that exists to be safe, 
        # or specifically look for one.
        # Let's just add it to the LAST section found.
        target_section = sec
    
    if not target_section:
        print("❌ No sections found to inject into!")
        sys.exit(1)
        
    print(f"   Injecting into section: {target_section['title']}")
    
    # Inject Equation
    equation_obj = {
        "type": "equation",
        "latex": "E = mc^2 + P_v",
        "label": "5.1",
        "page": 4, # Page 5 is index 4
        "bbox": [100.0, 500.0, 300.0, 550.0] # Dummy bbox
    }
    
    # Also add text context
    text_obj = {
        "type": "text",
        "text": "The following equation describes the velocity pressure:",
        "page": 4,
        "bbox": [100.0, 480.0, 500.0, 495.0]
    }
    
    target_section["content"].append(text_obj)
    target_section["content"].append(equation_obj)
    
    # Save Mutated Spec
    mutant_spec_path = TASKS_LOOP / "fixtures" / "items_mutant.json"
    mutant_spec_path.write_text(json.dumps(spec, indent=2))
    
    # 4. Generate Mutant PDF
    print(f"== Generating {mutant_name} ==")
    run_command([
        sys.executable, str(UTILS / "create_fixture_pdf.py"),
        "--spec", str(mutant_spec_path),
        "--name", mutant_name
    ])
    
    # 5. Verify Existence
    mutant_pdf = TASKS_LOOP / "fixtures" / mutant_name / "source.pdf"
    if mutant_pdf.exists():
        print(f"✅ Success! Created {mutant_pdf}")
        print("   Ready for pipeline processing.")
    else:
        print("❌ Failed to create mutant PDF")
        sys.exit(1)

if __name__ == "__main__":
    main()
