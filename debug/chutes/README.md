# Chutes Warm‑Start and Router Debugs

All scripts in this folder are self‑contained, fast, and produce explicit JSON artifacts. They fail fast if the proper venv/.env are not active.

Always activate venv + env first (from AGENTS.md):

```
source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
```

## Scripts

- list_models.py
  - Lists available Chutes model ids (uses `/models`).
  - Output: prints to stdout, optional JSON via `--output json`.

- warm_start_probe.py
  - Pings a single model N times with a tiny prompt.
  - Flags cold starts/timeouts; writes per‑call latencies and p50/p95.
  - Output: debug/artifacts/warm_probe.json

- router_probe.py
  - Sends a batch via LiteLLM Router with bounded concurrency.
  - Output: debug/artifacts/router_probe.json

- run_stage07_sample.py
  - Runs 07b→07c→07d with a cap (STAGE07_MAX_ITEMS), then 07e assemble.
  - Output: debug/artifacts/stage07_live_sample.json

- curl_chat_ping.sh
  - Raw curl against `/chat/completions` to isolate SDK issues.
  - Output: prints JSON; use `--model` to override.

## Quick starts

Warm probe (10 calls, 120s timeout, 2 retries)

```
python debug/chutes/warm_start_probe.py \
  --model "${STAGE07B_MODEL:-openai/zai-org/GLM-4.5-Air}" \
  --count 10 --interval 5 --timeout 120 --retries 2 \
  --output debug/artifacts/warm_probe.json
```

Router probe (8 items, concurrency=2)

```
python debug/chutes/router_probe.py \
  --model "${STAGE07C_MODEL:-openai/zai-org/GLM-4.5-Air}" \
  --batch-size 8 --concurrency 2 --timeout 90 --retries 2 \
  --output debug/artifacts/router_probe.json
```

List models

```
python debug/chutes/list_models.py
```

Raw curl ping

```
bash debug/chutes/curl_chat_ping.sh --model "zai-org/GLM-4.5-Air" --text "ping"
```
