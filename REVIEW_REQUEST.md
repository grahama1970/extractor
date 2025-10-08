# Review: Enforce Marker-only Extraction + Annotated Overlays

## Context
We hardened Stage‑02 to prohibit PyMuPDF/text heuristics and added a viewable overlay tool for visual collaboration. Please review enforcement, determinism, and safety.

## Questions
1) Stage‑02 enforcement: Are there any remaining code paths that could allow a non‑Marker fallback? If so, propose a unified diff to close them.
2) Determinism: Is our block ordering / content hashing sufficient across PDFs? Suggest improvements (unified diffs) to make summaries and hashes more robust.
3) Preflight & errors: Is the predictor preflight clear and early enough? Propose diffs to improve messages and testability.
4) Overlay clamping: Any edge cases where label rectangles can still go out of bounds or be zero/negative height? Suggest minimal fixes.
5) Scripts: Is `scripts/pipeline/run_and_annotate.py` robust for strict-only multi‑PDF runs? Recommend diffs for resiliency.

## Files to Review (relative)
- AGENTS.md
- src/extractor/pipeline/steps/02_marker_extractor.py
- src/extractor/pipeline/tools/render_annotated_pdf.py
- scripts/pipeline/run_and_annotate.py

## Repro
See `.github/copilot-instructions.md` (Repro Commands).

