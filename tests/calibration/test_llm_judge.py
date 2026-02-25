"""Tests for Stage 3 LLM judge.

Task 10: Implement Stage 3 LLM judge for edge cases.
"""

import pytest

from extractor.pipeline.calibration import (
    PatternLearner,
    LLMJudgeResult,
)


class TestShouldUseLLMJudge:
    """Test LLM judge threshold checking."""

    def test_low_confidence_triggers_judge(self):
        """Test low confidence triggers LLM judge."""
        learner = PatternLearner()
        assert learner.should_use_llm_judge(0.5) is True
        assert learner.should_use_llm_judge(0.6) is True

    def test_high_confidence_skips_judge(self):
        """Test high confidence skips LLM judge."""
        learner = PatternLearner()
        assert learner.should_use_llm_judge(0.8) is False
        assert learner.should_use_llm_judge(0.9) is False

    def test_custom_threshold(self):
        """Test custom threshold."""
        learner = PatternLearner()
        assert learner.should_use_llm_judge(0.5, threshold=0.5) is False
        assert learner.should_use_llm_judge(0.49, threshold=0.5) is True


class TestFormatLLMJudgeResult:
    """Test LLM judge result formatting."""

    def test_format_includes_both_analyses(self):
        """Test format shows both agent and LLM analysis."""
        learner = PatternLearner()
        result = LLMJudgeResult(
            verdict="figure",
            confidence=0.85,
            reasoning="Contains image data and figure caption",
        )

        formatted = learner.format_llm_judge_result(
            agent_type="table",
            agent_reasoning="Grid-like structure detected",
            llm_result=result,
        )

        assert "Agent Analysis" in formatted
        assert "LLM Judge Analysis" in formatted
        assert "table" in formatted
        assert "figure" in formatted
        assert "Grid-like" in formatted
        assert "figure caption" in formatted
        assert "What's your verdict?" in formatted

    def test_format_shows_confidence(self):
        """Test format shows confidence percentage."""
        learner = PatternLearner()
        result = LLMJudgeResult(
            verdict="header",
            confidence=0.92,
            reasoning="Large bold text",
        )

        formatted = learner.format_llm_judge_result(
            agent_type="header",
            agent_reasoning="Bold text detected",
            llm_result=result,
        )

        assert "92%" in formatted


class TestLLMJudgeResult:
    """Test LLMJudgeResult dataclass."""

    def test_result_has_all_fields(self):
        """Test result has required fields."""
        result = LLMJudgeResult(
            verdict="header",
            confidence=0.9,
            reasoning="Test reasoning",
            raw_response='{"verdict": "header"}',
        )

        assert result.verdict == "header"
        assert result.confidence == 0.9
        assert result.reasoning == "Test reasoning"
        assert result.raw_response is not None


@pytest.mark.asyncio
class TestStage3LLMJudge:
    """Test Stage 3 LLM judge async method."""

    async def test_fallback_when_scillm_unavailable(self):
        """Test graceful fallback when scillm not installed."""
        learner = PatternLearner()

        # This should not raise, just return fallback result
        result = await learner.stage3_llm_judge(
            element_text="Test text",
            element_type="header",
            confidence=0.5,
            reasoning="Test reasoning",
        )

        assert isinstance(result, LLMJudgeResult)
        # Should return original type when LLM unavailable
        assert result.verdict == "header"
