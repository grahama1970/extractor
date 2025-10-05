# Debug Probes for Warm Starts and Router Behavior

These scripts isolate LiteLLM/Chutes behavior to avoid pipeline complexity. All produce explicit logs + JSON artifacts.

## 1) Warm Start Probe (single model)

```
source .venv/bin/activate
python debug/chutes_warm_start_probe.py \
  --model "${STAGE07B_MODEL:-openai/zai-org/GLM-4.5-Air}" \
  --count 10 --interval 5 --timeout 120 --retries 2 \
  --output debug/artifacts/warm_probe.json
```

- Sends `count` short requests, one at a time, every `interval` seconds.
- Records per‑call latency, status (ok/error), and any Retry‑After behavior.

## 2) Router Probe (batch, small concurrency)

```
python debug/litellm_router_probe.py \
  --model "${STAGE07C_MODEL:-openai/zai-org/GLM-4.5-Air}" \
  --batch-size 8 --concurrency 2 --timeout 90 --retries 2 \
  --output debug/artifacts/router_probe.json
```

- Exercises Router with bounded concurrency.
- Logs request/response timings and error taxonomy per item.

## 3) Pipeline Stage Sampler (limit N items)

```
STAGE07_MAX_ITEMS=5 \
STAGE07_GLOBAL_CONCURRENCY=2 STAGE07_REQUEST_TIMEOUT=120 STAGE07_NUM_RETRIES=2 \
LITELLM_FILE_LOG=1 \
python debug/run_stage07_live_sample.py
```

- Runs 07b→07c→07d for at most `STAGE07_MAX_ITEMS` items per stage, then 07e assemble.
- Writes a compact summary JSON under `debug/artifacts/stage07_live_sample.json`.

Artifacts and logs are under `debug/artifacts/` and `data/results/pipeline/logs/`.
