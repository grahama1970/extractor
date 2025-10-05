## Extractor Features

### Reliability & Resilience
- Tenacity‑backed retries around LiteLLM Router
  - 429: honors Retry‑After (floor 0.5s)
  - 5xx/timeouts: exponential backoff with jitter (cap 10s)
  - Fast‑fail auth/404; single fallback attempt to a configured large model
- In‑process circuit breaker (open after sustained failures; cap window 30s)
- Optional pre‑call jitter gate when concurrency >1 (20–120 ms; seeded in deterministic mode)

### Strict JSON & Schema
- Stage 07 strict reflow uses response_format=json_object by default
- Optional json_schema (env: `STAGE07_STRICT_JSON_SCHEMA=1`) with auto‑downgrade
- Hardened tolerant parser as fallback if strict fails
- UnifiedDocument: `schema_version="1.0.0"`, normalization notes, deterministic ordering

### Determinism
- Defensive sorting of sections and tables
- Figure image hashing (sha256 first 4KB)
- Long paragraph splitting (default cap 2400 chars; env override)

### Structured Providers (Non‑PDF)
- Markdown: root heading (level 0), short‑line merges, schema_version/normalization
- HTML: schema_version/normalization; basic table and figure placeholders from DOM

### Toggle Matrix (selected)
- Stage 07 strict JSON default: `STAGE07_STRICT_JSON_DEFAULT=1`
- Prefer json_schema: `STAGE07_STRICT_JSON_SCHEMA=1`
- Disable strict default: `STAGE07_STRICT_JSON_DISABLE=1`
- Figure placeholder: `STAGE07_FIGURE_PLACEHOLDER=1`
- Paragraph cap: `UNIFIED_MAX_PARAGRAPH_CHARS=2400`
- Circuit breaker: `LITELLM_BREAKER_FAILS=5`, `LITELLM_BREAKER_CAP_S=30`
- Pre‑call jitter: `LLM_PRECALL_JITTER_MIN_MS=20`, `LLM_PRECALL_JITTER_MAX_MS=120`

### Artifacts & Logs
- Stage 07 per‑section logs: `data/results/pipeline/07_reflow_section/logs/`
- Router retries/backoff log: `data/results/pipeline/logs/litellm_call.log`

