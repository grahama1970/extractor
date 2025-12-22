"""
Unit tests for LLMCallRecord schema and log_llm_call helper.
"""

import pytest
from pydantic import ValidationError

from extractor.pipeline.schemas.llm_call import (
    LLMCallRecord,
    validate_llm_call_record,
)


class TestLLMCallRecord:
    def test_valid_success_record(self):
        record = LLMCallRecord(
            ts="2024-12-22T09:00:00Z",
            stage="07_reflow_section",
            task_kind="reflow",
            route="chutes/text",
            model="deepseek/deepseek-chat",
            section_id="sec_001",
            success=True,
            latency_ms=1500,
            tokens_in=100,
            tokens_out=200,
        )
        assert record.success is True
        assert record.error_class is None

    def test_valid_error_record(self):
        record = LLMCallRecord(
            ts="2024-12-22T09:00:00Z",
            stage="09_section_summarizer",
            task_kind="summarize",
            route="chutes/text",
            model="kimi/k2-chat",
            success=False,
            error_class="parse_fail",
            raw_preview='{"malformed: json',
        )
        assert record.success is False
        assert record.error_class == "parse_fail"

    def test_minimal_record(self):
        record = LLMCallRecord(
            ts="2024-12-22T09:00:00Z",
            stage="03_suspicious_headers",
            task_kind="verify_header",
            route="chutes/vlm",
            model="qwen/qwen-vl",
            success=True,
        )
        assert record.section_id is None
        assert record.tokens_in is None

    def test_route_validation(self):
        # Valid routes
        LLMCallRecord(
            ts="2024-12-22T09:00:00Z",
            stage="test",
            task_kind="test",
            route="chutes/text",
            model="test",
            success=True,
        )
        LLMCallRecord(
            ts="2024-12-22T09:00:00Z",
            stage="test",
            task_kind="test",
            route="chutes/vlm",
            model="test",
            success=True,
        )

        # Invalid route
        with pytest.raises(ValidationError):
            LLMCallRecord(
                ts="2024-12-22T09:00:00Z",
                stage="test",
                task_kind="test",
                route="invalid/route",
                model="test",
                success=True,
            )

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            LLMCallRecord(
                ts="2024-12-22T09:00:00Z",
                stage="test",
                task_kind="test",
                route="chutes/text",
                model="test",
                success=True,
                unknown_field="value",
            )

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            LLMCallRecord(
                ts="2024-12-22T09:00:00Z",
                stage="test",
                # missing task_kind, route, model, success
            )


class TestValidateLLMCallRecord:
    def test_valid_returns_record(self):
        data = {
            "ts": "2024-12-22T09:00:00Z",
            "stage": "07_reflow_section",
            "task_kind": "reflow",
            "route": "chutes/text",
            "model": "test",
            "success": True,
        }
        record, error = validate_llm_call_record(data)
        assert record is not None
        assert error is None

    def test_invalid_returns_error(self):
        data = {"stage": "test"}  # Missing required fields
        record, error = validate_llm_call_record(data)
        assert record is None
        assert error is not None


class TestModelDumpExcludeNone:
    def test_exclude_none_compact(self):
        record = LLMCallRecord(
            ts="2024-12-22T09:00:00Z",
            stage="07_reflow_section",
            task_kind="reflow",
            route="chutes/text",
            model="test",
            success=True,
        )
        dumped = record.model_dump(exclude_none=True)
        assert "section_id" not in dumped
        assert "error_class" not in dumped
        assert "tokens_in" not in dumped
        assert dumped["success"] is True
