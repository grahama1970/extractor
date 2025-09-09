03 Suspicious Headers

Purpose
- Verify candidate section headers using a vision-capable LLM on an image of the block plus neighbors.
- Incorporate Stage 01 annotation cues (prioritizing `relevant_to: ["03"]`) to bias or auto-reject.
- Persist verdicts to JSON (and optionally ArangoDB) for downstream stages.

Inputs
- Stage 02 Marker JSON of blocks (`input_json`).
- Clean PDF from Stage 01 (`--pdf-dir`, first `*_clean.pdf` is used).
- Optional Stage 01 annotations JSON (`--annotations`).

Outputs
- `03_suspicious_headers/json_output/03_verified_blocks.json` (flattened `blocks`).
- `03_suspicious_headers/image_output/*.png` (context images per candidate).
- Optional DB inserts into `headers_verified` (when env + `--persist-headers`).

Key Behavior
- Vision preflight: rejects models without image support before batch calls.
- Context image: renders target+nearest non-empty above/below at `--dpi` with small margin.
- Signals to LLM: injects concise font/color/confidence signals (from `first_span_font`, `surya_confidence`, `suspicion_confidence`, `quality_score`).
- Annotation cues: overlap-match per-page annotations; boost those with `relevant_to: ["03"]`; auto-reject on strong negative cues using `config/relevant_rules.json` thresholds.
- Result write-back: sets `llm_verification`, clears `suspicious_header`, adjusts `block_type` to `Text` when rejected; updates suspicion fields by default.
 - Verify-all mode: `--verify-all-headers` treats every `SectionHeader` as a candidate (ignores Stage 02 suspicious flags) for targeted testing.

CLI (main)
- `run <input_json> --pdf-dir <dir> -o <results_dir> [--annotations --model -c --dpi --debug --limit --timeout --use-knowledge/--no-knowledge --auto-reject/--no-auto-reject --persist-headers/--no-persist-headers --verify-all-headers/--only-suspicious]`

Environment
- LLM: `LITELLM_VISION_MODEL` (e.g., `openai/gpt-5-mini`).
- Optional ArangoDB: `ARANGO_HOST/PORT/USER/PASSWORD/DATABASE`, `ARANGO_HEADERS_VERIFIED_COLLECTION`.

Downstream
- Produces verified headers for section building and reflow; suspicion fields reflect final verdict for consistency.
