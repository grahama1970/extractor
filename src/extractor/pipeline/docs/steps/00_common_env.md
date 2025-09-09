# Common Environment and Session Settings

- VLM Model: `LITELLM_VLM_MODEL` is the single source for multimodal LLM (e.g., `openai/gpt-5-mini`).
- Session: `LITELLM_SESSION_ID` identifies a pipeline run. It appears in logs and scopes the cache namespace.
- Provider attachment: `LITELLM_ATTACH_SESSION` (default: true) attaches `user` and `metadata.session_id` to provider calls.
- Cache namespace: `LITELLM_CACHE_NAMESPACE` (default: `LITELLM_SESSION_ID`) isolates Redis cache per run.
- Multimodal routing: All steps use `litellm_call`, which auto-routes GPT‑5 + images via OpenAI Responses API and normalizes outputs.
- ArangoDB: `ARANGO_HOST/PORT/USER/PASSWORD/DATABASE`. Use a dedicated test DB during development.

Recommended per-run exports
```
export LITELLM_VLM_MODEL=openai/gpt-5-mini
export LITELLM_SESSION_ID=$(date +%s)-dev
export LITELLM_ATTACH_SESSION=true
export ARANGO_DATABASE=pdf_knowledge_base_test_${LITELLM_SESSION_ID}
```
