from scillm import completion
import os, json

base = os.environ["CHUTES_API_BASE"]  # must end with /v1
key  = os.environ["CHUTES_API_KEY"]
_mid = open("scripts/artifacts/chutes_models_ids.txt", "r", encoding="utf-8").read().splitlines()[0]
model = _mid if _mid.startswith("openai/") else f"openai/{_mid}"

resp = completion(
    model=model,
    api_base=base,
    api_key=None,  # prevent SDK Bearer injection
    messages=[{"role": "user", "content": 'Return only {"ok":true} as JSON.'}],
    response_format={"type": "json_object"},
    extra_headers={"x-api-key": key},      # explicit auth: x-api-key
)

print(resp.choices[0].message.get("content", ""))
