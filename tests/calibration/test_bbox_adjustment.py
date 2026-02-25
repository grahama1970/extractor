"""Tests for bbox adjustment flow.

Task 7: Parse human descriptions and calculate new bounding boxes.
"""

import pytest

from extractor.pipeline.calibration.bbox_adjuster import (
    parse_bbox_adjustment,
    apply_adjustment,
    BboxAdjustment,
    AdjustmentType,
)


class TestParseRelativeAdjustments:
    """Test parsing relative adjustment descriptions."""

    @pytest.mark.parametrize(
        "text,expected_type,expected_direction,expected_amount",
        [
            ("extend right by 50px", AdjustmentType.EXTEND, "right", 50),
            ("extend left by 30", AdjustmentType.EXTEND, "left", 30),
            ("extend top by 20px", AdjustmentType.EXTEND, "top", 20),
            ("extend bottom by 40", AdjustmentType.EXTEND, "bottom", 40),
            ("shrink right by 10px", AdjustmentType.SHRINK, "right", 10),
            ("reduce left by 15", AdjustmentType.SHRINK, "left", 15),
        ],
    )
    def test_relative_adjustments(self, text, expected_type, expected_direction, expected_amount):
        """Test parsing relative bbox adjustments."""
        result = parse_bbox_adjustment(text)
        assert result is not None
        assert result.adjustment_type == expected_type
        assert result.direction == expected_direction
        assert result.amount == expected_amount


class TestParseAbsoluteCoords:
    """Test parsing absolute coordinate specifications."""

    @pytest.mark.parametrize(
        "text,expected_bbox",
        [
            ("[72, 200, 540, 450]", [72, 200, 540, 450]),
            ("72, 200, 540, 450", [72, 200, 540, 450]),
            ("new coords: 72, 200, 540, 450", [72, 200, 540, 450]),
            ("set bbox to [100, 100, 400, 400]", [100, 100, 400, 400]),
        ],
    )
    def test_absolute_coords(self, text, expected_bbox):
        """Test parsing absolute coordinate specifications."""
        result = parse_bbox_adjustment(text)
        assert result is not None
        assert result.adjustment_type == AdjustmentType.ABSOLUTE
        assert result.new_bbox == expected_bbox


class TestParseSemanticAdjustments:
    """Test parsing semantic/descriptive adjustments."""

    @pytest.mark.parametrize(
        "text,expected_direction",
        [
            ("include the caption below", "bottom"),
            ("include caption above", "top"),
            ("cuts off the right side", "right"),
            ("cutting off on the left", "left"),
            ("extend to full width", "width"),
        ],
    )
    def test_semantic_adjustments(self, text, expected_direction):
        """Test parsing semantic adjustment descriptions."""
        result = parse_bbox_adjustment(text)
        assert result is not None
        assert result.direction == expected_direction


class TestApplyAdjustments:
    """Test applying adjustments to existing bboxes."""

    def test_extend_right(self):
        """Test extending bbox to the right."""
        original = [72, 200, 400, 450]
        adjustment = BboxAdjustment(
            adjustment_type=AdjustmentType.EXTEND,
            direction="right",
            amount=50,
        )
        result = apply_adjustment(original, adjustment)
        assert result == [72, 200, 450, 450]

    def test_extend_left(self):
        """Test extending bbox to the left."""
        original = [72, 200, 400, 450]
        adjustment = BboxAdjustment(
            adjustment_type=AdjustmentType.EXTEND,
            direction="left",
            amount=20,
        )
        result = apply_adjustment(original, adjustment)
        assert result == [52, 200, 400, 450]

    def test_extend_top(self):
        """Test extending bbox upward."""
        original = [72, 200, 400, 450]
        adjustment = BboxAdjustment(
            adjustment_type=AdjustmentType.EXTEND,
            direction="top",
            amount=30,
        )
        result = apply_adjustment(original, adjustment)
        assert result == [72, 170, 400, 450]

    def test_extend_bottom(self):
        """Test extending bbox downward."""
        original = [72, 200, 400, 450]
        adjustment = BboxAdjustment(
            adjustment_type=AdjustmentType.EXTEND,
            direction="bottom",
            amount=25,
        )
        result = apply_adjustment(original, adjustment)
        assert result == [72, 200, 400, 475]

    def test_shrink_right(self):
        """Test shrinking bbox from the right."""
        original = [72, 200, 400, 450]
        adjustment = BboxAdjustment(
            adjustment_type=AdjustmentType.SHRINK,
            direction="right",
            amount=50,
        )
        result = apply_adjustment(original, adjustment)
        assert result == [72, 200, 350, 450]

    def test_absolute_replacement(self):
        """Test replacing bbox with absolute coords."""
        original = [72, 200, 400, 450]
        adjustment = BboxAdjustment(
            adjustment_type=AdjustmentType.ABSOLUTE,
            new_bbox=[100, 150, 500, 500],
        )
        result = apply_adjustment(original, adjustment)
        assert result == [100, 150, 500, 500]


class TestEdgeCases:
    """Test edge cases in bbox adjustment."""

    def test_unparseable_returns_none(self):
        """Test that unparseable input returns None."""
        result = parse_bbox_adjustment("make it better")
        assert result is None

    def test_negative_amount_clamped(self):
        """Test that negative amounts don't make invalid bboxes."""
        original = [72, 200, 100, 250]  # Small bbox
        adjustment = BboxAdjustment(
            adjustment_type=AdjustmentType.SHRINK,
            direction="right",
            amount=50,  # Would make x1 < x0
        )
        result = apply_adjustment(original, adjustment)
        # Should clamp to minimum valid bbox
        assert result[2] >= result[0]  # x1 >= x0
