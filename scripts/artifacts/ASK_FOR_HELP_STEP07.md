# Fork
Fork: grahama1970/extractor
Branch: feat/section-heuristics-and-overlay
Path: git@github.com:grahama1970/extractor.git#feat/section-heuristics-and-overlay

## Help Needed: Stage 07 Prompt + Schema Reliability (Multimodal Reflow)

TL;DR
- We need a production‑safe prompt + minimal parser tweaks that reliably yield a single JSON object with `reflowed_json` for one section, using OpenAI‑compatible models via Chutes. The section input is: (a) the section’s compact JSON (title, pages, counts, text snippet), plus (b) optionally one section image and up to 2 low‑confidence table images.

What we’re asking for
- A small, working message template (SYSTEM + USER content order, where images go) that consistently returns:
  `{ reflowed_json: { title, blocks: [...] }, ocr_corrections: {}, improvements_made: "", summary: "" }`.
- Ready‑to‑apply unified diffs that: (1) install this prompt, (2) add any necessary small parser improvements, (3) adjust timeouts/retries if you recommend it.
- If model choice matters, propose the best among our verified Chutes models (DeepSeek V3.1, GLM‑4.5‑Air); if both are flaky, provide a Gemini 2.5 Flash variant as a fallback.

Why this matters now
- Stage 07 is the last mile: exporters and downstream consumers require the strict JSON to pass CI. Without a reliable `reflowed_json`, we fail the pipeline gate.

Inputs (per section)
- Section JSON summary (compact): `{ title, page_start, page_end, table_count, figure_count, text[:N] }`
- Optional images (deterministic order):
  1) section image (one)
  2) up to 2 low‑confidence table crops
  3) first figure (optional)

What we already implemented
- Hardened extraction and auto‑wrapper for plausible `{title,blocks}` payloads.
- LiteLLM callback hygiene to avoid MAX_CALLBACKS buildup.
- Chutes router fix: route `openai/<vendor>/<name>` as `<vendor>/<name>`.
- Single‑section repro + prompt lab to iterate guard styles and models.

How to reproduce (single section)
```bash
source .venv/bin/activate && set -a && source .env && set +a

# Pick a verified model from your /models listing on your account
export LITELLM_VLM_MODEL="openai/deepseek-ai/DeepSeek-V3.1"
export LITELLM_LARGE_VLLM_MODEL="openai/deepseek-ai/DeepSeek-V3.1"

PYTHONPATH=./src \
python debug/reflow_single_section.py \
  --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
  --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
  --index 0 --timeout 60 --model "$LITELLM_VLM_MODEL"

# Artifacts
#  scripts/artifacts/reflow_single_section_0_raw.txt
#  scripts/artifacts/reflow_single_section_0_result.json
```

Prompt lab (iterate guards + models; Gemini fallback optional)
```bash
PYTHONPATH=./src \
python debug/step07_prompt_lab.py \
  --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
  --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
  --index 0 \
  --models "openai/deepseek-ai/DeepSeek-V3.1,openai/zai-org/GLM-4.5-Air" \
  --guards strict,minimal \
  --timeout 60 --max-chars 8000 \
  --out-dir scripts/artifacts/prompt_lab \
  --try-gemini true
```

Acceptance (ask)
- With at least one of the verified Chutes models, the section run returns a strict JSON response that includes `reflowed_json`. If none succeeds, the Gemini 2.5 Flash variant works with a nearly identical prompt.
- Parser retains minimal repair but no infinite retries; record `parse_strategy` in metadata.
- No MAX_CALLBACKS warnings; deterministic outputs intact.

Blocking questions (please answer with unified diffs)
1) SYSTEM/USER template: the exact short contract + guard text, and whether to include `response_format={"type":"json_object"}` for DeepSeek/GLM on Chutes. Place images before or after text?
2) Parser: keep our scan/repair + auto‑wrapper, or propose a more robust extractor (code). If you prefer a tool/function style, include exact JSON/tool schema and code.
3) Timeouts/retry: recommend first‑token soft timeout vs hard timeout, and a single retry (images off + trimmed text). Provide exact numbers and env flags.
4) Model choice: pick one of DeepSeek V3.1 or GLM‑4.5‑Air for strict JSON; if inconclusive, supply Gemini fallback prompt.
5) Test: provide a minimal mocked test that asserts `reflowed_json` on a fenced/verbose response.

Relevant paths to review
- Stage 07: `src/extractor/pipeline/steps/07_reflow_section.py`
- Router:   `src/extractor/pipeline/utils/litellm_call.py`
- Debug:    `debug/reflow_single_section.py`, `debug/step07_prompt_lab.py`
- Inputs:   `data/results/pipeline/04_section_builder/json_output/04_sections.json`
- Images:   `data/results/pipeline/04_section_builder/image_output/` (section_*.png)

Artifacts
- `scripts/artifacts/reflow_single_section_*` (raw/result)
- `scripts/artifacts/prompt_lab/run_*/summary.json`
- `scripts/artifacts/stage07_live_run.log`

Thank you — please return answers and ready‑to‑apply diffs.

