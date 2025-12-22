"""
Unit tests for reflow schema validation.
"""

import pytest
from pydantic import ValidationError

from extractor.pipeline.schemas.reflow import (
    ReflowOutput,
    ReflowedJson,
    ParagraphBlock,
    ListBlock,
    TableBlock,
    FigureBlock,
    validate_reflow_output,
)


class TestParagraphBlock:
    def test_valid_paragraph(self):
        block = ParagraphBlock(type="paragraph", text="Hello world")
        assert block.text == "Hello world"

    def test_missing_text_fails(self):
        with pytest.raises(ValidationError):
            ParagraphBlock(type="paragraph")


class TestListBlock:
    def test_valid_list(self):
        block = ListBlock(type="list", items=["a", "b", "c"])
        assert len(block.items) == 3

    def test_empty_list_allowed(self):
        block = ListBlock(type="list", items=[])
        assert block.items == []


class TestTableBlock:
    def test_valid_table(self):
        block = TableBlock(
            type="table",
            id="t1",
            title="Test Table",
            columns=["A", "B"],
            rows=[["1", "2"], ["3", "4"]],
        )
        assert len(block.rows) == 2

    def test_row_column_mismatch_fails(self):
        with pytest.raises(ValidationError) as exc_info:
            TableBlock(
                type="table",
                id="t1",
                columns=["A", "B", "C"],
                rows=[["1", "2"]],  # Only 2 cells, expected 3
            )
        assert "cells" in str(exc_info.value)

    def test_optional_title(self):
        block = TableBlock(
            type="table",
            id="t1",
            columns=["A"],
            rows=[["1"]],
        )
        assert block.title is None


class TestFigureBlock:
    def test_valid_figure(self):
        block = FigureBlock(
            type="figure",
            id="f1",
            image_ref="path/to/image.png",
            caption="A diagram",
        )
        assert block.image_ref == "path/to/image.png"

    def test_optional_caption(self):
        block = FigureBlock(type="figure", id="f1", image_ref="img.png")
        assert block.caption is None


class TestReflowedJson:
    def test_empty_blocks(self):
        rj = ReflowedJson(title=None, blocks=[])
        assert rj.blocks == []

    def test_mixed_blocks(self):
        rj = ReflowedJson(
            title="Test Section",
            blocks=[
                {"type": "paragraph", "text": "Hello"},
                {"type": "list", "items": ["a", "b"]},
            ],
        )
        assert len(rj.blocks) == 2
        assert rj.blocks[0].type == "paragraph"
        assert rj.blocks[1].type == "list"


class TestReflowOutput:
    def test_full_valid_output(self):
        data = {
            "reflowed_json": {"title": "Intro", "blocks": []},
            "ocr_corrections": {"teh": "the"},
            "improvements_made": "Fixed typos",
            "summary": "Introduction section",
            "confidence": 0.95,
        }
        output = ReflowOutput.model_validate(data)
        assert output.confidence == 0.95
        assert output.ocr_corrections["teh"] == "the"

    def test_minimal_valid_output(self):
        data = {"reflowed_json": {"blocks": []}}
        output = ReflowOutput.model_validate(data)
        assert output.summary == ""
        assert output.confidence == 1.0

    def test_confidence_out_of_range_fails(self):
        with pytest.raises(ValidationError):
            ReflowOutput.model_validate(
                {"reflowed_json": {"blocks": []}, "confidence": 1.5}
            )

    def test_negative_confidence_fails(self):
        with pytest.raises(ValidationError):
            ReflowOutput.model_validate(
                {"reflowed_json": {"blocks": []}, "confidence": -0.1}
            )


class TestValidateReflowOutput:
    def test_valid_returns_output(self):
        data = {"reflowed_json": {"blocks": []}}
        output, error = validate_reflow_output(data)
        assert output is not None
        assert error is None

    def test_invalid_returns_error(self):
        data = {"wrong_key": "value"}
        output, error = validate_reflow_output(data)
        assert output is None
        assert error is not None
        assert "reflowed_json" in error.lower() or "required" in error.lower()
