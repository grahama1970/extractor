#!/usr/bin/env bash
set -uo pipefail

# Minimal sanity checks for text + vision routes via LiteLLM Router.
# Writes artifacts under scripts/artifacts/.

ART_DIR="scripts/artifacts"
mkdir -p "$ART_DIR"

# Activate env if present
if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
fi
set -a && [[ -f .env ]] && source .env && set +a

TEXT_MODEL=${LITELLM_DEFAULT_MODEL:-${LITELLM_MODEL:-${LITELLM_MED_TEXT_MODEL:-${LITELLM_SMALL_TEXT_MODEL:-""}}}}
# Prefer Chutes provider when CHUTES_API_KEY is set
if [[ -n "${CHUTES_API_KEY:-}" ]]; then
  # With scillm mapping, treat Chutes as OpenAI-compatible via OPENAI_* env;
  # keep the model as openai/* alias from .env
  VLM_MODEL=${LITELLM_VLM_MODEL:-${LITELLM_SMALL_VLM_MODEL:-${LITELLM_MED_VLM_MODEL:-${LITELLM_LARGE_VLLM_MODEL:-$TEXT_MODEL}}}}
else
  VLM_MODEL=${LITELLM_VLM_MODEL:-${LITELLM_SMALL_VLM_MODEL:-${LITELLM_MED_VLM_MODEL:-${LITELLM_LARGE_VLLM_MODEL:-$TEXT_MODEL}}}}
fi

if [[ -n "${CHUTES_API_KEY:-}" ]]; then
  # Prefer a known-deployed text model on Chutes when available
  TEXT_MODEL=${LITELLM_LARGE_TEXT_MODEL:-${LITELLM_MED_TEXT_MODEL:-${LITELLM_SMALL_TEXT_MODEL:-$TEXT_MODEL}}}
fi
echo "[sanity] Text model: ${TEXT_MODEL}"
python -m extractor.pipeline.utils.litellm_call sanity \
  --model "$TEXT_MODEL" \
  --wrap-json \
  --timeout 20 \
  | tee "${ART_DIR}/llm_sanity_text.json" >/dev/null || true

echo "[sanity] Vision model: ${VLM_MODEL}"
python -m extractor.pipeline.utils.litellm_call main \
  --model "$VLM_MODEL" \
  --json \
  --timeout 30 \
  --no-progress \
  @- <<<'Return only {"ok":true} as JSON.' \
  | tee "${ART_DIR}/llm_sanity_vlm.json" >/dev/null || true

echo "Saved: ${ART_DIR}/llm_sanity_text.json"
echo "Saved: ${ART_DIR}/llm_sanity_vlm.json"
