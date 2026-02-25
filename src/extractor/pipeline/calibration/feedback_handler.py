"""Human feedback handler for calibration.

Processes TUI feedback into ArangoDB records.
Supports: correct, wrong_type, not_element, split, flagged.
Corrections are append-only (never delete for training data preservation).
"""

from datetime import datetime, timezone
from typing import Any

from extractor.pipeline.calibration.models import (
    CalibrationExample,
    AgentDetection,
    Correction,
    ExpectedOutput,
    ExtractionHint,
    HumanVerdict,
    CreatedBy,
)
from extractor.pipeline.calibration.schema import CalibrationSchema


class FeedbackHandler:
    """Handle human feedback on element detections."""

    def __init__(self, schema: CalibrationSchema | None = None):
        """Initialize feedback handler.

        Args:
            schema: CalibrationSchema instance. Creates new one if not provided.
        """
        self.schema = schema or CalibrationSchema()
        self.schema.create_collections()

    def save_feedback(
        self,
        session_key: str,
        preset_id: str,
        calibration_round: int,
        page: int,
        element_idx: int,
        element_type: str,
        bbox: list[float],
        agent_detection: dict[str, Any],
        verdict: str,
        correction: dict[str, Any] | None = None,
        expected_output: dict[str, Any] | None = None,
        extraction_hint: dict[str, Any] | None = None,
        created_by: str = "human",
    ) -> dict[str, Any]:
        """Save human feedback on an element detection.

        Args:
            session_key: Parent session key.
            preset_id: Preset ID.
            calibration_round: Current calibration round.
            page: Page number.
            element_idx: Element index on page.
            element_type: Type of element.
            bbox: Bounding box [x0, y0, x1, y1].
            agent_detection: Agent's detection result dict.
            verdict: Human verdict (correct, wrong_type, not_element, split, flagged).
            correction: Optional correction data.
            expected_output: Optional expected extraction output.
            extraction_hint: Optional extraction hints (camelot params, etc).
            created_by: Who created this ("human" or "agent").

        Returns:
            Created example document.
        """
        # Generate unique key
        key = f"{session_key}_p{page}_elem_{element_idx}"

        # Check if example already exists - if so, append correction
        existing = self.schema.get_example(key)
        if existing:
            # Append-only: create new example with correction reference
            correction_num = 1
            while self.schema.get_example(f"{key}_corr{correction_num}"):
                correction_num += 1
            key = f"{key}_corr{correction_num}"

        # Create example model
        example = CalibrationExample(
            _key=key,
            session_key=session_key,
            preset_id=preset_id,
            round=calibration_round,
            page=page,
            element_idx=element_idx,
            element_type=element_type,
            bbox=bbox,
            agent_detection=AgentDetection(**agent_detection),
            human_verdict=HumanVerdict(verdict) if verdict else None,
            correction=Correction(**correction) if correction else None,
            expected_output=ExpectedOutput(**expected_output) if expected_output else None,
            extraction_hint=ExtractionHint(**extraction_hint) if extraction_hint else None,
            created_at=datetime.now(timezone.utc),
            created_by=CreatedBy(created_by),
        )

        # Save to ArangoDB
        return self.schema.create_example(example.to_arango())

    def save_correct(
        self,
        session_key: str,
        preset_id: str,
        calibration_round: int,
        page: int,
        element_idx: int,
        element_type: str,
        bbox: list[float],
        agent_detection: dict[str, Any],
    ) -> dict[str, Any]:
        """Save 'correct' verdict for an element.

        Args:
            session_key: Parent session key.
            preset_id: Preset ID.
            calibration_round: Current calibration round.
            page: Page number.
            element_idx: Element index.
            element_type: Element type.
            bbox: Bounding box.
            agent_detection: Agent's detection.

        Returns:
            Created example document.
        """
        return self.save_feedback(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=calibration_round,
            page=page,
            element_idx=element_idx,
            element_type=element_type,
            bbox=bbox,
            agent_detection=agent_detection,
            verdict="correct",
        )

    def save_rejection(
        self,
        session_key: str,
        preset_id: str,
        calibration_round: int,
        page: int,
        element_idx: int,
        element_type: str,
        bbox: list[float],
        agent_detection: dict[str, Any],
        reason: str = "",
    ) -> dict[str, Any]:
        """Save 'not_element' verdict (rejection/negative example).

        Args:
            session_key: Parent session key.
            preset_id: Preset ID.
            calibration_round: Current calibration round.
            page: Page number.
            element_idx: Element index.
            element_type: Element type.
            bbox: Bounding box.
            agent_detection: Agent's detection.
            reason: Reason for rejection.

        Returns:
            Created example document (negative training example).
        """
        return self.save_feedback(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=calibration_round,
            page=page,
            element_idx=element_idx,
            element_type=element_type,
            bbox=bbox,
            agent_detection=agent_detection,
            verdict="not_element",
            correction={"correct_type": None, "note": reason},
        )

    def save_wrong_type(
        self,
        session_key: str,
        preset_id: str,
        calibration_round: int,
        page: int,
        element_idx: int,
        element_type: str,
        bbox: list[float],
        agent_detection: dict[str, Any],
        correct_type: str,
        note: str = "",
    ) -> dict[str, Any]:
        """Save 'wrong_type' verdict with correction.

        Args:
            session_key: Parent session key.
            preset_id: Preset ID.
            calibration_round: Current calibration round.
            page: Page number.
            element_idx: Element index.
            element_type: Agent's detected type (wrong).
            bbox: Bounding box.
            agent_detection: Agent's detection.
            correct_type: The correct element type.
            note: Optional note about the correction.

        Returns:
            Created example document.
        """
        return self.save_feedback(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=calibration_round,
            page=page,
            element_idx=element_idx,
            element_type=element_type,
            bbox=bbox,
            agent_detection=agent_detection,
            verdict="wrong_type",
            correction={"correct_type": correct_type, "note": note},
        )

    def save_split(
        self,
        session_key: str,
        preset_id: str,
        calibration_round: int,
        page: int,
        element_idx: int,
        element_type: str,
        bbox: list[float],
        agent_detection: dict[str, Any],
        split_description: str,
    ) -> dict[str, Any]:
        """Save 'split' verdict for merged elements.

        Args:
            session_key: Parent session key.
            preset_id: Preset ID.
            calibration_round: Current calibration round.
            page: Page number.
            element_idx: Element index.
            element_type: Element type.
            bbox: Bounding box.
            agent_detection: Agent's detection.
            split_description: Text description of how to split.

        Returns:
            Created example document.
        """
        return self.save_feedback(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=calibration_round,
            page=page,
            element_idx=element_idx,
            element_type=element_type,
            bbox=bbox,
            agent_detection=agent_detection,
            verdict="split",
            correction={"correct_type": element_type, "note": split_description},
        )

    def save_flagged(
        self,
        session_key: str,
        preset_id: str,
        calibration_round: int,
        page: int,
        element_idx: int,
        element_type: str,
        bbox: list[float],
        agent_detection: dict[str, Any],
        flag_reason: str,
    ) -> dict[str, Any]:
        """Save 'flagged' verdict for expert review.

        Args:
            session_key: Parent session key.
            preset_id: Preset ID.
            calibration_round: Current calibration round.
            page: Page number.
            element_idx: Element index.
            element_type: Element type.
            bbox: Bounding box.
            agent_detection: Agent's detection.
            flag_reason: Reason for flagging.

        Returns:
            Created example document.
        """
        return self.save_feedback(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=calibration_round,
            page=page,
            element_idx=element_idx,
            element_type=element_type,
            bbox=bbox,
            agent_detection=agent_detection,
            verdict="flagged",
            correction={"correct_type": None, "note": flag_reason},
        )

    def save_with_expected_csv(
        self,
        session_key: str,
        preset_id: str,
        calibration_round: int,
        page: int,
        element_idx: int,
        bbox: list[float],
        agent_detection: dict[str, Any],
        expected_csv: str,
    ) -> dict[str, Any]:
        """Save table with expected CSV output.

        Args:
            session_key: Parent session key.
            preset_id: Preset ID.
            calibration_round: Current calibration round.
            page: Page number.
            element_idx: Element index.
            bbox: Bounding box.
            agent_detection: Agent's detection.
            expected_csv: Expected CSV output for the table.

        Returns:
            Created example document.
        """
        return self.save_feedback(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=calibration_round,
            page=page,
            element_idx=element_idx,
            element_type="table",
            bbox=bbox,
            agent_detection=agent_detection,
            verdict="correct",
            expected_output={"csv": expected_csv, "format": "inline"},
        )

    def save_with_extraction_hint(
        self,
        session_key: str,
        preset_id: str,
        calibration_round: int,
        page: int,
        element_idx: int,
        element_type: str,
        bbox: list[float],
        agent_detection: dict[str, Any],
        camelot_flavor: str | None = None,
        line_scale: int | None = None,
        edge_tol: int | None = None,
    ) -> dict[str, Any]:
        """Save with extraction hint (camelot params).

        Args:
            session_key: Parent session key.
            preset_id: Preset ID.
            calibration_round: Current calibration round.
            page: Page number.
            element_idx: Element index.
            element_type: Element type.
            bbox: Bounding box.
            agent_detection: Agent's detection.
            camelot_flavor: Camelot flavor (lattice/stream).
            line_scale: Camelot line_scale parameter.
            edge_tol: Camelot edge_tol parameter.

        Returns:
            Created example document.
        """
        hint = {}
        if camelot_flavor:
            hint["camelot_flavor"] = camelot_flavor
        if line_scale is not None:
            hint["line_scale"] = line_scale
        if edge_tol is not None:
            hint["edge_tol"] = edge_tol

        return self.save_feedback(
            session_key=session_key,
            preset_id=preset_id,
            calibration_round=calibration_round,
            page=page,
            element_idx=element_idx,
            element_type=element_type,
            bbox=bbox,
            agent_detection=agent_detection,
            verdict="correct",
            extraction_hint=hint if hint else None,
        )

    def get_session_examples(
        self, session_key: str, verdict: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all examples for a session.

        Args:
            session_key: Session key.
            verdict: Optional filter by verdict.

        Returns:
            List of example documents.
        """
        examples = self.schema.list_examples(session_key=session_key)
        if verdict:
            examples = [e for e in examples if e.get("human_verdict") == verdict]
        return examples

    def get_round_accuracy(
        self, session_key: str, calibration_round: int
    ) -> tuple[int, int, float]:
        """Calculate accuracy for a calibration round.

        Args:
            session_key: Session key.
            calibration_round: Round number.

        Returns:
            Tuple of (correct_count, total_count, accuracy_percentage).
        """
        examples = self.schema.list_examples(session_key=session_key)
        round_examples = [e for e in examples if e.get("round") == calibration_round]

        if not round_examples:
            return (0, 0, 0.0)

        correct = sum(1 for e in round_examples if e.get("human_verdict") == "correct")
        total = len(round_examples)
        accuracy = correct / total if total > 0 else 0.0

        return (correct, total, accuracy * 100)

    def get_session_stats(self, session_key: str) -> dict[str, Any]:
        """Get overall session statistics for resume UX.

        Args:
            session_key: Session key.

        Returns:
            Dictionary with:
            - reviewed: Total examples reviewed
            - correct: Number marked correct
            - accuracy: Overall accuracy percentage
            - by_type: Breakdown by element type
            - current_round: Latest round number
            - last_page: Last page reviewed
            - last_element_idx: Last element index on that page
        """
        examples = self.schema.list_examples(session_key=session_key)

        if not examples:
            return {
                "reviewed": 0,
                "correct": 0,
                "accuracy": 0.0,
                "by_type": {},
                "current_round": 1,
                "last_page": None,
                "last_element_idx": None,
            }

        # Overall stats
        reviewed = len(examples)
        correct = sum(1 for e in examples if e.get("human_verdict") == "correct")
        accuracy = (correct / reviewed * 100) if reviewed > 0 else 0.0

        # By type breakdown
        by_type: dict[str, dict[str, int]] = {}
        for ex in examples:
            etype = ex.get("element_type", "unknown")
            if etype not in by_type:
                by_type[etype] = {"reviewed": 0, "correct": 0}
            by_type[etype]["reviewed"] += 1
            if ex.get("human_verdict") == "correct":
                by_type[etype]["correct"] += 1

        # Current round (max round number seen)
        current_round = max((e.get("round", 1) for e in examples), default=1)

        # Last reviewed element (for continue-from)
        sorted_examples = sorted(
            examples,
            key=lambda e: (e.get("round", 0), e.get("page", 0), e.get("element_idx", 0)),
        )
        last = sorted_examples[-1] if sorted_examples else None

        return {
            "reviewed": reviewed,
            "correct": correct,
            "accuracy": round(accuracy, 1),
            "by_type": by_type,
            "current_round": current_round,
            "last_page": last.get("page") if last else None,
            "last_element_idx": last.get("element_idx") if last else None,
        }
