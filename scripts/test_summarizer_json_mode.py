#!/usr/bin/env python3
"""
Quick, isolated test for JSON-mode summarization outside the pipeline stage.

Usage examples:
  . .venv/bin/activate && \
  python scripts/test_summarizer_json_mode.py \
      --sections data/results/pipeline/07_reflow_section/json_output/07_reflowed.json \
      --index 0 --strict-json --model openai/gpt-5-mini

  . .venv/bin/activate && \
  python scripts/test_summarizer_json_mode.py \
      --sections data/results/pipeline/07_reflow_section/json_output/07_reflowed.json \
      --index 0 --strict-json --model openai/gpt-5

This mirrors the core of Stage 09's summarize_section prompt but runs stand‑alone.
"""
import os
import json
import asyncio
import argparse
from textwrap import dedent

try:
    import litellm  # type: ignore
except Exception:
    print("SKIP: litellm not installed; test_summarizer_json_mode skipped.")
    raise SystemExit(0)
from extractor.pipeline.utils.litellm_response_utils import extract_content

try:
    from extractor.pipeline.utils.json_utils import clean_json_string
except Exception:
    # Fallback: simple loader
    def clean_json_string(content, return_dict=False):
        try:
            obj = json.loads(content)
            return obj if return_dict else content
        except Exception:
            return {} if return_dict else content


async def test_summarize(section: dict, *, model: str, strict_json: bool) -> dict:
    base_text = (
        section.get("reflowed_text")
        or section.get("merged_text")
        or section.get("raw_text")
        or ""
    )
    prompt = dedent(f"""
        Summarize the following document section in 2–4 sentences and list 3–7 key concepts.

        Section title: {section.get('title','Untitled')}
        Level: {section.get('level',0)}
        Text:
        {base_text}

        Return strictly JSON:
        {{
          "summary": "concise summary",
          "key_concepts": ["concept1", "concept2", "..."]
        }}
    """).strip()

    system_json_guard = (
        "You output ONLY well-formed JSON objects. No prose, markdown, or extra text. "
        "Use double-quoted keys/strings and no trailing commas."
    )
    temp = 1.0 if "gpt-5" in (model or "").lower() else 0.3
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_json_guard},
            {"role": "user", "content": prompt},
        ],
        temperature=temp,
        timeout=120,
        max_tokens=700,
    )
    if strict_json:
        kwargs["response_format"] = {"type": "json_object"}

    resp = await litellm.acompletion(**kwargs)
    # Normalize content across providers
    content = extract_content(resp)

    result = clean_json_string(content, return_dict=True)
    ok = isinstance(result, dict) and "summary" in result
    return {
        "ok": ok,
        "raw_snippet": (content or "")[:180],
        "result": result if isinstance(result, dict) else {},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", required=False, help="Path to 07_reflowed.json (optional)")
    ap.add_argument("--index", type=int, default=0, help="Section index in reflowed_sections")
    ap.add_argument("--model", default=os.getenv("LITELLM_MODEL", "openai/gpt-5-mini"))
    ap.add_argument("--strict-json", action="store_true")
    args = ap.parse_args()

    # Build a minimal section if file not provided
    if args.sections and os.path.exists(args.sections):
        data = json.load(open(args.sections))
        sections = data.get("reflowed_sections") or data.get("sections") or []
        if not sections:
            raise SystemExit("No sections found in provided JSON")
        section = sections[args.index]
    else:
        section = {
            "id": "test_section_0",
            "title": "Sample Section",
            "level": 1,
            "reflowed_text": (
                "BHT is implemented as a memory composed of configuration parameter entries. "
                "When a branch instruction is resolved, status is stored and used for prediction."
            ),
        }

    out = asyncio.run(test_summarize(section, model=args.model, strict_json=args.strict_json))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
