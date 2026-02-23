try:
    from litellm import Router  # type: ignore
except Exception:
    print("SKIP: litellm not installed; chutes_router_check skipped.")
    raise SystemExit(0)
import os

r = Router(
    default_litellm_params={
        "api_base": os.environ["CHUTES_API_BASE"],
        "api_key": None,  # prevent Bearer injection
        "extra_headers": {"x-api-key": os.environ["CHUTES_API_KEY"]},
    }
)

_mid = open("scripts/artifacts/chutes_models_ids.txt", "r", encoding="utf-8").read().splitlines()[0]
model = _mid if _mid.startswith("openai/") else f"openai/{_mid}"

out = r.completion(
    model=model,
    messages=[{"role": "user", "content": 'Return only {"ok":true} as JSON.'}],
    response_format={"type": "json_object"},
)

print(out.choices[0].message.get("content", ""))
