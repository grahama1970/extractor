"""Tests for human feedback handler.

These tests verify feedback saves to ArangoDB correctly.
"""


import pytest

from extractor.pipeline.calibration.feedback_handler import FeedbackHandler
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
def handler(schema):
    """Create a FeedbackHandler instance for testing."""
    return FeedbackHandler(schema)


@pytest.mark.integration
def test_save_correction(handler, schema):
    """Test feedback saves to ArangoDB, corrections append without delete."""
    session_key = "test-session_2026-01-19"
    preset_id = "test-preset"

    # Save initial feedback
    result = handler.save_correct(
        session_key=session_key,
        preset_id=preset_id,
        calibration_round=1,
        page=5,
        element_idx=3,
        element_type="table",
        bbox=[72.0, 200.0, 540.0, 400.0],
        agent_detection={"type": "table", "confidence": 0.78, "reasoning": "Grid detected"},
    )

    assert "_key" in result
    assert result["_key"] == f"{session_key}_p5_elem_3"

    # Verify saved
    doc = schema.get_example(result["_key"])
    assert doc is not None
    assert doc["human_verdict"] == "correct"
    assert doc["page"] == 5


@pytest.mark.integration
def test_save_rejection(handler, schema):
    """Test 'not element' feedback creates negative example."""
    session_key = "test-session_2026-01-19"

    result = handler.save_rejection(
        session_key=session_key,
        preset_id="test-preset",
        calibration_round=1,
        page=10,
        element_idx=2,
        element_type="header",
        bbox=[72.0, 50.0, 400.0, 70.0],
        agent_detection={"type": "header", "confidence": 0.6, "reasoning": "Bold text"},
        reason="This is actually a caption, not a header",
    )

    assert "_key" in result

    # Verify saved as negative example
    doc = schema.get_example(result["_key"])
    assert doc is not None
    assert doc["human_verdict"] == "not_element"
    assert doc["correction"]["note"] == "This is actually a caption, not a header"


@pytest.mark.integration
def test_save_split(handler, schema):
    """Test 'split' feedback handles merged elements."""
    session_key = "test-session_2026-01-19"

    result = handler.save_split(
        session_key=session_key,
        preset_id="test-preset",
        calibration_round=1,
        page=15,
        element_idx=1,
        element_type="table",
        bbox=[72.0, 100.0, 540.0, 500.0],
        agent_detection={"type": "table", "confidence": 0.85, "reasoning": "Large table"},
        split_description="This is actually two tables. Split at y=300.",
    )

    assert "_key" in result

    # Verify saved with split info
    doc = schema.get_example(result["_key"])
    assert doc is not None
    assert doc["human_verdict"] == "split"
    assert "two tables" in doc["correction"]["note"]


@pytest.mark.integration
def test_append_only(handler, schema):
    """Test corrections are append-only (no deletes)."""
    session_key = "test-session_2026-01-19"
    preset_id = "test-preset"

    # Save initial correct verdict
    result1 = handler.save_correct(
        session_key=session_key,
        preset_id=preset_id,
        calibration_round=1,
        page=5,
        element_idx=3,
        element_type="table",
        bbox=[72.0, 200.0, 540.0, 400.0],
        agent_detection={"type": "table", "confidence": 0.78, "reasoning": "Grid"},
    )

    # Now "correct" the correction - should create new entry, not overwrite
    result2 = handler.save_wrong_type(
        session_key=session_key,
        preset_id=preset_id,
        calibration_round=1,
        page=5,
        element_idx=3,
        element_type="table",
        bbox=[72.0, 200.0, 540.0, 400.0],
        agent_detection={"type": "table", "confidence": 0.78, "reasoning": "Grid"},
        correct_type="figure",
        note="Actually a diagram",
    )

    # Both entries should exist
    assert result1["_key"] != result2["_key"]

    doc1 = schema.get_example(result1["_key"])
    doc2 = schema.get_example(result2["_key"])

    assert doc1 is not None
    assert doc2 is not None

    # Original is preserved
    assert doc1["human_verdict"] == "correct"
    # Correction is added
    assert doc2["human_verdict"] == "wrong_type"
    assert "_corr" in result2["_key"]


@pytest.mark.integration
def test_save_with_expected_csv(handler, schema):
    """Test saving table with expected CSV output."""
    result = handler.save_with_expected_csv(
        session_key="test-session",
        preset_id="test-preset",
        calibration_round=1,
        page=7,
        element_idx=0,
        bbox=[72, 200, 540, 400],
        agent_detection={"type": "table", "confidence": 0.9, "reasoning": "Table"},
        expected_csv="col1,col2,col3\nval1,val2,val3\n",
    )

    doc = schema.get_example(result["_key"])
    assert doc is not None
    assert doc["expected_output"]["csv"] == "col1,col2,col3\nval1,val2,val3\n"


@pytest.mark.integration
def test_save_with_extraction_hint(handler, schema):
    """Test saving with camelot extraction hint."""
    result = handler.save_with_extraction_hint(
        session_key="test-session",
        preset_id="test-preset",
        calibration_round=1,
        page=8,
        element_idx=1,
        element_type="table",
        bbox=[72, 200, 540, 400],
        agent_detection={"type": "table", "confidence": 0.7, "reasoning": "Borderless"},
        camelot_flavor="stream",
        line_scale=15,
        edge_tol=100,
    )

    doc = schema.get_example(result["_key"])
    assert doc is not None
    assert doc["extraction_hint"]["camelot_flavor"] == "stream"
    assert doc["extraction_hint"]["line_scale"] == 15
    assert doc["extraction_hint"]["edge_tol"] == 100


@pytest.mark.integration
def test_get_round_accuracy(handler):
    """Test accuracy calculation."""
    session_key = "acc-test-session"

    # Save 3 correct, 1 wrong
    for i in range(3):
        handler.save_correct(
            session_key=session_key,
            preset_id="test",
            calibration_round=1,
            page=i,
            element_idx=0,
            element_type="header",
            bbox=[0, 0, 100, 20],
            agent_detection={"type": "header", "confidence": 0.9, "reasoning": ""},
        )

    handler.save_rejection(
        session_key=session_key,
        preset_id="test",
        calibration_round=1,
        page=10,
        element_idx=0,
        element_type="header",
        bbox=[0, 0, 100, 20],
        agent_detection={"type": "header", "confidence": 0.5, "reasoning": ""},
        reason="Not a header",
    )

    correct, total, accuracy = handler.get_round_accuracy(session_key, calibration_round=1)
    assert correct == 3
    assert total == 4
    assert accuracy == 75.0


@pytest.mark.integration
def test_get_session_examples(handler):
    """Test retrieving session examples."""
    session_key = "example-test-session"

    handler.save_correct(
        session_key=session_key,
        preset_id="test",
        calibration_round=1,
        page=1,
        element_idx=0,
        element_type="header",
        bbox=[0, 0, 100, 20],
        agent_detection={"type": "header", "confidence": 0.9, "reasoning": ""},
    )

    examples = handler.get_session_examples(session_key)
    assert len(examples) == 1

    # Filter by verdict
    correct = handler.get_session_examples(session_key, verdict="correct")
    assert len(correct) == 1

    wrong = handler.get_session_examples(session_key, verdict="wrong_type")
    assert len(wrong) == 0
