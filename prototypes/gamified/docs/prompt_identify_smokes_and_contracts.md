# litellm_call Smokes and Contracts

Goal: maintain a minimal, reproducible set of smoke checks for `extractor.pipeline.utils.litellm_call` that do not collide with the upstream `litellm` package and that exercise both text and multimodal paths, including batching and fan‑out.

## Preconditions

- Activate venv + env:
  ```bash
  source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
  ```
- Set one of the following in `.env` (in order of precedence used by our code):
  - `LITELLM_MODEL` (optional)
  - `LITELLM_DEFAULT_MODEL` (preferred)
  - `DEFAULT_LITELLM_MODEL` (optional)
  - Example: `LITELLM_DEFAULT_MODEL=openai/gpt-4o-mini`
- Ensure matching provider key(s) are present (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, etc.).

## Do not collide with `litellm` package

- Always execute via our module path, not the upstream package name:
  ```bash
  export BASE="PYTHONPATH=src python src/extractor/pipeline/utils/litellm_call.py"
  ```
- Import helpers using the project path: `from extractor.pipeline.utils import litellm_call`.

## Quick Health

```bash
$BASE sanity --wrap-json
```

Success criteria: prints JSON containing `{"ok": true}` and exits 0.

## Text‑only Smokes

```bash
# Simple text, JSON shorthand
$BASE main --json "Return only {\"ok\":true} as JSON"

# Multiple prompts
$BASE main "What is 2+2?" "Capital of France?"
```

## Fan‑out Across Models (one prompt → many models)

```bash
$BASE main "Summarize in one sentence." \
  --models "openai/gpt-4o-mini,anthropic/claude-3-5-haiku" \
  --prefix-model
```

## Multimodal Smokes

```bash
# Image via URL
IMG_URL="https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Grosser_Panda.JPG/960px-Grosser_Panda.JPG"
$BASE main "Describe this image: $IMG_URL"

# Image via local path (auto-compresses to data URL)
$BASE main "Describe ./path/to/image.jpg"
```

Tip: set `LITELLM_IMAGE_CACHE_DIR` or use `--image-cache-dir` for persistent caching.

## Streaming (single prompt)

```bash
$BASE main --stream "Write a haiku about pandas."
```

## File & Stdin Inputs

```bash
# Prompts from file (lines)
printf "Hello\nWorld\n" > /tmp/prompts.txt
$BASE main @/tmp/prompts.txt

# JSONL
printf '{"text":"Say hi"}\n' > /tmp/prompts.jsonl
$BASE main --jsonl @/tmp/prompts.jsonl

# Stdin
echo "What is 3+5?" | $BASE main --stdin
```

## Artifacts and Logs (optional)

Append results to a file for triage:

```bash
mkdir -p scripts/artifacts
TS=$(date +%Y%m%d_%H%M%S)
$BASE main --json "Return only {\"ok\":true}" --quiet --output scripts/artifacts/litellm_smoke_${TS}.log
```

## Exit Codes and Troubleshooting

- `sanity` exits 0 only if the output JSON contains `{"ok": true}`; otherwise 2.
- Common failures:
  - Auth: invalid API key → set provider env var.
  - Model name: verify the model exists for your provider.
  - Vision unsupported: switch to a vision‑capable model or remove image parts.

## Contracts (Expectations)

- CLI accepts prompts via args, files (`@file`), JSONL (`--jsonl`), and stdin (`--stdin`).
- `--json` implies `--wrap-json` and `--response-format json_object`.
- Fan‑out (`--models a,b`) duplicates each prompt and prefixes outputs with model name when `--prefix-model` is set.
- Streaming prints plain text and returns assembled text; metadata augmentation is not applied in streaming mode.
