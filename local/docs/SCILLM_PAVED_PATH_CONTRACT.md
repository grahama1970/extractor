# Extractor SciLLM Paved‑Path Contract (No Hacks / No Wrappers)

This project must call SciLLM and Chutes via the paved helpers and `api_key=` only — never manual headers or raw HTTP for `/v1/chat/completions`.

Do
- Use `scillm.acompletion/completion` with `custom_llm_provider='openai_like'`, `api_base=$CHUTES_API_BASE`, `api_key=$CHUTES_API_KEY`.
- Use `scillm.paved.list_models_openai_like` + `scillm.paved.sanity_preflight` for discovery and preflight (short‑wall, parallel).
- Use `scillm.Router` or `scillm.paved.chutes_router_json` when a router is needed; do not re‑implement routing.
- Request strict JSON where applicable: `response_format={'type':'json_object'}` (or json_schema).

Don’t
- Don’t set `extra_headers={"Authorization": ...}` or `extra_headers={"x-api-key": ...}` in code.
- Don’t use `requests/httpx/aiohttp/curl` to call `/v1/chat/completions` or `/v1/models` in executable code (docs are OK).
- Don’t implement client‑side alternates for Stage 07; preflight must fail fast so ops can fix routing/quota.

Grep guard (run locally or in CI)
```
rg -n "extra_headers=|Authorization|x-api-key|/chat/completions|requests\.(get|post)\(" experiments/extractor -g '!**/.venv/**'
```

Change history
- 2025‑11‑09: Initial version (enforced across Extractor repo).

