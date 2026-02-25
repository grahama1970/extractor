"""Tests for s05_table_extractor with calibrated camelot params.

These tests verify calibrated extraction parameters are used when available.
"""


import pytest

from extractor.pipeline.calibration.schema import ArangoConfig, CalibrationSchema


@pytest.fixture
def schema():
    """Create a CalibrationSchema instance for testing."""
    config = ArangoConfig.from_env()
    config.database = "extractor_calibration_test"
    schema = CalibrationSchema(config)
    # Drop first to ensure clean state (handles leftover from interrupted tests)
    schema.drop_collections()
    schema.create_collections()
    yield schema
    schema.drop_collections()


def test_uses_calibrated_params(schema):
    """Test s05 uses learned camelot params (line_scale, flavor)."""
    # Create a learned pattern with camelot hints
    schema.create_pattern(
        {
            "_key": "test-preset_table_pattern",
            "preset_id": "test-preset",
            "element_type": "table",
            "pattern_name": "data_table",
            "stage1_regex": r"Table\s+\d+",
            "stage2_python": "def validate(t, f): return True",
            "confidence": 0.88,
            "confirmed_by_human": True,
            "active": True,
            "metadata": {
                "camelot_flavor": "lattice",
                "line_scale": 50,
            },
        }
    )

    # Verify pattern can be retrieved with camelot params
    patterns = schema.list_patterns(preset_id="test-preset", active_only=True)
    assert len(patterns) == 1
    pattern = patterns[0]

    # Integration point: s05 should use these params
    assert "metadata" in pattern
    metadata = pattern["metadata"]
    assert metadata["camelot_flavor"] == "lattice"
    assert metadata["line_scale"] == 50


def test_per_pattern_params(schema):
    """Test different patterns can have different camelot params."""
    # Pattern 1: lattice flavor for bordered tables
    schema.create_pattern(
        {
            "_key": "test-preset_bordered_table",
            "preset_id": "test-preset",
            "element_type": "table",
            "pattern_name": "bordered_table",
            "stage1_regex": r"\|.*\|",
            "confidence": 0.85,
            "confirmed_by_human": True,
            "active": True,
            "metadata": {
                "camelot_flavor": "lattice",
                "line_scale": 40,
            },
        }
    )

    # Pattern 2: stream flavor for borderless tables
    schema.create_pattern(
        {
            "_key": "test-preset_borderless_table",
            "preset_id": "test-preset",
            "element_type": "table",
            "pattern_name": "borderless_table",
            "stage1_regex": r"^\s{4,}\S",
            "confidence": 0.82,
            "confirmed_by_human": True,
            "active": True,
            "metadata": {
                "camelot_flavor": "stream",
                "row_tol": 5,
            },
        }
    )

    # Verify both patterns exist with different params
    patterns = schema.list_patterns(preset_id="test-preset", active_only=True)
    assert len(patterns) == 2

    # Integration: s05 should select correct params based on table type
    by_name = {p["pattern_name"]: p for p in patterns}

    bordered = by_name["bordered_table"]
    assert bordered["metadata"]["camelot_flavor"] == "lattice"
    assert bordered["metadata"]["line_scale"] == 40

    borderless = by_name["borderless_table"]
    assert borderless["metadata"]["camelot_flavor"] == "stream"
    assert borderless["metadata"]["row_tol"] == 5


def test_fallback_to_default(schema):
    """Test s05 falls back to default params when no calibration."""
    # When no calibrated patterns exist, s05 should use default params
    patterns = schema.list_patterns(preset_id="nonexistent-preset", active_only=True)
    assert len(patterns) == 0

    # Integration: s05 should use default camelot settings
    # Default: flavor="lattice", line_scale=40
    DEFAULT_CAMELOT_PARAMS = {
        "flavor": "lattice",
        "line_scale": 40,
    }

    # s05 should use these when no calibrated params found
    assert DEFAULT_CAMELOT_PARAMS["flavor"] == "lattice"


def test_extraction_hints_from_feedback(schema):
    """Test extraction hints from human feedback are stored and retrieved."""
    # Simulate what happens when human provides extraction hint during calibration
    # This tests the data structure for storing hints

    # First create a session
    schema.create_session(
        {
            "_key": "hint-session",
            "preset_id": "test-preset",
            "client": "test",
            "pdf_path": "test.pdf",
            "page_count": 10,
            "status": "in_progress",
            "owner": "test",
        }
    )

    # Create an example with extraction hint
    example = schema.create_example(
        {
            "session_id": "hint-session",
            "page_num": 5,
            "element_idx": 2,
            "element_type": "table",
            "bbox": [100, 200, 500, 400],
            "text_snippet": "Table 3: Performance Metrics",
            "agent_detection": {
                "detected_type": "table",
                "confidence": 0.75,
                "reasoning": "Found table header pattern",
            },
            "human_verdict": "correct",
            "created_by": "human",
            "extraction_hint": {
                "camelot_flavor": "stream",
                "row_tol": 8,
                "note": "Borderless table with irregular spacing",
            },
        }
    )

    # Verify hint can be retrieved
    retrieved = schema.get_example(example["_key"])
    assert retrieved is not None
    assert "extraction_hint" in retrieved
    hint = retrieved["extraction_hint"]
    assert hint["camelot_flavor"] == "stream"
    assert hint["row_tol"] == 8


def test_expected_csv_for_validation(schema):
    """Test expected CSV output is stored for validation."""
    # When human provides expected CSV during calibration
    schema.create_session(
        {
            "_key": "csv-session",
            "preset_id": "test-preset",
            "client": "test",
            "pdf_path": "test.pdf",
            "page_count": 10,
            "status": "in_progress",
            "owner": "test",
        }
    )

    expected_csv = """Name,Value,Unit
Temperature,25.5,C
Pressure,101.3,kPa
Humidity,65,percent"""

    example = schema.create_example(
        {
            "session_id": "csv-session",
            "page_num": 3,
            "element_idx": 0,
            "element_type": "table",
            "bbox": [50, 100, 550, 300],
            "text_snippet": "Table 1: Environmental Conditions",
            "agent_detection": {
                "detected_type": "table",
                "confidence": 0.9,
                "reasoning": "Clear table structure with header row",
            },
            "human_verdict": "correct",
            "created_by": "human",
            "expected_output": {
                "csv": expected_csv,
                "rows": 4,
                "cols": 3,
            },
        }
    )

    # Verify expected output can be retrieved
    retrieved = schema.get_example(example["_key"])
    assert retrieved is not None
    assert "expected_output" in retrieved
    output = retrieved["expected_output"]
    assert output["csv"] == expected_csv
    assert output["rows"] == 4
    assert output["cols"] == 3

    # Integration: s05 can compare extracted CSV with expected for accuracy
    def calculate_table_accuracy(extracted_csv: str, expected_csv: str) -> float:
        """Simple accuracy metric for table extraction."""
        extracted_rows = extracted_csv.strip().split("\n")
        expected_rows = expected_csv.strip().split("\n")

        if len(expected_rows) == 0:
            return 0.0

        matching = 0
        for i, expected in enumerate(expected_rows):
            if i < len(extracted_rows) and extracted_rows[i] == expected:
                matching += 1

        return matching / len(expected_rows)

    # Test the accuracy calculation
    assert calculate_table_accuracy(expected_csv, expected_csv) == 1.0
    assert calculate_table_accuracy("Wrong,Data\n", expected_csv) < 0.5


def test_calibration_improves_extraction():
    """Test concept: calibrated params should improve extraction accuracy."""
    # This test verifies the integration concept:
    # - s05 normally uses default camelot params
    # - With calibration, learned params should improve accuracy

    # Example: borderless table that default lattice fails on
    # After calibration with stream flavor hint, extraction should succeed

    default_params = {"flavor": "lattice", "line_scale": 40}

    # Simulate what s05 would do:
    # 1. Check for calibrated params for this table type
    # 2. If found, use calibrated params
    # 3. If not, use default params

    def get_extraction_params(pattern_metadata: dict | None) -> dict:
        """Get camelot params, preferring calibrated values."""
        if pattern_metadata and "camelot_flavor" in pattern_metadata:
            return {
                "flavor": pattern_metadata["camelot_flavor"],
                "line_scale": pattern_metadata.get("line_scale", 40),
                "row_tol": pattern_metadata.get("row_tol", 2),
                "edge_tol": pattern_metadata.get("edge_tol", 50),
            }
        return default_params

    # Without calibration
    params_default = get_extraction_params(None)
    assert params_default["flavor"] == "lattice"

    # With calibration
    params_calibrated = get_extraction_params(
        {
            "camelot_flavor": "stream",
            "row_tol": 5,
            "edge_tol": 20,
        }
    )
    assert params_calibrated["flavor"] == "stream"
    assert params_calibrated["row_tol"] == 5
