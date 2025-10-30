- Stage sequencing in driver:
      - 05_table_extractor is executed twice in src/
        extractor/pipeline/run_pipeline.py: it runs once
        with artifacts indexing and manifest record,
        then a second time again right after. This
        wastes time and can confuse downstream counts.
        > can you fix this. That sounds like bad code or a bug

      - RunManifest is created then later overwritten
        by a dict named manifest; finalize() never runs
        due to shadowing (caught by broad except). Final
        manifest file may be stale or missing finalize
        metadata.
    > this souuds (again) like bad code written by you. Fix

      - --stop-on-fail uses action="store_true" with
        default=True, so it’s effectively always true;
        there’s no way to disable stop-on-fail via CLI.

 > this souuds (again) like bad code written by you. Fix

  - Stage 04 vs Stage 03:
      - The pipeline does not call
        03_suspicious_headers, but 04_section_builder’s
        run() defaults fallback_heuristics=False.
        Without Stage 03 verification signals, 04 will
        lean on Marker’s SectionHeader labels only.
        Enabling fallback heuristics when 03 is skipped
        would reduce fragility.
> do NOT skip 03_suspicious_headers. This sounds like bad code written by you, and 100% set against the purpose of the pdf extraction

  - Stage 07 (reflow) compliance and offline behavior:
      - Two different functions named
        _build_compact_prompt are defined in the same
        file; the second silently overwrites the first.
        This is brittle and confusing.
> this souuds (again) like bad code written by you. Fix

      - It constructs a litellm.Router locally rather
        than using the centralized SciLLM router in
        extractor/pipeline/utils/scillm_router.py,
        violating the “Router-only, centralized” policy
        in AGENTS.md.
> this souuds (again) like bad code written by you. Fix

      - Preflight: even when run with --summary-only
        (text-only mode), it still performs a SciLLM
        preflight and raises if CHUTES_* env isn’t set.
        That blocks the intended offline path.
      - Net effect: pdf extraction/reflow will
        fail without CHUTES configuration even with
        --summary-only, and it deviates from the
        mandated router usage in this repo.
  - Optional inputs:
      - 09a_pdf_annotator tolerates missing 03/06b
        inputs (auto-discovery); run_pipeline passes a
        fixed 06b path that may not exist, but the step
        gracefully checks for existence before use. This
        is okay.
  - External deps to run end-to-end:
      - Stage 01 and 04 require PyMuPDF; Stage 05
        requires Camelot (and system dependencies like
        Ghostscript). Stage 02 relies on project Marker
        internals but does have a fallback simple
        extractor.
      - With current code, a summary-only, figure-desc-
        skipped run still requires CHUTES_* for Stage
        07; that contradicts the intended “offline”
        mode.