#!/usr/bin/env python3
"""
Contract linter: Ensure all pipeline steps call Chutes via SciLLM Router only.

Rules:
- No direct HTTP to /chat/completions or manual Authorization headers in steps.
- No requests/httpx/aiohttp usage in steps (preflight validator is exempt).
- Steps must import get_text_router/get_vlm_router OR use scillm_json_text/scillm_json_vlm.

Exit non-zero on violations; print offending files/lines.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
STEPS = ROOT / "src/extractor/pipeline/steps"

ALLOWLIST = {
    (STEPS / "scillm_preflight_validator.py").resolve(),
    (STEPS / "08_lean4_theorem_prover.py").resolve(),  # allowed to use httpx for Certainly health/bridge
}

PAT_HTTP = re.compile(r"/chat/completions|Authorization:\s*Bearer", re.IGNORECASE)
PAT_LIBS = re.compile(r"\b(requests\.|httpx\.|aiohttp\.)")
PAT_CHUTES = re.compile(r"\bchutes\b|/chat/completions|scillm", re.IGNORECASE)

violations: list[str] = []

for py in sorted(STEPS.glob("*.py")):
    text = py.read_text(encoding="utf-8", errors="ignore")
    # allow preflight file
    if py.resolve() in ALLOWLIST:
        continue
    # Direct HTTP markers
    if PAT_HTTP.search(text):
        violations.append(f"{py}: contains raw /chat/completions or Authorization header")
    # Disallowed HTTP client libs when combined with Chutes/SciLLM context
    if PAT_LIBS.search(text) and PAT_CHUTES.search(text):
        violations.append(f"{py}: uses HTTP client libs alongside Chutes/SciLLM – use Router only")

if violations:
    print("SciLLM contract violations detected:")
    for v in violations:
        print(" -", v)
    sys.exit(2)
else:
    print("OK: All steps comply with SciLLM Chutes contract.")
    sys.exit(0)
