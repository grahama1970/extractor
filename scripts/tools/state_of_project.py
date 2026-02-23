#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

import os
import subprocess
import glob
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ART = os.path.join(ROOT, "scripts", "artifacts")
DOC = os.path.join(ROOT, "docs", "STATE_OF_PROJECT.md")


def run(cmd: str, env=None) -> tuple[int, str]:
    print(f"$ {cmd}")
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=ROOT,
        env=env or os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def latest(pattern: str) -> str:
    files = sorted(glob.glob(os.path.join(ART, pattern)))
    return files[-1] if files else ""


def main():
    ts = datetime.utcnow().isoformat(timespec="seconds").replace(":", "-") + "Z"
    # UX Health
    ux_code, ux_out = run("BASE_URL=http://127.0.0.1:8080/main node scripts/ux_check_broken.mjs")
    ux_log = latest("ux_check_*.log")

    # UI smokes
    kc_code, _ = run("BASE_URL=http://127.0.0.1:8080 node scripts/smokes/ui_keyboard_core.mjs")
    sh_code, _ = run(
        "BASE_URL=http://127.0.0.1:8080 node scripts/smokes/ui_search_highlight_thumb.mjs"
    )

    # API smokes
    oslc_code, _ = run("BASE_URL=http://127.0.0.1:8000 uv run scripts/smokes/api_oslc_stub.py")
    cfs_code, _ = run("BASE_URL=http://127.0.0.1:8000 uv run scripts/smokes/api_conflicts_save.py")

    # Pipeline smokes
    reqif_code, _ = run(
        "PYTHONPATH=$(pwd)/src .venv/bin/python scripts/smokes/pipeline/smoke_reqif_export_v0.py"
    )
    rtm_code, _ = run(
        "PYTHONPATH=$(pwd)/src .venv/bin/python scripts/smokes/pipeline/smoke_stage14_rtm_v0.py"
    )
    resume_code, _ = run(
        "PYTHONPATH=$(pwd)/src .venv/bin/python scripts/smokes/pipeline/smoke_resume_manifest.py"
    )

    # Artifacts
    reqif_path = os.path.join("scripts", "artifacts", "export.reqif")
    rtm_md = os.path.join("scripts", "artifacts", "rtm_smoke", "final_report.md")
    resume_md = os.path.join("scripts", "artifacts", "resume_smoke", "final_report.md")

    section = []
    section.append("\n---\n")
    section.append(f"## Auto‑Run Validation — {ts}")
    section.append("")
    section.append("- UX Health")
    section.append(
        "  - Command:\n    ```bash\n    BASE_URL=http://127.0.0.1:8080/main \\\n    node scripts/ux_check_broken.mjs\n    ```"
    )
    section.append(f"  - Status: {'OK' if ux_code==0 else 'FAIL'}")
    section.append(f"  - Latest log: {ux_log or '(none)'}")
    section.append("")
    section.append("- UI Smokes (subset)")
    section.append(
        f"  - Keyboard core: {'OK' if kc_code==0 else 'FAIL'} — scripts/smokes/ui_keyboard_core.mjs"
    )
    section.append(
        f"  - Search highlight + thumb: {'OK' if sh_code==0 else 'FAIL'} — scripts/smokes/ui_search_highlight_thumb.mjs"
    )
    section.append("")
    section.append("- API Smokes")
    section.append(f"  - OSLC stub: {'OK' if oslc_code==0 else 'FAIL'}")
    section.append(f"  - Conflicts save: {'OK' if cfs_code==0 else 'FAIL'}")
    section.append("")
    section.append("- Pipeline Smokes")
    section.append(f"  - ReqIF v0 export: {'OK' if reqif_code==0 else 'FAIL'} — {reqif_path}")
    section.append(f"  - RTM v0 report: {'OK' if rtm_code==0 else 'FAIL'} — {rtm_md}")
    section.append(f"  - Resume manifest: {'OK' if resume_code==0 else 'FAIL'} — {resume_md}")
    section.append("")
    section.append("Artifacts for this run are stored under scripts/artifacts/ with timestamps.")

    md = "\n".join(section) + "\n"
    with open(DOC, "a", encoding="utf-8") as f:
        f.write(md)
    print(f"Updated {DOC} with auto-run section ({ts}).")


if __name__ == "__main__":
    main()
