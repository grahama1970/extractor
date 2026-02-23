import sys
import subprocess
from pathlib import Path

# Unified Sanity Runner
# Runs all sanity checks in sequence.

SANITY_DIR = Path(__file__).parent

CHECKS = [
    ("S05 Tables", "camelot_sanity.py"),
    ("S07 Ingest", "s07_ingest_sanity.py"),
    ("S08 Prover", "s08_prove_sanity.py"),
    ("S09 Summarizer", "s09_summarize_sanity.py"),
    # S10 sanity relies on S07 output, so it's a good end-to-end check
    ("S10 Export", "s10_export_sanity.py"),
]


def run_check(name, script):
    print(f"\n>>> Running Sanity Check: {name} ({script})")
    script_path = SANITY_DIR / script
    try:
        # Run in subprocess to isolate env/state
        res = subprocess.run(
            [sys.executable, str(script_path)], check=False, capture_output=True, text=True
        )
        if res.returncode == 0:
            print(f"✅ {name}: PASSED")
            print(res.stdout)
            return True
        else:
            print(f"❌ {name}: FAILED (Code {res.returncode})")
            print("--- STDOUT ---")
            print(res.stdout)
            print("--- STDERR ---")
            print(res.stderr)
            return False
    except Exception as e:
        print(f"❌ {name}: EXECUTION ERROR: {e}")
        return False


def main():
    print("=== PIPELINE SANITY SUITE ===")
    failed = []
    for name, script in CHECKS:
        if not run_check(name, script):
            failed.append(name)

    print("\n=== SUMMARY ===")
    if failed:
        print(f"❌ FAILED CHECKS: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("✅ ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
