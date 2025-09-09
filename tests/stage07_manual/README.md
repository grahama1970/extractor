# Stage 07 Manual VLM Payload (GPT‑5 mini)

This folder contains a complete, ready‑to‑send JSON payload for testing Stage 07 (reflow) manually against the OpenAI Responses API with GPT‑5 mini. It embeds images as base64 data URLs and includes the exact system/user content we send programmatically.

Files
- `responses_input.json`: OpenAI Responses input with `input:[{role,user,content:[input_text,input_image,...]}]`.
- `chat_messages.json`: Chat‑style `messages` payload (for reference/use with LiteLLM or playgrounds).
- `context_text.txt`: The exact text sent alongside images.
- `images/section.png`, `images/table1.png`, `images/figure1.png`: Extracted from your last pipeline run for inspection.
- `build_payload.py`: Script that assembles (and re‑generates) payload files from the latest pipeline results.

Prereqs
- Run the pipeline end‑to‑end (stages 01→06) so images exist under `data/results/pipeline/...`.
- Python env for the builder script.

Build/refresh payload
```
python tests/stage07_manual/build_payload.py \
  --results data/results/pipeline \
  --out tests/stage07_manual
```

Send to OpenAI Responses API (manual)
```
export OPENAI_API_KEY=sk-...
curl -sS \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/responses \
  -d @tests/stage07_manual/responses_input.json | jq .
```

Notes
- Model: `gpt-5-mini` (Responses API). We set `temperature=1.0`, `max_output_tokens=1200`, and request `response_format: {"type":"json_object"}`.
- If you want to try without strict JSON: remove the `response_format` field and resend.
- If the payload fails due to image size, re‑run the builder; it re‑encodes images via PIL.
