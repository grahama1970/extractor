Yes, although this script is much smaller (\~450 lines) than the massive Stage 07 script, it definitely needs refactoring.

**Why?**

1.  **Duplicate Code:** The helper function `_choice_content` is defined **twice** (lines 35 and 47).
2.  **Logic Coupling:** The "Rolling Window" orchestration (managing indexes, semaphores, and checkpoints) is mixed with the low-level "Prompt & Retry" logic.
3.  **Testability:** It is currently very hard to unit test the prompt formatting logic without mocking the entire AsyncIO/Semaphore machinery.

I recommend creating `extractor/pipeline/utils/summarizer/`.

### Recommended Directory Structure

```text
extractor/pipeline/
├── steps/
│   └── 09_section_summarizer.py   <-- CLI & Configuration only
└── utils/
    └── summarizer/
        ├── __init__.py
        ├── generation.py          <-- LLM calls, prompts, retry logic, direct fallback
        └── batching.py            <-- The rolling window & checkpoint orchestration
```

---

### 1\. `generation.py` (The Worker)

Isolate the act of summarizing _one thing_ (a section or a checkpoint) from the logic of managing _many things_.

- **Move:** `_choice_content` (Remove the duplicate\!).
- **Move:** `_direct_scillm_summary_call`.
- **Move:** `summarize_section`
  - _Refactor:_ Clean up the Prompt Construction logic inside this function.
- **Move:** `create_checkpoint_summary`.

### 2\. `batching.py` (The Manager)

Isolate the complex state machine that tracks "previous summaries" and decides when to trigger a checkpoint.

- **Move:** `batch_summarize_sections_rolling`.
  - _Update:_ Make it import `summarize_section` and `create_checkpoint_summary` from `generation.py`.

### The New `09_section_summarizer.py`

The main file becomes a clean entry point:

```python
import extractor.pipeline.utils.summarizer.batching as summary_batch

def _cmd_run(input_json, ...):
    # ... Setup ...

    # One clean call to the logic
    summaries = asyncio.run(
        summary_batch.batch_summarize_sections_rolling(
            sections=sections,
            max_concurrent=max_concurrent,
            window_size=window_size,
            ...
        )
    )

    # ... Save results ...
```

### Next Step

Would you like me to generate **`generation.py`**? This will clean up the prompt formatting and fix the duplicate function definition immediately.

Here is the code for **`extractor/pipeline/utils/summarizer/generation.py`**.

This module isolates the "Worker" logic: generating a prompt, calling the LLM (with fallback), parsing the JSON, and handling the specific retry logic for summaries and checkpoints. It eliminates the duplicate helper functions found in the original script.

### `extractor/pipeline/utils/summarizer/generation.py`

```python
import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from textwrap import dedent
from pathlib import Path

from loguru import logger
from extractor.pipeline.utils.json_utils import clean_json_string, restrict_top_level_keys
from extractor.pipeline.utils.json_mode import JSON_SYSTEM_GUARD
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.model_select import get_text_model
from extractor.pipeline.utils.prompt_loader import load_prompt

# Load prompts once at module level
PROMPT = load_prompt("09_section_summarizer")
STEP_NAME = "09_section_summarizer"


def _choice_content(resp: Any) -> Optional[str]:
    """Extract content from an OpenAI-compatible response object or dict."""
    try:
        choices = getattr(resp, "choices", None)
        if not choices and isinstance(resp, dict):
            choices = resp.get("choices")
        if not choices:
            return None
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
        else:
            message = getattr(first, "message", None)

        if not message:
            return None

        if isinstance(message, dict):
            return message.get("content")
        return getattr(message, "content", None)
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': 'generation.choice_content'})
        raise


async def _direct_scillm_summary_call(
    messages: List[Dict[str, Any]],
    *,
    response_format: Optional[Dict[str, Any]] = None,
    timeout: int,
) -> Optional[str]:
    """Fallback: Direct call to SciLLM client if Router returns empty/null."""
    try:
        from scillm import acompletion as _sc_acompletion  # type: ignore
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': 'generation.import_scillm'})
        raise

    try:
        resp = await _sc_acompletion(
            model=os.environ.get("CHUTES_TEXT_MODEL", ""),
            api_base=os.environ.get("CHUTES_API_BASE", ""),
            api_key=os.environ.get("CHUTES_API_KEY", ""),
            custom_llm_provider="openai_like",
            messages=messages,
            response_format=response_format or {"type": "json_object"},
            temperature=0.0,
            timeout=timeout,
        )
        return _choice_content(resp)
    except Exception as exc:
        # Don't re-raise here, just log warning and return None to let caller handle failure
        logger.warning(f"stage09.direct_scillm_retry_failed error={exc}")
        return None


async def summarize_section(
    section: Dict[str, Any],
    semaphore: asyncio.Semaphore,
    previous_summaries: Optional[List[Dict[str, Any]]] = None,
    window_size: int = 3,
    strict_json: bool = True,
    request_timeout: int = 120,
    timings_lock: Optional[asyncio.Lock] = None,
    timings_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Generate a summary for a single section using SciLLM (Router), with optional rolling context.
    """
    prev = previous_summaries or []
    async with semaphore:
        # Format Context
        prev_text = "\n".join(
            f"- {p.get('section_title', 'Untitled')}: {p.get('summary_data',{}).get('summary','')}"
            for p in prev
            if p.get("success")
        )
        base_text = (
            section.get("reflowed_text")
            or section.get("merged_text")
            or section.get("raw_text")
            or ""
        )

        prompt = PROMPT["user"].format(
            previous_summaries=prev_text or "(none)",
            section_title=section.get("title", "Untitled"),
            section_level=section.get("level", 0),
            section_text=base_text,
        )

        system_json_guard = PROMPT["system"]
        model_name = get_text_model()
        is_gpt5 = "gpt-5" in (model_name or "").lower()
        router = get_text_router()

        t0 = asyncio.get_event_loop().time()
        error: Optional[str] = None
        served_model: Optional[str] = None
        usage: Dict[str, Any] = {}
        content_preview: Optional[str] = None

        try:
            messages_payload = [
                {"role": "system", "content": system_json_guard},
                {"role": "user", "content": prompt},
            ]

            resp = await router.acompletion(
                model="chutes/text",
                messages=messages_payload,
                response_format={"type": "json_object"} if strict_json else None,
                temperature=0.0 if is_gpt5 else 0.0,
                timeout=request_timeout,
            )
            served_model = getattr(resp, "model", None) or getattr(resp, "id", None) or "chutes/text"
            content = _choice_content(resp)

            # Fallback if empty content
            if not (isinstance(content, str) and content.strip()):
                logger.warning(
                    "stage09.router_empty_content section_id=%s model=%s -- retrying via direct SciLLM",
                    section.get("id"),
                    served_model,
                )
                resp_direct = await _direct_scillm_summary_call(
                    messages_payload,
                    response_format={"type": "json_object"} if strict_json else None,
                    timeout=request_timeout,
                )
                content = resp_direct if resp_direct else ""

            content_preview = str(content)[:400] if content is not None else None

            # Track Usage
            usage_obj = getattr(resp, "usage", None) or {}
            if isinstance(usage_obj, dict):
                usage = usage_obj
            else:
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                    "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                    "total_tokens": getattr(usage_obj, "total_tokens", None),
                }

            # Parse & Clean
            result = clean_json_string(content, return_dict=True)
            if isinstance(result, dict):
                result = restrict_top_level_keys(result, allowed={"summary", "key_concepts"})

            # Validation & Defaulting
            if isinstance(result, dict):
                if not result.get("summary"):
                    fallback = (base_text or "").strip()
                    if len(fallback) > 240:
                        fallback = f"{fallback[:120]} … {fallback[-120:]}"
                    result["summary"] = fallback or "(no content)"
                if not result.get("key_concepts"):
                    result["key_concepts"] = []

            if strict_json and (
                not isinstance(result, dict)
                or "summary" not in result
                or not isinstance(result.get("key_concepts", []), list)
            ):
                raise ValueError(
                    f"stage09.invalid_response section_id={section.get('id')} content_preview={content_preview}"
                )

            return {
                "section_id": section.get("id"),
                "section_title": section.get("title"),
                "section_level": section.get("level", 0),
                "summary_data": {
                    "summary": result.get("summary", ""),
                    "key_concepts": result.get("key_concepts", []),
                },
                "success": True,
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "stage09.summarize_section_error section_id=%s title=%s error=%s",
                section.get("id"),
                section.get("title"),
                error,
            )
            return {
                "section_id": section.get("id"),
                "section_title": section.get("title"),
                "section_level": section.get("level", 0),
                "summary_data": {
                    "summary": "",
                    "key_concepts": [],
                },
                "success": False,
            }
        finally:
            # Write timing log
            if timings_path is not None and timings_lock is not None:
                t1 = asyncio.get_event_loop().time()
                latency_ms = int((t1 - t0) * 1000)
                line = {
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "type": "section",
                    "section_id": section.get("id"),
                    "section_title": section.get("title"),
                    "served_model": served_model,
                    "usage": usage,
                    "latency_ms": latency_ms,
                    "outcome": "success" if error is None else "error",
                    "error": error,
                    "raw_preview": content_preview if error is not None else None,
                }
                try:
                    async with timings_lock:
                        with timings_path.open("a", encoding="utf-8") as f:
                            f.write(json.dumps(line, ensure_ascii=False) + "\n")
                except Exception as exc:
                    # Don't crash the pipeline just because logging failed
                    logger.warning(f"stage09.timings_log_error: {exc}")


async def create_checkpoint_summary(
    summaries: List[Dict[str, Any]],
    checkpoint_name: str = "Chapter",
    request_timeout: int = 120,
    timings_lock: Optional[asyncio.Lock] = None,
    timings_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Create a high-level summary of multiple sections."""
    if not summaries:
        return None

    successful_summaries = [s for s in summaries if s.get("success")]
    if not successful_summaries:
        return None

    summary_texts: List[str] = []
    for s in successful_summaries:
        try:
            if s.get("summary_data"):
                summary_texts.append(f"- {s['section_title']}: {s['summary_data']['summary']}")
        except Exception:
            continue

    prompt = dedent(
        f"""
    Create a high-level summary of this chapter/part of the document.

    Section summaries:
    {chr(10).join(summary_texts)}

    Provide a JSON response with:
    {{
        "checkpoint_summary": "A comprehensive 3-4 sentence summary of this entire chunk",
        "major_themes": ["List", "of", "major", "themes"],
        "key_concepts": ["Most", "important", "concepts", "from", "all", "sections"],
        "chapter_purpose": "The overall purpose of this chapter in the document"
    }}
    """
    ).strip()

    model_name = (os.getenv("CHUTES_TEXT_MODEL") or get_text_model()).strip()
    if not model_name:
        logger.error("checkpoint_summary.no_model_configured")
        return None

    async def _call_once_async():
        router = get_text_router()
        return await router.acompletion(
            model="chutes/text",
            messages=[
                {"role": "system", "content": JSON_SYSTEM_GUARD},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            timeout=request_timeout,
        )

    # Retry logic (3 attempts)
    attempts = 0
    served_model: Optional[str] = None
    usage: Dict[str, Any] = {}
    start_time = asyncio.get_event_loop().time()

    while True:
        try:
            resp = await _call_once_async()
            break
        except Exception as e:
            attempts += 1
            msg = str(e)
            if attempts >= 3:
                logger.error(f"Failed to create checkpoint summary (attempts={attempts}): {e}")
                # Log capacity skips
                outcome = "error"
                if any(t in msg for t in ("429", "Too Many Requests", "capacity")):
                    outcome = "skipped_capacity"
                elif ("401" in msg) or ("Unauthorized" in msg):
                    outcome = "skipped_auth"

                if timings_path is not None and timings_lock is not None:
                    try:
                        async with timings_lock:
                            with timings_path.open("a", encoding="utf-8") as f:
                                f.write(json.dumps({
                                    "ts": datetime.utcnow().isoformat() + "Z",
                                    "type": "checkpoint",
                                    "name": checkpoint_name,
                                    "latency_ms": int((asyncio.get_event_loop().time() - start_time) * 1000),
                                    "outcome": outcome,
                                    "error": msg,
                                }) + "\n")
                    except Exception:
                        pass
                return {
                    "type": "checkpoint",
                    "name": checkpoint_name,
                    "sections_covered": len(successful_summaries),
                    "data": {"checkpoint_skipped": outcome},
                    "skipped": True,
                    "reason": outcome,
                }

            # Backoff
            if any(t in msg for t in ("429", "Too Many Requests", "capacity")):
                await asyncio.sleep(0.5)
                continue
            if ("401" in msg) or ("Unauthorized" in msg):
                await asyncio.sleep(0.25)
                continue
            logger.error(f"Failed to create checkpoint summary: {e}")
            return None

    content = _choice_content(resp)
    if not content:
        logger.error("checkpoint_summary.empty_content")
        return None

    try:
        served_model = getattr(resp, "model", None) or getattr(resp, "id", None) or "chutes/text"
        usage_obj = getattr(resp, "usage", None) or {}
        if isinstance(usage_obj, dict):
            usage = usage_obj
        else:
            usage = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                "total_tokens": getattr(usage_obj, "total_tokens", None),
            }
        result = clean_json_string(content, return_dict=True)
    except Exception as e:
        logger.error(f"checkpoint_summary.json_clean_failed: {e}")
        return None

    # Log success timing
    if timings_path is not None and timings_lock is not None:
        try:
            async with timings_lock:
                with timings_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "ts": datetime.utcnow().isoformat() + "Z",
                        "type": "checkpoint",
                        "name": checkpoint_name,
                        "served_model": served_model,
                        "usage": usage,
                        "latency_ms": int((asyncio.get_event_loop().time() - start_time) * 1000),
                        "outcome": "success",
                        "error": None,
                    }) + "\n")
        except Exception:
            pass

    return {
        "type": "checkpoint",
        "name": checkpoint_name,
        "sections_covered": len(successful_summaries),
        "data": result,
    }
```
