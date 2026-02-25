# SciLLM Usage (Chutes, OpenAI‑compatible)

This repo uses SciLLM directly for all Chutes calls. Follow this guide for a friction‑free setup.

## TL;DR (Works Everywhere)

- Activate env + load .env, then ensure we never send Bearer by mistake:
  ```bash
  source .venv/bin/activate
  set -a && [ -f .env ] && source .env && set +a
  unset OPENAI_API_KEY
  export SCILLM_AUTOSCALE=1
  ```
- Verify your tenant and pick a model id:
  ```bash
  BASE_NO_V1=${CHUTES_API_BASE%/v1}
  curl -sS -H "x-api-key: $CHUTES_API_KEY" "$BASE_NO_V1/v1/models" | jq -r '.data[].id' | head
  export CHUTES_TEXT_MODEL="<one-id-from-the-list>"
  ```
- Call SciLLM directly (OpenAI‑compatible path + x‑api‑key):
  ```python
  from scillm import completion
  out = completion(
      model=os.environ["CHUTES_TEXT_MODEL"],
      custom_llm_provider="openai_like",
      api_base=os.environ["CHUTES_API_BASE"],
      api_key=None,
      extra_headers={"x-api-key": os.environ["CHUTES_API_KEY"]},
      messages=[{"role":"user","content":"Return only {\\"ok\\":true} as JSON."}],
      response_format={"type":"json_object"},
      timeout=60,
  )
  ```

## Call Pattern (single source of truth)
Use scillm directly in steps. Contract:
- custom_llm_provider="openai_like"
- api_base=$CHUTES_API_BASE
- api_key=None and extra_headers={"x-api-key": $CHUTES_API_KEY}
- response_format as needed (json_object/json_schema)

## Direct (Only if You Must)

If a step requires `scillm.completion` directly, mirror QUICKSTART:
```python
from scillm import completion
resp = completion(
  model=os.environ["CHUTES_TEXT_MODEL"],
  api_base=os.environ["CHUTES_API_BASE"],  # may include /v1
  api_key=None,                             # prevents Bearer
  custom_llm_provider="openai_like",
  messages=[{"role":"user","content":"Return only {\\"ok\\":true} as JSON."}],
  response_format={"type":"json_object"},
  extra_headers={"x-api-key": os.environ["CHUTES_API_KEY"]},
  timeout=60,
)
```
If you see a 404 on `/chat/completions`, flip the base: add or remove `/v1` and retry once.

## Environment Variables

- `CHUTES_API_BASE` (required): OpenAI‑compatible base (often ends with `/v1`).
- `CHUTES_API_KEY` (required): x‑api‑key for your tenant.
- `CHUTES_TEXT_MODEL` (required in production paths): pick from `/v1/models` on your tenant.
- `CHUTES_VLM_MODEL` (optional): vision model id for VLM steps.
- `SCILLM_AUTOSCALE=1` (recommended): enables gentle pacing to avoid rate limits.
- DO NOT set `OPENAI_API_KEY` for Chutes calls; it forces Bearer.

## Pipeline Integration

- Stage 06a Title/Caption Enricher calls `chutes_chat_json` only.
- The legacy `litellm_call` shim has been retired from extractor usage; do not reference it in new code.
- Preferred usage in new code: import `chutes_chat_json`.

## Quick Doctor (manual)

```bash
# 1) Env
source .venv/bin/activate
set -a && source .env && set +a
unset OPENAI_API_KEY
export SCILLM_AUTOSCALE=1

# 2) Models list (expect 200 + ids)
BASE_NO_V1=${CHUTES_API_BASE%/v1}
curl -sS -H "x-api-key: $CHUTES_API_KEY" "$BASE_NO_V1/v1/models" | jq -r '.data[].id' | head

# 3) Tiny JSON chat via helper (expect {"ok":true})
python - <<'PY'
import os
from extractor.pipeline.utils.chutes_scillm import chutes_chat_json
m=os.environ.get('CHUTES_TEXT_MODEL') or 'chutesai/Mistral-Small-3.1-24B-Instruct-2503'
res=chutes_chat_json(model=m, messages=[{"role":"user","content":"Return only {\\\"ok\\\":true} as JSON."}], timeout=15)
print(res.get('choices',[{}])[0].get('message',{}).get('content',''))
PY
```

## Troubleshooting

- 404 on `/chat/completions` → flip base.
- “Unmapped LLM provider” → ensure `custom_llm_provider='openai_like'` and `api_key=None` (if you are bypassing the helper).
- 401/Bearer path → unset `OPENAI_API_KEY` and rely on `x-api-key`.
- Vendor id timeouts/404 → pick a model id from your tenant’s `/v1/models`.

## References

- QUICKSTART (source of truth): `/home/graham/workspace/experiments/litellm/QUICKSTART.md`

## Do/Don’t

- Do: use `chutes_chat_json` for all Chutes calls.
- Do: keep `OPENAI_API_KEY` unset for Chutes.
- Don’t: hardcode provider names per step; let the helper decide.
- Don’t: thread custom headers everywhere; use the helper.

---

This file is the canonical reference. If anything here stops working with your tenant, run the “Quick Doctor” above and attach logs from `scripts/artifacts/` when asking for help.
