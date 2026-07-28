"""
Response utilities shared across adapters/tests.

Functions here normalize provider responses and optionally augment JSON with
usage/cost metadata reported by providers (when available via LiteLLM).

Design:
- Keep JSON cleaning/parsing centralized by reusing json_utils.clean_json_string
- Keep response content extraction tolerant of both dict (OpenAI-style) and
  ModelResponse-like objects, including content lists (multimodal parts)
- Provide normalize_json_content() to accept dict-or-string JSON mode content
  and return a consistent (raw_text, json_obj) pair.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from extractor.pipeline.utils.json_utils import clean_json_string
from extractor.pipeline.utils.image_helpers import extract_images
from extractor.pipeline.utils.reliability import log_stage_error
from typing import Any as _Any, Dict as _Dict, List as _List, Optional as _Optional, Tuple as _Tuple
import json as _json


def extract_content(resp: Any) -> str:
    """Extract a text content string from various response shapes.

    Supports:
    - OpenAI-style dicts: { choices: [ { message: { content: ... } } ] }
    - ModelResponse-like objects with .choices[0].message.content or .text
    - content as a list of parts → concatenates relevant text fields
    - Fallback to response.output_text if available
    """
    # OpenAI-style dict
    if isinstance(resp, dict) and "choices" in resp:
        try:
            ch = resp.get("choices") or []
            if ch:
                msg = ch[0].get("message") or {}
                content = msg.get("content")
                if isinstance(content, list):
                    parts = []
                    for p in content:
                        if isinstance(p, dict):
                            t = p.get("text") or p.get("content") or p.get("input_text")
                            if isinstance(t, str) and t.strip():
                                parts.append(t.strip())
                    if parts:
                        return "\n".join(parts)
                if content is not None:
                    # If providers return a JSON object in content (JSON mode), serialize to string
                    if isinstance(content, dict):
                        try:
                            return _json.dumps(content, ensure_ascii=False)
                        except Exception:
                            return ""
                    return str(content)
                txt = ch[0].get("text")
                if isinstance(txt, str):
                    return txt
            # Fallbacks sometimes exposed by adapters
            ot = resp.get("output_text")
            if isinstance(ot, str) and ot.strip():
                return ot
        except Exception as exc:
            log_stage_error("response_utils.extract_content", exc, {"context": "openai_dict"})

    # ModelResponse-like object
    ch_obj = getattr(resp, "choices", None)
    if ch_obj:
        try:
            ch0 = ch_obj[0]
            msg = getattr(ch0, "message", None)
            if msg is not None and getattr(msg, "content", None) is not None:
                content = getattr(msg, "content")
                if isinstance(content, list):
                    parts = []
                    for p in content:
                        if isinstance(p, dict):
                            t = p.get("text") or p.get("content") or p.get("input_text")
                            if isinstance(t, str) and t.strip():
                                parts.append(t.strip())
                    if parts:
                        return "\n".join(parts)
                if isinstance(content, dict):
                    try:
                        return _json.dumps(content, ensure_ascii=False)
                    except Exception:
                        return ""
                return str(content)
            txt = getattr(ch0, "text", None)
            if isinstance(txt, str):
                return txt
            ot = getattr(resp, "output_text", None)
            if isinstance(ot, str) and ot.strip():
                return ot
        except Exception as exc:
            log_stage_error("response_utils.extract_content", exc, {"context": "model_response"})

    # Top-level fallbacks for dict/objects that put text elsewhere
    if isinstance(resp, dict):
        if isinstance(resp.get("content"), str):
            return str(resp.get("content"))
        if isinstance(resp.get("output_text"), str):
            return str(resp.get("output_text"))

    if isinstance(resp, str):
        return resp
    return ""


def normalize_json_content(resp: Any) -> _Tuple[str, _Optional[_Dict[str, _Any]]]:
    """
    Normalize JSON mode responses into (raw_text, json_obj or None).

    - Handles dict-or-string in message.content.
    - Attempts to json.loads string content; if that fails, tries clean_json_string.
    - Returns ("", None) if not available/parseable.
    """
    raw_text = extract_content(resp) or ""
    json_obj: _Optional[_Dict[str, _Any]] = None
    try:
        if raw_text:
            try:
                parsed = _json.loads(raw_text)
                if isinstance(parsed, dict):
                    json_obj = parsed
            except Exception as exc:
                log_stage_error(
                    "response_utils.normalize_json_content", exc, {"context": "loads_raw_text"}
                )
                repaired = clean_json_string(raw_text, return_dict=True)
                if isinstance(repaired, dict):
                    json_obj = repaired
        else:
            # Try direct access if extract_content couldn't resolve
            choices = (
                getattr(resp, "choices", None)
                if not isinstance(resp, dict)
                else resp.get("choices")
            )
            if choices:
                first = choices[0]
                message = (
                    getattr(first, "message", None)
                    if not isinstance(first, dict)
                    else first.get("message")
                )
                if message is not None:
                    content = (
                        getattr(message, "content", None)
                        if not isinstance(message, dict)
                        else message.get("content")
                    )
                    if isinstance(content, dict):
                        json_obj = content
                        raw_text = _json.dumps(content, ensure_ascii=False)
                    elif isinstance(content, str):
                        raw_text = content
                        try:
                            parsed = _json.loads(raw_text)
                            if isinstance(parsed, dict):
                                json_obj = parsed
                        except Exception as exc:
                            log_stage_error(
                                "response_utils.normalize_json_content",
                                exc,
                                {"context": "loads_content_str"},
                            )
                            repaired = clean_json_string(raw_text, return_dict=True)
                            if isinstance(repaired, dict):
                                json_obj = repaired
    except Exception as exc:
        log_stage_error("response_utils.normalize_json_content", exc, {"context": "normalize"})
        json_obj = None
    return raw_text, json_obj


def to_messages_and_model(
    item: _Any,
    default_model: str,
    *,
    response_format: _Optional[str] = None,
    request_timeout: _Optional[float] = None,
    image_cache_dir: _Optional[str] = None,
) -> _Tuple[str, _List[_Dict[str, _Any]], _Dict[str, _Any]]:
    """Normalize input → (model, OpenAI messages, extra kwargs).

    Forms:
    - str: parse images from text; build a single user message with text + image_url parts (url kept as-is)
    - shorthand dict: {text?, image?, model?}
    - full dict with 'messages': preserve messages; remaining keys become per-request kwargs
    Note: image URL conversion to data: URIs occurs later in the call path.
    """
    extra_kwargs: _Dict[str, _Any] = {}

    # Full dict with manual messages
    if isinstance(item, dict) and "messages" in item:
        model = item.get("model", default_model)
        messages = item["messages"]
        for k, v in item.items():
            if k not in {"model", "messages"}:
                extra_kwargs[k] = v
        if response_format:
            extra_kwargs.setdefault("response_format", {"type": response_format})
        if request_timeout is not None:
            extra_kwargs.setdefault("timeout", request_timeout)
        return model, messages, extra_kwargs

    # Shorthand dict
    if isinstance(item, dict):
        text = str(item.get("text", ""))
        images = [str(item["image"])] if "image" in item else []
        model = item.get("model", default_model)
    else:
        images, text = extract_images(str(item))
        model = default_model

    # Build multimodal parts (text + image references); URL conversion happens later
    content_parts: _List[_Dict[str, _Any]] = []
    if text:
        content_parts.append({"type": "text", "text": text})
    for img in images:
        content_parts.append({"type": "image_url", "image_url": {"url": img}})

    messages = [{"role": "user", "content": content_parts or [{"type": "text", "text": ""}]}]
    if response_format:
        extra_kwargs.setdefault("response_format", {"type": response_format})
    if request_timeout is not None:
        extra_kwargs.setdefault("timeout", request_timeout)
    return model, messages, extra_kwargs


def extract_usage_and_cost(resp: Any) -> Dict[str, Any]:
    """Gather token usage and provider-reported cost/cache metadata if present."""
    metadata: Dict[str, Any] = {}
    usage = getattr(resp, "usage", None)

    token_usage = None
    if usage is not None:
        if isinstance(usage, dict):
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        else:
            token_usage = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
    if token_usage is not None:
        metadata["token_usage"] = token_usage

    hidden = getattr(resp, "_hidden_params", {}) or {}
    if isinstance(hidden, dict) and "response_cost" in hidden:
        metadata["response_cost"] = hidden.get("response_cost")
    if isinstance(hidden, dict) and "cache_hit" in hidden:
        metadata["cache_hit"] = hidden.get("cache_hit")
    # Extra detection for cache flags on alternative response shapes
    try:
        if "cache_hit" not in metadata:
            if isinstance(resp, dict) and isinstance(resp.get("cache_hit"), bool):
                metadata["cache_hit"] = resp.get("cache_hit")
            elif hasattr(resp, "cache_hit"):
                ch = getattr(resp, "cache_hit")
                if isinstance(ch, bool):
                    metadata["cache_hit"] = ch
    except Exception:
        pass
    return metadata


def augment_json_with_cost(text: str, resp: Any, wrap_non_json: bool = False) -> str:
    """Return JSON text augmented with provider metadata, or wrap non‑JSON when requested.

    Behavior:
    - Parse with clean_json_string() to tolerate code fences / noisy text
    - If parsed is a dict:
        * If parsed["metadata"] is a dict → update it
        * If parsed["metadata"] exists but is not a dict → write to parsed["_metadata"] (non‑destructive)
        * Else → set parsed["metadata"] = metadata
    - If parsed is list/primitive and wrap_non_json is True → wrap into {content, metadata}
    - Otherwise return the original text unchanged
    """
    try:
        parsed = clean_json_string(text, return_dict=True)
    except Exception:
        parsed = text

    # If parsing failed, optionally wrap the raw text
    if isinstance(parsed, str):
        if wrap_non_json:
            return json.dumps(
                {"content": text, "metadata": extract_usage_and_cost(resp)}, ensure_ascii=False
            )
        return text

    md = extract_usage_and_cost(resp)
    if isinstance(parsed, dict):
        if "metadata" in parsed:
            if isinstance(parsed.get("metadata"), dict):
                parsed["metadata"].update(md)  # type: ignore[union-attr]
            else:
                # Non‑destructive: write provider metadata under _metadata when a non‑dict metadata exists
                parsed["_metadata"] = {**(parsed.get("_metadata", {}) or {}), **md}
        elif "_metadata" in parsed and isinstance(parsed.get("_metadata"), dict):
            parsed["_metadata"].update(md)  # type: ignore[union-attr]
        else:
            parsed["metadata"] = md
        return json.dumps(parsed, ensure_ascii=False)

    # list or other JSON types; optionally wrap
    if wrap_non_json:
        return json.dumps({"content": parsed, "metadata": md}, ensure_ascii=False)

    return json.dumps(parsed, ensure_ascii=False)


def classify_error(e: Exception) -> Dict[str, Any]:
    """Normalize common provider/transport errors into categories and hints."""
    msg = str(e)
    m = msg.lower()

    def any_in(s: str, needles: list[str]) -> bool:
        """Perform any in operation."""
        return any(n in s for n in needles)

    category = "unknown"
    hint = None

    if any_in(
        m,
        [
            "does not support",
            "unsupported",
            "image input",
            "image_url",
            "no vision",
            "vision not",
            "invalid type for",
            "doesn't support",
        ],
    ):
        category = "vision_unsupported"
        hint = "Switch to a vision-capable model or remove image parts."
    elif any_in(
        m,
        [
            "max token",
            "max_tokens",
            "output token",
            "maximum output",
            "context length",
            "maximum context length",
            "token limit",
            "truncated",
            "insufficient tokens",
            "insufficient output tokens",
            "finish_reason: length",
            "reduce the length of the messages",
        ],
    ):
        category = "token_limit"
        hint = "Increase output tokens/max_tokens or reduce input/context."
    elif any_in(m, ["rate limit", "too many requests", "429"]):
        category = "rate_limit"
        hint = "Lower concurrency or enable retry/backoff."
    elif any_in(m, ["timeout", "timed out", "deadline exceeded"]):
        category = "timeout"
        hint = "Increase timeout or reduce payload size."
    elif any_in(m, ["unauthorized", "invalid api key", "forbidden", "401", "403"]):
        category = "auth_error"
        hint = "Check API key/permissions for the selected provider."
    elif any_in(m, ["service unavailable", "server error", "internal error", "500", "503"]):
        category = "server_error"
        hint = "Provider issue; retry with backoff or change region."
    elif any_in(m, ["connection", "network", "httpx", "ssl"]):
        category = "network_error"
        hint = "Check network connectivity and provider endpoint URL."
    elif any_in(m, ["quota", "insufficient_quota", "billing", "payment required"]):
        category = "quota"
        hint = "Check billing/quota or change the account/region."
    elif any_in(m, ["model not found", "unknown model", "does not exist", "invalid model"]):
        category = "model_not_found"
        hint = "Verify model name or update to a supported model."
    elif any_in(
        m,
        [
            "bad request",
            "invalid request",
            "unrecognized request argument",
            "parameter missing",
            "param required",
            "unsupported parameter",
        ],
    ):
        category = "bad_request"
        hint = "Fix request parameters; check provider API docs."
    elif any_in(
        m,
        [
            "content policy",
            "safety",
            "blocked",
            "harmful",
            "violates",
            "content filter",
            "safetyexception",
            "blocked by safety",
        ],
    ):
        category = "safety_block"
        hint = "Adjust content or safety settings for the provider."
    elif any_in(
        m, ["tools not supported", "function call not allowed", "tool calls are not supported"]
    ):
        category = "tools_unsupported"
        hint = "Remove tools or choose a model that supports tool calls."

    return {
        "type": type(e).__name__,
        "message": msg[:400],
        "category": category,
        **({"hint": hint} if hint else {}),
    }


def format_error(e: Exception, wrap_json: bool = False) -> str:
    """Format error according to wrap_json convention used by litellm_call.

    - When wrap_json is True, returns a JSON object with an `error` field.
    - Otherwise, returns an empty string for compatibility with existing callers.
    """
    if wrap_json:
        return json.dumps({"error": classify_error(e)}, ensure_ascii=False)
    return ""


def format_answer(resp: Any, wrap_json: bool = False) -> str:
    """Format a successful response into a final output string.

    Uses extract_content + augment_json_with_cost, and honors wrap_json behavior
    for non-JSON text.
    """
    answer = extract_content(resp)
    return augment_json_with_cost(answer, resp, wrap_non_json=wrap_json)


def redact_prompt_for_log(prompt: Any) -> Any:
    """Return a safe-to-log version of a prompt (mask secrets)."""
    try:
        from copy import deepcopy

        p = deepcopy(prompt)
        if isinstance(p, dict) and "api_key" in p:
            p["api_key"] = "***"
        return p
    except Exception:
        return prompt


def format_answer_with_logging(
    idx: int,
    resp: Any,
    wrap_json: bool,
    prompt_for_log: Any,
    logger,
) -> str:
    """Compose the final answer (or error), and emit concise logs.

    - Delegates to format_answer/format_error
    - Logs warning for vision-unsupported and other errors with category
    - Logs trimmed prompt and answer preview for info-level observability
    """
    if isinstance(resp, Exception):
        err = classify_error(resp)
        if err.get("category") == "vision_unsupported":
            logger.warning(f"LiteLLM call failed for Q{idx}: {type(resp).__name__}: {resp}")
        final_answer = format_error(resp, wrap_json)
    else:
        try:
            final_answer = format_answer(resp, wrap_json)
        except Exception as e:
            logger.warning(f"Failed to parse response for Q{idx}: {e}")
            final_answer = format_error(e, wrap_json)

    safe_prompt = redact_prompt_for_log(prompt_for_log)
    try:
        logger.info(f"Q{idx}: {str(safe_prompt)[:50]}... -> {final_answer[:100]}...")
    except Exception:
        pass
    return final_answer


async def assemble_stream_text(resp_stream: Any) -> str:
    """Consume an async streaming response and return assembled text.

    Supports both OpenAI-style delta chunks and alt shapes with choices[0].text.
    Also prints chunks to stdout as they arrive, matching existing CLI UX.
    """
    assembled: list[str] = []
    try:
        async for chunk in resp_stream:  # type: ignore
            try:
                delta = chunk["choices"][0]["delta"].get("content")
                if delta:
                    print(delta, end="", flush=True)
                    assembled.append(delta)
                    continue
            except Exception:
                pass
            text = (
                getattr(getattr(chunk, "choices", [None])[0], "text", None)
                if hasattr(chunk, "choices")
                else None
            )
            if isinstance(text, str):
                print(text, end="", flush=True)
                assembled.append(text)
    except Exception:
        # Swallow stream errors to mirror prior tolerant behavior
        pass
    print()
    return "".join(assembled)
