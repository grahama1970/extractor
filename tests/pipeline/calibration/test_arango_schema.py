"""Tests for ArangoDB calibration schema.

These tests verify the calibration collections can be created and basic CRUD works.
"""

from datetime import datetime, timezone

import pytest

from extractor.pipeline.calibration.schema import (
    COLLECTION_EXAMPLES,
    COLLECTION_PATTERNS,
    COLLECTION_SESSIONS,
    EDGE_CONFIRMS,
    ArangoConfig,
    CalibrationSchema,
)


@pytest.fixture
def schema():
    """Create a CalibrationSchema instance for testing."""
    # Use test-specific database to avoid polluting production data
    config = ArangoConfig.from_env()
    config.database = "extractor_calibration_test"
    return CalibrationSchema(config)


@pytest.fixture
def clean_schema(schema):
    """Create schema and clean up collections before/after test."""
    # Setup: ensure collections exist but are empty
    schema.create_collections()
    schema.drop_collections()
    schema.create_collections()
    yield schema
    # Teardown: clean up test data
    schema.drop_collections()


@pytest.mark.integration
def test_create_collections(schema):
    """Test that calibration collections can be created."""
    # Drop any existing collections first
    schema.drop_collections()

    # Create collections
    results = schema.create_collections()

    # Verify all collections were created
    assert results[COLLECTION_SESSIONS] is True
    assert results[COLLECTION_EXAMPLES] is True
    assert results[COLLECTION_PATTERNS] is True
    assert results[EDGE_CONFIRMS] is True

    # Verify collections exist
    assert schema.db.has_collection(COLLECTION_SESSIONS)
    assert schema.db.has_collection(COLLECTION_EXAMPLES)
    assert schema.db.has_collection(COLLECTION_PATTERNS)
    assert schema.db.has_collection(EDGE_CONFIRMS)

    # Second call should not recreate
    results2 = schema.create_collections()
    assert results2[COLLECTION_SESSIONS] is False
    assert results2[COLLECTION_EXAMPLES] is False
    assert results2[COLLECTION_PATTERNS] is False
    assert results2[EDGE_CONFIRMS] is False

    # Cleanup
    schema.drop_collections()


@pytest.mark.integration
def test_session_crud(clean_schema):
    """Test calibration session CRUD operations."""
    schema = clean_schema
    now = datetime.now(timezone.utc).isoformat()

    # Create
    session_data = {
        "_key": "test-preset_2026-01-19",
        "preset_id": "test-preset",
        "client": "test-client",
        "pdf_path": "data/input/test.pdf",
        "page_count": 100,
        "status": "in_progress",
        "accuracy_history": [],
        "created_at": now,
        "updated_at": now,
        "owner": "test-user",
    }
    result = schema.create_session(session_data)
    assert "_key" in result
    assert result["_key"] == "test-preset_2026-01-19"

    # Read
    session = schema.get_session("test-preset_2026-01-19")
    assert session is not None
    assert session["preset_id"] == "test-preset"
    assert session["status"] == "in_progress"

    # Update
    schema.update_session(
        "test-preset_2026-01-19",
        {"status": "converged", "accuracy_history": [0.72, 0.88, 0.95]},
    )
    updated = schema.get_session("test-preset_2026-01-19")
    assert updated["status"] == "converged"
    assert updated["accuracy_history"] == [0.72, 0.88, 0.95]

    # List
    sessions = schema.list_sessions()
    assert len(sessions) == 1

    # List with filter
    sessions = schema.list_sessions(preset_id="test-preset")
    assert len(sessions) == 1
    sessions = schema.list_sessions(preset_id="nonexistent")
    assert len(sessions) == 0


@pytest.mark.integration
def test_example_crud(clean_schema):
    """Test calibration example CRUD operations."""
    schema = clean_schema
    now = datetime.now(timezone.utc).isoformat()

    # Create
    example_data = {
        "_key": "test-preset_2026-01-19_p5_elem_3",
        "session_key": "test-preset_2026-01-19",
        "preset_id": "test-preset",
        "round": 1,
        "page": 5,
        "element_idx": 3,
        "element_type": "table",
        "bbox": [72, 200, 540, 400],
        "agent_detection": {"type": "table", "confidence": 0.78, "reasoning": "..."},
        "human_verdict": "correct",
        "correction": None,
        "expected_output": None,
        "extraction_hint": None,
        "created_at": now,
        "created_by": "human",
    }
    result = schema.create_example(example_data)
    assert "_key" in result

    # Read
    example = schema.get_example("test-preset_2026-01-19_p5_elem_3")
    assert example is not None
    assert example["page"] == 5
    assert example["element_type"] == "table"

    # List
    examples = schema.list_examples()
    assert len(examples) == 1

    # List with filters
    examples = schema.list_examples(session_key="test-preset_2026-01-19")
    assert len(examples) == 1
    examples = schema.list_examples(page=5)
    assert len(examples) == 1
    examples = schema.list_examples(page=10)
    assert len(examples) == 0


@pytest.mark.integration
def test_pattern_crud(clean_schema):
    """Test learned pattern CRUD operations."""
    schema = clean_schema
    now = datetime.now(timezone.utc).isoformat()

    # Create
    pattern_data = {
        "_key": "test-preset_header_blue_font",
        "preset_id": "test-preset",
        "element_type": "header",
        "pattern_name": "blue_font_header",
        "stage1_regex": r"^\d+\.\d+\s+[A-Z]",
        "stage2_python": "def validate(text, font): return font.color == '#003366'",
        "stage3_prompt": "Is '{text}' a section header?",
        "confidence": 0.92,
        "learned_from": ["p3_elem_1", "p7_elem_0"],
        "confirmed_by_human": True,
        "created_at": now,
        "active": True,
    }
    result = schema.create_pattern(pattern_data)
    assert "_key" in result

    # Read
    pattern = schema.get_pattern("test-preset_header_blue_font")
    assert pattern is not None
    assert pattern["element_type"] == "header"
    assert pattern["confidence"] == 0.92

    # Update
    schema.update_pattern("test-preset_header_blue_font", {"confidence": 0.95})
    updated = schema.get_pattern("test-preset_header_blue_font")
    assert updated["confidence"] == 0.95

    # List
    patterns = schema.list_patterns()
    assert len(patterns) == 1

    # List with filters
    patterns = schema.list_patterns(preset_id="test-preset")
    assert len(patterns) == 1
    patterns = schema.list_patterns(preset_id="nonexistent")
    assert len(patterns) == 0

    # Test active_only filter
    schema.update_pattern("test-preset_header_blue_font", {"active": False})
    patterns = schema.list_patterns(active_only=True)
    assert len(patterns) == 0
    patterns = schema.list_patterns(active_only=False)
    assert len(patterns) == 1


@pytest.mark.integration
def test_confirm_edge(clean_schema):
    """Test edge collection for example-pattern relationships."""
    schema = clean_schema
    now = datetime.now(timezone.utc).isoformat()

    # Create an example
    example_data = {
        "_key": "test_p5_elem_1",
        "session_key": "test_session",
        "preset_id": "test-preset",
        "round": 1,
        "page": 5,
        "element_idx": 1,
        "element_type": "header",
        "bbox": [72, 100, 540, 120],
        "agent_detection": {"type": "header", "confidence": 0.9},
        "human_verdict": "correct",
        "created_at": now,
        "created_by": "human",
    }
    schema.create_example(example_data)

    # Create a pattern
    pattern_data = {
        "_key": "test_header_pattern",
        "preset_id": "test-preset",
        "element_type": "header",
        "pattern_name": "test_header",
        "stage1_regex": r"^\d+\.",
        "confidence": 0.85,
        "learned_from": ["test_p5_elem_1"],
        "confirmed_by_human": True,
        "created_at": now,
        "active": True,
    }
    schema.create_pattern(pattern_data)

    # Create edge
    edge = schema.create_confirm_edge(
        example_key="test_p5_elem_1",
        pattern_key="test_header_pattern",
        relationship="confirms",
    )
    # Insert returns metadata, verify edge was created
    assert "_key" in edge
    assert "_id" in edge

    # Get pattern examples
    examples = schema.get_pattern_examples("test_header_pattern")
    assert len(examples) == 1
    assert examples[0]["_key"] == "test_p5_elem_1"
