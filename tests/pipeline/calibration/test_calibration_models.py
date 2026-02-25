"""Tests for calibration data models.

These tests verify Pydantic models serialize to ArangoDB and back correctly.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from extractor.pipeline.calibration.models import (
    AgentDetection,
    CalibrationExample,
    CalibrationSession,
    ConfirmEdge,
    Correction,
    CreatedBy,
    ExpectedOutput,
    ExtractionHint,
    HumanVerdict,
    LearnedPattern,
    Relationship,
    SessionStatus,
)
from extractor.pipeline.calibration.schema import (
    ArangoConfig,
    CalibrationSchema,
    COLLECTION_EXAMPLES,
    COLLECTION_PATTERNS,
)


@pytest.fixture
def schema():
    """Create a CalibrationSchema instance for testing."""
    config = ArangoConfig.from_env()
    config.database = "extractor_calibration_test"
    schema = CalibrationSchema(config)
    schema.create_collections()
    yield schema
    schema.drop_collections()


def test_session_roundtrip(schema):
    """Test CalibrationSession serializes to ArangoDB and back."""
    now = datetime.now(timezone.utc)

    # Create session model
    session = CalibrationSession(
        _key="test-preset_2026-01-19",
        preset_id="test-preset",
        client="test-client",
        pdf_path="data/input/test.pdf",
        page_count=100,
        status=SessionStatus.IN_PROGRESS,
        accuracy_history=[0.72, 0.88],
        created_at=now,
        updated_at=now,
        owner="test-user",
    )

    # Verify model attributes
    assert session.key == "test-preset_2026-01-19"
    assert session.preset_id == "test-preset"
    assert session.status == SessionStatus.IN_PROGRESS

    # Convert to ArangoDB format and save
    arango_doc = session.to_arango()
    assert "_key" in arango_doc
    assert arango_doc["_key"] == "test-preset_2026-01-19"
    assert isinstance(arango_doc["created_at"], str)

    # Save to ArangoDB
    result = schema.create_session(arango_doc)
    assert result["_key"] == "test-preset_2026-01-19"

    # Read back from ArangoDB
    doc = schema.get_session("test-preset_2026-01-19")
    assert doc is not None

    # Convert back to model
    loaded = CalibrationSession.from_arango(doc)
    assert loaded.key == session.key
    assert loaded.preset_id == session.preset_id
    assert loaded.status == session.status
    assert loaded.accuracy_history == [0.72, 0.88]


def test_example_roundtrip(schema):
    """Test CalibrationExample serializes correctly."""
    now = datetime.now(timezone.utc)

    # Create example model with all nested types
    example = CalibrationExample(
        _key="test_p5_elem_3",
        session_key="test-session",
        preset_id="test-preset",
        round=1,
        page=5,
        element_idx=3,
        element_type="table",
        bbox=[72.0, 200.0, 540.0, 400.0],
        agent_detection=AgentDetection(
            type="table",
            confidence=0.78,
            reasoning="Detected grid structure with borders",
        ),
        human_verdict=HumanVerdict.CORRECT,
        correction=None,
        expected_output=ExpectedOutput(csv="col1,col2\nval1,val2", format="inline"),
        extraction_hint=ExtractionHint(camelot_flavor="lattice", line_scale=25),
        created_at=now,
        created_by=CreatedBy.HUMAN,
    )

    # Verify model attributes
    assert example.key == "test_p5_elem_3"
    assert example.agent_detection.confidence == 0.78
    assert example.human_verdict == HumanVerdict.CORRECT
    assert example.extraction_hint.camelot_flavor == "lattice"

    # Convert to ArangoDB format
    arango_doc = example.to_arango()
    assert "_key" in arango_doc
    assert isinstance(arango_doc["agent_detection"], dict)

    # Save to ArangoDB
    result = schema.create_example(arango_doc)
    assert "_key" in result

    # Read back
    doc = schema.get_example("test_p5_elem_3")
    assert doc is not None

    # Convert back to model
    loaded = CalibrationExample.from_arango(doc)
    assert loaded.key == example.key
    assert loaded.agent_detection.confidence == 0.78
    assert loaded.human_verdict == HumanVerdict.CORRECT


def test_pattern_roundtrip(schema):
    """Test LearnedPattern serializes correctly."""
    now = datetime.now(timezone.utc)

    # Create pattern model
    pattern = LearnedPattern(
        _key="test-preset_header_pattern",
        preset_id="test-preset",
        element_type="header",
        pattern_name="blue_font_header",
        stage1_regex=r"^\d+\.\d+\s+[A-Z]",
        stage2_python="def validate(text, font): return font.color == '#003366'",
        stage3_prompt="Is '{text}' a section header?",
        confidence=0.92,
        learned_from=["p3_elem_1", "p7_elem_0"],
        confirmed_by_human=True,
        created_at=now,
        active=True,
    )

    # Verify model attributes
    assert pattern.key == "test-preset_header_pattern"
    assert pattern.confidence == 0.92
    assert pattern.confirmed_by_human is True

    # Convert to ArangoDB format
    arango_doc = pattern.to_arango()
    assert "_key" in arango_doc

    # Save to ArangoDB
    result = schema.create_pattern(arango_doc)
    assert "_key" in result

    # Read back
    doc = schema.get_pattern("test-preset_header_pattern")
    assert doc is not None

    # Convert back to model
    loaded = LearnedPattern.from_arango(doc)
    assert loaded.key == pattern.key
    assert loaded.confidence == 0.92
    assert loaded.stage1_regex == r"^\d+\.\d+\s+[A-Z]"


def test_validation():
    """Test model validation catches invalid data."""
    # Test confidence out of range
    with pytest.raises(ValidationError):
        AgentDetection(type="table", confidence=1.5, reasoning="test")

    with pytest.raises(ValidationError):
        AgentDetection(type="table", confidence=-0.1, reasoning="test")

    # Test missing required fields
    with pytest.raises(ValidationError):
        CalibrationSession(
            preset_id="test",  # Missing _key, client, pdf_path, page_count, owner
        )

    # Test invalid bbox (wrong length)
    with pytest.raises(ValidationError):
        CalibrationExample(
            _key="test",
            session_key="test",
            preset_id="test",
            round=1,
            page=0,
            element_idx=0,
            element_type="table",
            bbox=[1, 2, 3],  # Should be 4 elements
            agent_detection=AgentDetection(type="table", confidence=0.8, reasoning=""),
        )

    # Test negative page count
    with pytest.raises(ValidationError):
        CalibrationSession(
            _key="test",
            preset_id="test",
            client="test",
            pdf_path="test.pdf",
            page_count=0,  # Must be >= 1
            owner="test",
        )


def test_confirm_edge():
    """Test ConfirmEdge model for example-pattern links."""
    edge = ConfirmEdge(
        _from=f"{COLLECTION_EXAMPLES}/test_p5_elem_1",
        _to=f"{COLLECTION_PATTERNS}/test_header_pattern",
        relationship=Relationship.CONFIRMS,
    )

    # Verify attributes
    assert edge.from_example == f"{COLLECTION_EXAMPLES}/test_p5_elem_1"
    assert edge.to_pattern == f"{COLLECTION_PATTERNS}/test_header_pattern"
    assert edge.relationship == Relationship.CONFIRMS

    # Convert to ArangoDB
    doc = edge.to_arango()
    assert doc["_from"] == f"{COLLECTION_EXAMPLES}/test_p5_elem_1"
    assert doc["_to"] == f"{COLLECTION_PATTERNS}/test_header_pattern"


def test_correction_model():
    """Test Correction nested model."""
    correction = Correction(correct_type="figure", note="This is a diagram, not a table")
    assert correction.correct_type == "figure"
    assert "diagram" in correction.note


def test_extraction_hint_model():
    """Test ExtractionHint nested model."""
    hint = ExtractionHint(camelot_flavor="stream", edge_tol=50)
    assert hint.camelot_flavor == "stream"
    assert hint.line_scale is None
    assert hint.edge_tol == 50


def test_session_status_enum():
    """Test SessionStatus enum values."""
    assert SessionStatus.IN_PROGRESS.value == "in_progress"
    assert SessionStatus.CONVERGED.value == "converged"
    assert SessionStatus.ARCHIVED.value == "archived"


def test_human_verdict_enum():
    """Test HumanVerdict enum values."""
    assert HumanVerdict.CORRECT.value == "correct"
    assert HumanVerdict.WRONG_TYPE.value == "wrong_type"
    assert HumanVerdict.NOT_ELEMENT.value == "not_element"
    assert HumanVerdict.SPLIT.value == "split"
    assert HumanVerdict.FLAGGED.value == "flagged"
