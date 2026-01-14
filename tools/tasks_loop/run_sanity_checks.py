#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
SANITY_DIR = SCRIPT_DIR / "sanity"

def run_script(path: Path) -> bool:
    print(f"Running {path.name}...")
    try:
        if path.suffix == ".py":
            cmd = [sys.executable, str(path)]
        elif path.suffix == ".sh":
            cmd = ["bash", str(path)] # Explicit bash execution
        else:
            print(f"Skipping unknown file type: {path.name}")
            return True
            
        # Run from ROOT
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"✅ PASS: {path.name}")
            out_summary = res.stdout.strip().split('\n')[-1] if res.stdout else "(no output)"
            print(f"   Output: {out_summary}")
            return True
        else:
            print(f"❌ FAIL: {path.name}")
            print(f"   Stderr: {res.stderr.strip()}")
            print(f"   Stdout: {res.stdout.strip()}")
            return False
            
    except Exception as e:
        print(f"❌ CRASH: {e}")
        return False

def main():
    print(f"== Sanity Checks Driver ==")
    print(f"Root: {ROOT}")
    
    if not SANITY_DIR.exists():
        print(f"Error: Sanity dir not found at {SANITY_DIR}")
        sys.exit(1)
        
    scripts = sorted([p for p in SANITY_DIR.iterdir() if p.name.startswith("S") and (p.suffix in [".py", ".sh"])])
    
    if not scripts:
        print("No scripts found!")
        sys.exit(1)
        
    failures = []
    print(f"Found {len(scripts)} sanity checks in {SANITY_DIR}\n")
    
    for s in scripts:
        if not run_script(s):
            failures.append(s.name)
            
    if failures:
        print(f"\n❌ {len(failures)} checks failed: {failures}")
        sys.exit(1)
        
    print("\n✅ All sanity checks passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
