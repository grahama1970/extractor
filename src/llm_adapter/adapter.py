from __future__ import annotations

import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

# SciLLM-first: keep litellm optional; prefer scillm
try:
    import scillm as litellm  # type: ignore
except Exception:  # pragma: no cover
    litellm = None  # type: ignore
from loguru import logger

from extractor.pipeline.utils.litellm_response_utils import extract_content
from extractor.pipeline.utils.metrics_logger import log_metric
from extractor.core.services.utils.json_utils import clean_json_string
from src.contracts import HeaderVerdict, ReflowedSection, SectionSummary


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


class LLMAdapter:
    """
    A narrow adapter with strict contracts and per-call artifact dumps.

    - Forces response_format={"type":"json_object"} (provider permitting)
    - Applies strict timeouts + minimal retries via LiteLLM (respecting env)
    - Validates JSON against Pydantic contracts; rejects extra/missing keys
    - Dumps request/response bundles under logs/{stage}/{id}/
    """

    def __init__(self, logs_root: Optional[Path] = None) -> None:
        self.logs_root = logs_root or Path("logs")

    # ------------------------ Public entrypoints ------------------------ #
    async def verify_header(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        prompt_version: str,
        doc_id: str,
        section_id: str,
        request_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> HeaderVerdict:
        metadata = {
            "doc_id": doc_id,
            "section_id": section_id,
            "prompt_version": prompt_version,
        }
        metadata.update(self._prompt_stats(messages))
        payload = await self._json_completion(
            stage="03_verify_header",
            request_id=request_id or f"{doc_id}-{section_id}",
            model=model,
            messages=messages,
            timeout=timeout,
            metadata=metadata,
        )
        data = self._parse_json(payload)
        data.update(
            {
                "doc_id": doc_id,
                "section_id": section_id,
                "prompt_version": prompt_version,
                "model_id": model,
            }
        )
        return HeaderVerdict.model_validate(data)

    async def reflow_section(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        prompt_version: str,
        doc_id: str,
        section_id: str,
        request_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ReflowedSection:
        metadata = {
            "doc_id": doc_id,
            "section_id": section_id,
            "prompt_version": prompt_version,
        }
        metadata.update(self._prompt_stats(messages))
        payload = await self._json_completion(
            stage="07_reflow_section",
            request_id=request_id or f"{doc_id}-{section_id}",
            model=model,
            messages=messages,
            timeout=timeout,
            metadata=metadata,
        )
        data = self._parse_json(payload)
        data.update(
            {
                "doc_id": doc_id,
                "section_id": section_id,
                "prompt_version": prompt_version,
                "model_id": model,
            }
        )
        return ReflowedSection.model_validate(data)

    async def summarize_section(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        prompt_version: str,
        doc_id: str,
        section_id: str,
        request_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> SectionSummary:
        metadata = {
            "doc_id": doc_id,
            "section_id": section_id,
            "prompt_version": prompt_version,
        }
        metadata.update(self._prompt_stats(messages))
        payload = await self._json_completion(
            stage="09_section_summary",
            request_id=request_id or f"{doc_id}-{section_id}",
            model=model,
            messages=messages,
            timeout=timeout,
            metadata=metadata,
        )
        data = self._parse_json(payload)
        data.update(
            {
                "doc_id": doc_id,
                "section_id": section_id,
                "prompt_version": prompt_version,
                "model_id": model,
            }
        )
        return SectionSummary.model_validate(data)

    # ------------------------ Internal helpers ------------------------ #
    async def _json_completion(
        self,
        *,
        stage: str,
        request_id: str,
        model: str,
        messages: List[Dict[str, Any]],
        timeout: Optional[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        req_dir = self.logs_root / stage / request_id
        _ensure_dir(req_dir)

        # Build kwargs with JSON enforcement
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
        }
        # Enforce JSON mode when possible per scratch.md guidance
        kwargs["response_format"] = {"type": "json_object"}
        if timeout is not None:
            kwargs["timeout"] = timeout

        # Dump request
        try:
            (req_dir / "req.json").write_text(json.dumps({"kwargs": kwargs}, indent=2))
        except Exception:
            logger.debug("Failed to write req.json")

        start_monotonic = asyncio.get_event_loop().time()
        try:
            # Prefer SciLLM; fall back if unavailable
            if hasattr(litellm, "acompletion"):
                resp = await litellm.acompletion(**kwargs)  # type: ignore[attr-defined]
            else:
                raise RuntimeError("SciLLM/LiteLLM client unavailable for adapter.")

            # Normalize JSON content: accept dict or string for response_format={"type":"json_object"}
            raw_text = extract_content(resp) or ""
            json_obj = None
            try:
                # If extract_content produced empty string, try direct access
                if not raw_text:
                    ch = resp.get("choices") if isinstance(resp, dict) else getattr(resp, "choices", None)
                    if ch:
                        msg = ch[0].get("message") if isinstance(ch[0], dict) else getattr(ch[0], "message", None)
                        if msg is not None:
                            content_val = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
                            if isinstance(content_val, dict):
                                json_obj = content_val
                                import json as _json

                                raw_text = _json.dumps(content_val, ensure_ascii=False)
                            elif isinstance(content_val, str):
                                raw_text = content_val
                # If we still have text, attempt to parse into json_obj for downstream strict typing
                if json_obj is None and raw_text:
                    import json as _json

                    try:
                        parsed = _json.loads(raw_text)
                        if isinstance(parsed, dict):
                            json_obj = parsed
                    except Exception:
                        json_obj = None
            except Exception:
                # Non-fatal; downstream _parse_json will repair when possible
                json_obj = None

            (req_dir / "raw.txt").write_text(raw_text)
            usage_obj = getattr(resp, "usage", None)
            used = getattr(usage_obj, "total_tokens", None) if usage_obj else None
            cost = None
            duration_ms = int((asyncio.get_event_loop().time() - start_monotonic) * 1000)
            metadata_payload = dict(metadata or {})
            log_metric(
                stage,
                {
                    "request_id": request_id,
                    "model": model,
                    "success": True,
                    "duration_ms": duration_ms,
                    "total_tokens": used,
                    "estimated_cost": cost,
                    "metadata": metadata_payload,
                },
            )
            verdict = {
                "valid_json": bool(raw_text.strip()) or isinstance(json_obj, dict),
                "total_tokens": used,
                "cost_usd": cost,
                "duration_ms": duration_ms,
            }
            (req_dir / "verdict.json").write_text(json.dumps(verdict, indent=2))
            return {"text": raw_text, "json_obj": json_obj, "usage": used, "cost": cost}
        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_monotonic) * 1000)
            metadata_payload = dict(metadata or {})
            log_metric(
                stage,
                {
                    "request_id": request_id,
                    "model": model,
                    "success": False,
                    "duration_ms": duration_ms,
                    "error": str(e),
                    "metadata": metadata_payload,
                },
            )
            err = {"error": str(e), "duration_ms": duration_ms}
            (req_dir / "verdict.json").write_text(json.dumps(err, indent=2))
            raise

    @staticmethod
    def _prompt_stats(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Collect lightweight prompt statistics for metrics metadata."""

        skip_keys = {"type", "role", "mime_type"}

        def _count(value: Any) -> int:
            if isinstance(value, str):
                return len(value)
            if isinstance(value, dict):
                total = 0
                for key, inner in value.items():
                    if key in skip_keys:
                        continue
                    total += _count(inner)
                return total
            if isinstance(value, list):
                return sum(_count(item) for item in value)
            return 0

        total_chars = 0
        for message in messages or []:
            content = message.get("content") if isinstance(message, dict) else None
            total_chars += _count(content)

        return {
            "prompt_chars": total_chars,
            "prompt_messages": len(messages) if messages else 0,
        }

    @staticmethod
    def _parse_json(payload: Dict[str, Any]) -> Dict[str, Any]:
        # Prefer normalized json_obj when present (already a dict)
        obj = payload.get("json_obj")
        if isinstance(obj, dict):
            return obj
        text = payload.get("text") or ""
        cleaned = clean_json_string(text, return_dict=True)
        if isinstance(cleaned, dict):
            return cleaned
        # As a fallback, try json.loads
        try:
            import json as _json

            obj = _json.loads(str(cleaned))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        raise ValueError("Adapter received non-dict JSON payload")


__all__ = ["LLMAdapter"]
