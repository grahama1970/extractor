"""Pydantic models for calibration data.

These models define the structure of calibration data stored in ArangoDB:
- CalibrationSession: Tracks overall calibration progress
- CalibrationExample: Individual human-reviewed element
- LearnedPattern: Pattern learned from human feedback
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Status of a calibration session."""

    IN_PROGRESS = "in_progress"
    CONVERGED = "converged"
    ARCHIVED = "archived"


class HumanVerdict(str, Enum):
    """Human verdict on an element detection."""

    CORRECT = "correct"
    WRONG_TYPE = "wrong_type"
    NOT_ELEMENT = "not_element"
    SPLIT = "split"
    FLAGGED = "flagged"
    ADJUST_BBOX = "adjust_bbox"


class CreatedBy(str, Enum):
    """Who created an example."""

    HUMAN = "human"
    AGENT = "agent"


class Relationship(str, Enum):
    """Relationship between example and pattern."""

    CONFIRMS = "confirms"
    CONTRADICTS = "contradicts"


class AgentDetection(BaseModel):
    """Agent's detection result for an element."""

    type: str = Field(..., description="Detected element type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    reasoning: str = Field(default="", description="Agent's reasoning for detection")


class Correction(BaseModel):
    """Human correction for a misdetected element."""

    correct_type: str | None = Field(None, description="Correct element type")
    note: str = Field(default="", description="Human's note about the correction")


class ExpectedOutput(BaseModel):
    """Expected extraction output for an element."""

    csv: str | None = Field(None, description="Expected CSV for table")
    format: str = Field(default="inline", description="Output format")
    text: str | None = Field(None, description="Expected text for headers")


class ExtractionHint(BaseModel):
    """Hints for extraction parameters."""

    camelot_flavor: str | None = Field(None, description="Camelot flavor: lattice/stream")
    line_scale: int | None = Field(None, description="Camelot line_scale parameter")
    edge_tol: int | None = Field(None, description="Camelot edge_tol parameter")


class CalibrationSession(BaseModel):
    """A calibration session tracking preset refinement progress.

    Attributes:
        key: Unique identifier (e.g., "boeing-specs_2026-01-19")
        preset_id: ID of the preset being calibrated
        client: Client identifier
        pdf_path: Path to the PDF being used for calibration
        page_count: Total pages in the PDF
        status: Current session status
        accuracy_history: List of accuracy scores per round
        created_at: When session was created
        updated_at: When session was last updated
        owner: User who owns this session
    """

    key: str = Field(..., alias="_key", description="Document key")
    preset_id: str = Field(..., description="Preset being calibrated")
    client: str = Field(..., description="Client identifier")
    pdf_path: str = Field(..., description="Path to calibration PDF")
    page_count: int = Field(..., ge=1, description="Total pages in PDF")
    status: SessionStatus = Field(default=SessionStatus.IN_PROGRESS, description="Session status")
    accuracy_history: list[float] = Field(default_factory=list, description="Accuracy per round")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )
    owner: str = Field(..., description="Session owner")

    model_config = {"populate_by_name": True}

    def to_arango(self) -> dict[str, Any]:
        """Convert to ArangoDB document format."""
        data = self.model_dump(by_alias=True)
        # Convert datetime to ISO strings
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_arango(cls, doc: dict[str, Any]) -> "CalibrationSession":
        """Create from ArangoDB document."""
        # Parse ISO datetime strings
        if isinstance(doc.get("created_at"), str):
            doc["created_at"] = datetime.fromisoformat(doc["created_at"])
        if isinstance(doc.get("updated_at"), str):
            doc["updated_at"] = datetime.fromisoformat(doc["updated_at"])
        return cls(**doc)


class CalibrationExample(BaseModel):
    """A single human-reviewed calibration example.

    Attributes:
        key: Unique identifier (e.g., "boeing-specs_2026-01-19_p5_elem_3")
        session_key: Reference to parent session
        preset_id: Preset ID for quick filtering
        round: Calibration round number
        page: Page number in PDF
        element_idx: Element index on page
        element_type: Type of element (header, table, figure)
        bbox: Bounding box [x0, y0, x1, y1]
        agent_detection: Agent's detection result
        human_verdict: Human's verdict on detection
        correction: Optional correction data
        expected_output: Optional expected extraction output
        extraction_hint: Optional hints for extraction
        created_at: Creation timestamp
        created_by: Who created this example
    """

    key: str = Field(..., alias="_key", description="Document key")
    session_key: str = Field(..., description="Parent session key")
    preset_id: str = Field(..., description="Preset ID")
    round: int = Field(..., ge=1, description="Calibration round")
    page: int = Field(..., ge=0, description="Page number")
    element_idx: int = Field(..., ge=0, description="Element index")
    element_type: str = Field(..., description="Element type")
    bbox: list[float] = Field(..., min_length=4, max_length=4, description="Bounding box")
    agent_detection: AgentDetection = Field(..., description="Agent's detection")
    human_verdict: HumanVerdict | None = Field(None, description="Human verdict")
    correction: Correction | None = Field(None, description="Correction if wrong")
    expected_output: ExpectedOutput | None = Field(None, description="Expected output")
    extraction_hint: ExtractionHint | None = Field(None, description="Extraction hints")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    created_by: CreatedBy = Field(default=CreatedBy.AGENT, description="Creator")

    model_config = {"populate_by_name": True}

    def to_arango(self) -> dict[str, Any]:
        """Convert to ArangoDB document format."""
        data = self.model_dump(by_alias=True)
        data["created_at"] = self.created_at.isoformat()
        # Convert nested models
        if data.get("agent_detection"):
            data["agent_detection"] = dict(data["agent_detection"])
        if data.get("correction"):
            data["correction"] = dict(data["correction"])
        if data.get("expected_output"):
            data["expected_output"] = dict(data["expected_output"])
        if data.get("extraction_hint"):
            data["extraction_hint"] = dict(data["extraction_hint"])
        return data

    @classmethod
    def from_arango(cls, doc: dict[str, Any]) -> "CalibrationExample":
        """Create from ArangoDB document."""
        if isinstance(doc.get("created_at"), str):
            doc["created_at"] = datetime.fromisoformat(doc["created_at"])
        return cls(**doc)


class LearnedPattern(BaseModel):
    """A pattern learned from human feedback.

    Attributes:
        key: Unique identifier (e.g., "boeing-specs_header_blue_font")
        preset_id: Preset this pattern belongs to
        element_type: Type of element this pattern detects
        pattern_name: Human-readable pattern name
        stage1_regex: Stage 1 wide-net regex (optional)
        stage2_python: Stage 2 Python validation code
        stage3_prompt: Stage 3 LLM fallback prompt
        confidence: Pattern confidence score
        learned_from: List of example keys that taught this pattern
        confirmed_by_human: Whether human confirmed this pattern
        created_at: Creation timestamp
        active: Whether pattern is currently active
    """

    key: str = Field(..., alias="_key", description="Document key")
    preset_id: str = Field(..., description="Preset ID")
    element_type: str = Field(..., description="Element type")
    pattern_name: str = Field(..., description="Pattern name")
    stage1_regex: str | None = Field(None, description="Stage 1 regex")
    stage2_python: str | None = Field(None, description="Stage 2 Python code")
    stage3_prompt: str | None = Field(None, description="Stage 3 LLM prompt")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence")
    learned_from: list[str] = Field(default_factory=list, description="Source examples")
    confirmed_by_human: bool = Field(default=False, description="Human confirmed")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    active: bool = Field(default=True, description="Pattern is active")

    model_config = {"populate_by_name": True}

    def to_arango(self) -> dict[str, Any]:
        """Convert to ArangoDB document format."""
        data = self.model_dump(by_alias=True)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_arango(cls, doc: dict[str, Any]) -> "LearnedPattern":
        """Create from ArangoDB document."""
        if isinstance(doc.get("created_at"), str):
            doc["created_at"] = datetime.fromisoformat(doc["created_at"])
        return cls(**doc)


class ConfirmEdge(BaseModel):
    """Edge linking an example to a pattern.

    Attributes:
        from_example: Example document ID
        to_pattern: Pattern document ID
        relationship: Type of relationship
    """

    from_example: str = Field(..., alias="_from", description="Example document ID")
    to_pattern: str = Field(..., alias="_to", description="Pattern document ID")
    relationship: Relationship = Field(..., description="Relationship type")

    model_config = {"populate_by_name": True}

    def to_arango(self) -> dict[str, Any]:
        """Convert to ArangoDB edge document."""
        return self.model_dump(by_alias=True)
