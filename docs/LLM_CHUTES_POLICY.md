#!/usr/bin/env markdown

# SciLLM Chutes Calls — Standard Policy

TL;DR (always)
- Router → SDK → curl. Curl is the hard fallback and must save artifacts.
- Never introduce ad‑hoc httpx paths; use the shared helpers.
- Prefer tenant‑listed models from `/v1/models` and set two alternates.
- Use `SCILLM_FORCE_CURL=1` to bypass Router/SDK globally when stability matters.

Shared helpers
- Text JSON (async): `extractor.pipeline.utils.chutes_text.achutes_text_json(messages, …)`
- Routers: `get_text_router()`, `get_vlm_router()`
- Curl (OpenAI‑compatible): `chutes_curl_chat_json(messages, …)`

Required env
- Text: `CHUTES_TEXT_MODEL` (+ `CHUTES_TEXT_MODEL_ALT1`, `ALT2`)
- VLM: `CHUTES_VLM_MODEL` (+ `CHUTES_VLM_MODEL_ALT1`, `ALT2`)
- Router/backoff: `SCILLM_CHUTES_CANONICALIZE_OPENAI_AUTH=1`, `LITELLM_MAX_RETRIES=3`, `LITELLM_RETRY_AFTER=2`, `SCILLM_COOLDOWN_429_S=120`, `SCILLM_RATE_LIMIT_QPS=2`
- Force curl: `SCILLM_FORCE_CURL=1`

Artifacts (curl)
- Always write `*.payload.json`, `*.headers.txt`, `*.response.json` under `scripts/artifacts/`.

References
- SCILLM usage guide: `SCILLM_USAGE.md`
- Chutes Quickstart: `../litellm/QUICKSTART.md` (OpenAI‑compatible payloads)

Examples
```bash
export CHUTES_TEXT_MODEL='Qwen/Qwen3-235B-A22B-Instruct-2507' \
       CHUTES_TEXT_MODEL_ALT1='deepseek-ai/DeepSeek-V3.1' \
       CHUTES_TEXT_MODEL_ALT2='zai-org/GLM-4.6-FP8'
export SCILLM_CHUTES_CANONICALIZE_OPENAI_AUTH=1 \
       LITELLM_MAX_RETRIES=3 LITELLM_RETRY_AFTER=2 \
       SCILLM_COOLDOWN_429_S=120 SCILLM_RATE_LIMIT_QPS=2

# Force curl when stabilizing
export SCILLM_FORCE_CURL=1
```

