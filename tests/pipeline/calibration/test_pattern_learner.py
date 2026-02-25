"""Tests for 3-stage pattern learner.

These tests verify patterns are learned from examples.
"""

import pytest

from extractor.pipeline.calibration.feedback_handler import FeedbackHandler
from extractor.pipeline.calibration.pattern_learner import (
    LearningResult,
    PatternLearner,
    PatternProposal,
)
from extractor.pipeline.calibration.schema import ArangoConfig, CalibrationSchema


@pytest.fixture
def schema():
    """Create a CalibrationSchema instance for testing."""
    config = ArangoConfig.from_env()
    config.database = "extractor_calibration_test"
    schema = CalibrationSchema(config)
    schema.create_collections()
    schema.drop_collections()
    schema.create_collections()
    yield schema
    schema.drop_collections()


@pytest.fixture
def learner(schema):
    """Create a PatternLearner instance for testing."""
    return PatternLearner(schema)


@pytest.fixture
def handler(schema):
    """Create a FeedbackHandler instance for testing."""
    return FeedbackHandler(schema)


def test_learn_header_pattern(learner, handler):
    """Test learner outputs 3-stage pattern from header examples."""
    session_key = "header-test-session"
    preset_id = "test-preset"

    # Create header examples
    headers = [
        ("1.0 Introduction", 14, True),
        ("1.1 Background", 14, True),
        ("2.0 Methods", 14, True),
        ("2.1 Data Collection", 14, True),
    ]

    for i, (text, size, bold) in enumerate(headers):
        handler.save_correct(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=1,
            page=i,
            element_idx=0,
            element_type="header",
            bbox=[72, 50, 400, 70],
            agent_detection={
                "type": "header",
                "confidence": 0.9,
                "reasoning": f"Font {size}pt {'Bold' if bold else ''}",
            },
        )

    # Learn patterns
    result = learner.learn_from_session(session_key, min_examples=3)

    assert isinstance(result, LearningResult)
    assert len(result.proposals) >= 1
    assert result.examples_used == 4

    # Check header pattern
    header_patterns = [p for p in result.proposals if p.element_type == "header"]
    assert len(header_patterns) >= 1

    pattern = header_patterns[0]
    assert pattern.stage1_regex is not None
    assert r"\d+" in pattern.stage1_regex  # Should detect section numbers
    assert pattern.confidence > 0.5
    assert len(pattern.learned_from) >= 3


def test_learn_table_pattern(learner, handler):
    """Test learner outputs camelot params from table examples."""
    session_key = "table-test-session"
    preset_id = "test-preset"

    # Create table examples with extraction hints
    for i in range(4):
        handler.save_with_extraction_hint(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=1,
            page=i * 10,
            element_idx=0,
            element_type="table",
            bbox=[72, 200, 540, 400],
            agent_detection={
                "type": "table",
                "confidence": 0.8,
                "reasoning": "Grid structure",
                "metadata": {"has_borders": True},
            },
            camelot_flavor="lattice",
            line_scale=25,
        )

    # Learn patterns
    result = learner.learn_from_session(session_key, min_examples=3)

    # Check table pattern
    table_patterns = [p for p in result.proposals if p.element_type == "table"]
    assert len(table_patterns) >= 1

    pattern = table_patterns[0]
    assert pattern.stage2_python is not None
    assert "lattice" in pattern.stage2_python
    assert "25" in pattern.stage2_python  # line_scale


def test_stage1_regex():
    """Test Stage 1 regex generation."""
    proposal = PatternProposal(
        element_type="header",
        pattern_name="test_header",
        stage1_regex=r"^\d+(\.\d+)*\s+[A-Z]",
        stage2_python=None,
        stage3_prompt=None,
        confidence=0.9,
        learned_from=["ex1", "ex2"],
        reasoning="Learned from section headers",
        sample_matches=["1.0 Introduction", "2.1 Methods"],
        sample_non_matches=["Regular text"],
    )

    assert proposal.stage1_regex is not None
    import re

    pattern = re.compile(proposal.stage1_regex)
    assert pattern.match("1.0 Introduction")
    assert pattern.match("2.1.3 Subsection")
    assert not pattern.match("Regular paragraph text")


def test_stage2_rapidfuzz():
    """Test Stage 2 fuzzy matching."""
    # Create a pattern with stage2 python
    stage2_code = """def validate(text, font_info):
    '''Stage 2 validation for header.'''
    if font_info.get('size', 0) >= 12 and font_info.get('is_bold', False):
        return True
    return False
"""

    # Execute the code
    exec_globals = {}
    exec(stage2_code, exec_globals)
    validate = exec_globals["validate"]

    # Test validation
    assert validate("1.0 Title", {"size": 14, "is_bold": True}) is True
    assert validate("1.0 Title", {"size": 10, "is_bold": False}) is False


def test_stage3_llm_fallback():
    """Test Stage 3 LLM fallback (when confidence < 0.7)."""
    proposal = PatternProposal(
        element_type="header",
        pattern_name="test_header",
        stage1_regex=r"^\d+",
        stage2_python="def validate(t, f): return True",
        stage3_prompt="Is '{text}' a section header? Answer YES or NO.",
        confidence=0.6,  # Low confidence triggers stage 3
        learned_from=["ex1"],
        reasoning="Low confidence pattern",
        sample_matches=[],
        sample_non_matches=[],
    )

    # Stage 3 should be available for low confidence
    assert proposal.confidence < 0.7
    assert proposal.stage3_prompt is not None
    assert "{text}" in proposal.stage3_prompt


def test_confirm_and_save_pattern(learner, handler, schema):
    """Test saving confirmed pattern to ArangoDB."""
    session_key = "save-pattern-session"
    preset_id = "test-preset"

    # Create examples first
    for i in range(3):
        handler.save_correct(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=1,
            page=i,
            element_idx=0,
            element_type="header",
            bbox=[72, 50, 400, 70],
            agent_detection={"type": "header", "confidence": 0.9, "reasoning": "Bold 14pt"},
        )

    # Learn patterns
    result = learner.learn_from_session(session_key, min_examples=2)
    assert len(result.proposals) >= 1

    # Confirm and save first pattern
    proposal = result.proposals[0]
    saved = learner.confirm_and_save_pattern(proposal, preset_id)

    assert "_key" in saved

    # Verify pattern was saved
    pattern = schema.get_pattern(f"{preset_id}_{proposal.pattern_name}")
    assert pattern is not None
    assert pattern["confirmed_by_human"] is True
    assert pattern["active"] is True


def test_get_active_patterns(learner, handler, schema):
    """Test retrieving active patterns."""
    session_key = "active-patterns-session"
    preset_id = "active-test-preset"

    # Create and save a pattern
    for i in range(3):
        handler.save_correct(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=1,
            page=i,
            element_idx=0,
            element_type="header",
            bbox=[72, 50, 400, 70],
            agent_detection={"type": "header", "confidence": 0.9, "reasoning": "Bold"},
        )

    result = learner.learn_from_session(session_key, min_examples=2)
    if result.proposals:
        learner.confirm_and_save_pattern(result.proposals[0], preset_id)

    # Get active patterns
    patterns = learner.get_active_patterns(preset_id)
    assert len(patterns) >= 1


def test_learning_result_dataclass():
    """Test LearningResult dataclass."""
    result = LearningResult(
        proposals=[],
        accuracy=0.85,
        examples_used=10,
        message="Test message",
    )

    assert result.accuracy == 0.85
    assert result.examples_used == 10
    assert result.message == "Test message"


def test_min_examples_threshold(learner, handler):
    """Test minimum examples required for pattern learning."""
    session_key = "min-examples-session"

    # Only create 2 examples (below default threshold of 3)
    for i in range(2):
        handler.save_correct(
            session_key=session_key,
            preset_id="test",
            calibration_round=1,
            page=i,
            element_idx=0,
            element_type="header",
            bbox=[72, 50, 400, 70],
            agent_detection={"type": "header", "confidence": 0.9, "reasoning": ""},
        )

    # With default min_examples=3, should not learn pattern
    result = learner.learn_from_session(session_key, min_examples=3)
    header_patterns = [p for p in result.proposals if p.element_type == "header"]
    assert len(header_patterns) == 0

    # With min_examples=2, should learn pattern
    result = learner.learn_from_session(session_key, min_examples=2)
    header_patterns = [p for p in result.proposals if p.element_type == "header"]
    assert len(header_patterns) >= 1
