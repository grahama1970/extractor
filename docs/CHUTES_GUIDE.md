Here are precise, actionable answers to the extractor agent’s
  questions, based on your live config (.env) and a real GET to
  your gateway.

  Models & Routing

  - Models (subset from GET https://llm.chutes.ai/v1/models)
      - deepseek-ai/DeepSeek-R1
      - deepseek-ai/DeepSeek-V3.1
      - deepseek-ai/DeepSeek-V3.1-Terminus
      - deepseek-ai/DeepSeek-V3-0324
      - moonshotai/Kimi-K2-Instruct-0905
      - chutesai/Mistral-Small-3.1-24B-Instruct-2503
      - chutesai/Mistral-Small-3.2-24B-Instruct-2506
      - zai-org/GLM-4.5-Air
      - zai-org/GLM-4.6-turbo
      - Qwen/Qwen2.5-72B-Instruct
      - Qwen/Qwen3-14B
      - Qwen/Qwen3-32B
      - Qwen/Qwen3-235B-A22B
      - Qwen/Qwen3-235B-A22B-Thinking-2507
  - Canonical naming vs openai/… aliases
      - Use canonical ids (no openai/ prefix) and set
        OPENAI_API_BASE=$CHUTES_API_BASE. We’ll keep a resolver
        mapping legacy openai/... names to these canonical ids
        for safety.
  - Alias mappings (current resolver defaults)
      - openai/chutesai/Mistral-Small-3.1-24B-Instruct-2503 →
        chutesai/Mistral-Small-3.1-24B-Instruct-2503
      - openai/Qwen/Qwen2.5-VL-72B-Instruct → not present on this
        gateway; nearest text model: Qwen/Qwen2.5-72B-Instruct (no
        VL). If vision is required, we need a VLM-enabled base or
        different model id.
      - openai/Qwen/Qwen3-VL-235B-A22B-Instruct → not present;
        nearest text models: Qwen/Qwen3-235B-A22B or Qwen/Qwen3-
        235B-A22B-Thinking-2507.
      - openai/zai-org/GLM-4.5-Air → zai-org/GLM-4.5-Air
      - openai/zai-org/GLM-4.6-turbo → zai-org/GLM-4.6-turbo
      - openai/deepseek-ai/DeepSeek-R1 → deepseek-ai/DeepSeek-R1
  - Provider prefix
      - No special chutes/ prefix needed. The OpenAI-compatible
        base is sufficient with canonical ids above.

  Auth & Endpoints

  - CHUTES_API_BASE: https://llm.chutes.ai/v1 (already includes /
    v1; do not append again)
  - CHUTES_API_KEY: Bearer token; use in Authorization header. No
    extra org/project headers observed.
  - Recommended environment mapping for clients
      - OPENAI_API_BASE=$CHUTES_API_BASE
      - OPENAI_API_KEY=$CHUTES_API_KEY
      - Keep a code-level alias normalizer (resolve_model_id) to
        map any openai/... to canonical ids.

  Request Parameters & Limits

  - From model metadata (example DeepSeek-R1):
    max_model_len=163840; max_output_length=163840;
    supported_features include json_mode and structured_outputs.
  - response_format={"type":"json_object"}: Supported on models
    that advertise json_mode/structured_outputs (DeepSeek-* and GLM
    entries do).
  - Vision inputs: This gateway listing shows text models; VL/VLM
    ids in your env (e.g., Qwen2.5‑VL‑72B) are not in /v1/models.
    Assume base64 data URLs only if/when a VLM is available; remote
    URLs should be considered unsupported until confirmed.
  - Timeouts: Recommend 40–60s for small/medium; 120–180s for
    large “Teacher” calls. Set client max timeout to 180s with
    exponential backoff.

  Rate Limits & Concurrency

  - Observed behavior: 429s appear when exceeding ~1–2 in‑flight
    per model (public endpoints). Start with concurrency=2/model,
    adapt with AIMD:
      - Backoff: exponential with jitter (base 0.8s, max 8s), honor
        Retry-After if returned.
      - Increase: +1 concurrency after 30s clean window; Decrease:
        halve on 429 burst >5% over 60s.

  Error Handling

  - Retryable: 429, 5xx, network timeouts. Treat as retry with
    backoff and respect Retry-After.
  - Fatal: 400 (bad request), 401/403 (auth), 404 (model not
    found), 422 (payload invalid). The gateway returns “model not
    found” when id is wrong; our resolver prevents most of these
    by normalizing.
  - Log enrichment: Surface HTTP status, error message, request_id
    (if present), and model id used.

  Environment & Config

  - Extractor expectations
      - Yes: map CHUTES_* to OPENAI_* at runtime when present.
      - Normalize model strings in code via resolve_model_id; do
        not rely on gateway aliases.
  - Library pins
      - We use the litellm Router interface and openai-compatible
        paths. No custom fork required. Keep litellm and openai
        python clients at current stable; we haven’t pinned to a
        specific version here. If you want a pin, we can add one
        after CI validates.

  Verification & Tests

  - Acceptance (we’ll deliver after you confirm above)
      - debug/test_scillm_text.py → prints {"ok": true}
      - debug/test_scillm_vlm.py → same (subject to an available
        VLM model on this base)
      - Artifacts saved under scripts/artifacts/.

  Observability & Logs

  - Set X-Request-Id on every request (uuid4) so you can correlate
    server logs if needed.
  - Health/metrics: We didn’t see a public /metrics on the gateway.
    Locally, we scrape our compare/judge exporter on 9400. If the
    gateway exposes /healthz or /metrics, share the URLs and auth;
    we’ll wire CI.

  CI/CD & Secrets

  - Secrets: store as GitHub Actions secret CHUTES_API_KEY (org/
    repo-level). No branch overrides needed unless you have
    start latency (we can add a job that hits /chat/completions
    with model=GLM-4.5-Air for 1 token).

  Fallbacks & Rollback

  - Fallback order (current)
      - For Teachers: deepseek-ai/DeepSeek-V3.1-Terminus →
        moonshotai/Kimi-K2-Instruct-0905 → Qwen/Qwen3-235B-A22B
        (text) → zai-org/GLM-4.6-turbo (cheap fallback).
      - For Students: chutesai/Mistral-Small-3.2-24B-Instruct-2506
        → Qwen/Qwen2.5-72B-Instruct → zai-org/GLM-4.5-Air (cheap).
  - litellm/SciLLM rollback: no fork required; we stick to OpenAI-
    compatible calls. If we hit regressions, pin previous known-
    good minor and re‑run the two acceptance tests.

  What you’ll get after this is locked

  - Minimal resolver (maps CHUTES_* → OPENAI_*; normalizes model
    ids) under src/extractor/pipeline/utils/litellm_call.py.
  - Two passing debug tests and saved artifacts.
  - README snippet with exact .env keys and verification one‑liner.

  Open items to confirm

  - Vision: Do you have a VLM model id on this gateway (e.g., Qwen-
    VL or Kimi-VL)? If yes, paste the exact id from /v1/models and
    any image payload constraints; otherwise we’ll gate VLM tests.
  - Any explicit rate limits per key you want us to aim under (RPS/
    QPS)?
  - Any special headers you want (customer-id, project-id) for
    server-side correlation?

  If you confirm the above (especially VLM availability), I’ll
  implement the extractor resolver + tests immediately and post
  the artifacts.


› don't you need to tell extractor agent how to use scillm to get
  currently available chutes models?


• Yes. Here’s exactly how the extractor agent should use SciLLM/
  OpenAI‑compatible calls to discover the currently available
  Chutes models and keep routing sane.

  How to list models (OpenAI‑compatible path)

  - Environment (map Chutes → OpenAI):
      - export OPENAI_API_BASE="$CHUTES_API_BASE"
      - export OPENAI_API_KEY="$CHUTES_API_KEY"
      - Note: CHUTES_API_BASE already includes /v1; don’t append
        it again.
  - One‑liner (curl):
      - curl -sS -H "Authorization: Bearer $CHUTES_API_KEY"
        "$CHUTES_API_BASE/models" | jq -r '.data[].id'
  - Python (OpenAI client; preferred inside SciLLM flows):
      - python - << 'PY'
        import os, json
        from openai import OpenAI
        client = OpenAI(base_url=os.environ["OPENAI_API_BASE"],
        api_key=os.environ["OPENAI_API_KEY"])
        resp = client.models.list()
        print(json.dumps([m.id for m in resp.data], indent=2))
        PY

  Where to call this in extractor

  - Before any model selection, fetch and cache to .artifacts/
    chutes/models.json so downstream can validate aliases and fail
    fast:
      - mkdir -p .artifacts/chutes
      - python (above) > .artifacts/chutes/models.json

  Alias normalization (so openai/... continues to work)

  - Keep canonical ids from /models (e.g., deepseek-ai/DeepSeek-
    V3.1-Terminus).
  - Maintain a small resolver in your extractor
    (resolve_model_alias):
      - If name starts with openai/, strip the prefix.
      - Map legacy names to canonical when needed:
          - openai/chutesai/Mistral-Small-3.1-24B-Instruct-2503 →
            chutesai/Mistral-Small-3.1-24B-Instruct-2503
          - openai/zai-org/GLM-4.5-Air → zai-org/GLM-4.5-Air
          - openai/zai-org/GLM-4.6-turbo → zai-org/GLM-4.6-turbo
          - openai/deepseek-ai/DeepSeek-R1 → deepseek-ai/DeepSeek-
            R1
          - Qwen VLM aliases: only keep if present in /models;
            otherwise downgrade to nearest text model (e.g., Qwen/
            Qwen2.5-72B-Instruct). Always verify presence against
            the cached list.

  SciLLM/litellm usage notes

  - SciLLM sits on OpenAI‑compatible APIs. For discovery, use the
    OpenAI client (above).
  - For completions, your existing litellm/SciLLM calls will work
    once OPENAI_API_BASE/KEY are set. Always run a pre‑run probe
    that:
      - Lists /models, resolves aliases, and drops any missing ids.
      - Optionally warms each selected model with a tiny prompt.

  Safety and timeouts

  - Default client timeout 60s (text), 120–180s (teacher/long).
  - Treat 429/5xx/timeouts as retryable (exponential backoff with
    jitter, honor Retry‑After).
  - Fail fast on 404 (“model not found”) and 401/403 (auth).

  If you want, I can drop a tiny helper into your extractor at src/
  extractor/pipeline/utils/litellm_call.py that:

  - fetches and caches /models
  - normalizes incoming model ids
  - exposes list_models() and resolve_model_id()
  - returns {"ok": true} in your two debug tests after a quick
    text call

  Say “add resolver” and I’ll commit that utility plus a debug/test
  script that saves the discovered model list under .artifacts/
  chutes/.