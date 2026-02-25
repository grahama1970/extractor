"""Relation annotation for calibration via TUI conversation.

Supports annotating relationships between elements:
- parent_child: Header → SubHeader hierarchy
- caption_of: Caption → Figure/Table
- references: Text mention → Figure/Table
- continues: Element continues from previous page
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from extractor.pipeline.calibration.schema import CalibrationSchema


class RelationType(str, Enum):
    """Types of relations between elements."""

    PARENT_CHILD = "parent_child"  # Header contains SubHeader
    CAPTION_OF = "caption_of"  # Caption describes Figure/Table
    REFERENCES = "references"  # Text mentions Figure/Table
    CONTINUES = "continues"  # Element continues from previous page
    RELATED = "related"  # General semantic relationship


@dataclass
class RelationProposal:
    """A proposed relation awaiting human confirmation."""

    relation_type: RelationType
    source_element: dict[str, Any]  # Element that "owns" the relation
    target_element: dict[str, Any]  # Element being related to
    confidence: float
    reasoning: str
    proposal_id: str = ""

    def format_question(self) -> str:
        """Format as a question for human confirmation."""
        source_desc = self._describe_element(self.source_element)
        target_desc = self._describe_element(self.target_element)

        if self.relation_type == RelationType.PARENT_CHILD:
            return (
                f"Should '{target_desc}' be a child of '{source_desc}'?\n"
                f"Reasoning: {self.reasoning}\n"
                f"(yes/no/skip)"
            )
        elif self.relation_type == RelationType.CAPTION_OF:
            return (
                f"Is '{source_desc}' a caption for {target_desc}?\n"
                f"Reasoning: {self.reasoning}\n"
                f"(yes/no/skip)"
            )
        elif self.relation_type == RelationType.REFERENCES:
            return (
                f"Does '{source_desc}' reference {target_desc}?\n"
                f"Reasoning: {self.reasoning}\n"
                f"(yes/no/skip)"
            )
        elif self.relation_type == RelationType.CONTINUES:
            return (
                f"Does '{target_desc}' continue from '{source_desc}'?\n"
                f"Reasoning: {self.reasoning}\n"
                f"(yes/no/skip)"
            )
        else:
            return (
                f"Are '{source_desc}' and '{target_desc}' related?\n"
                f"Reasoning: {self.reasoning}\n"
                f"(yes/no/skip)"
            )

    def _describe_element(self, elem: dict[str, Any]) -> str:
        """Create a short description of an element."""
        elem_type = elem.get("element_type", "element")
        text = elem.get("text", elem.get("text_preview", ""))
        if text:
            text = text[:40] + ("..." if len(text) > 40 else "")
            return f"{elem_type}: '{text}'"
        return f"{elem_type} on page {elem.get('page_num', '?')}"


@dataclass
class AnnotatedRelation:
    """A confirmed relation between two elements."""

    relation_type: RelationType
    source_id: str  # Element ID
    target_id: str  # Element ID
    confirmed_by: str = "human"  # "human" or "auto"
    confidence: float = 1.0
    note: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RelationDetector:
    """Detect and propose relations between elements."""

    def __init__(self):
        """Initialize relation detector."""
        # Patterns for detecting section numbering
        self.section_pattern = re.compile(r"^(\d+(?:\.\d+)*)\s*[.:]?\s*(.*)$")
        # Patterns for caption detection
        self.caption_patterns = [
            re.compile(r"^(Figure|Fig\.?|Table|Tab\.?)\s*(\d+(?:\.\d+)?)", re.I),
            re.compile(r"^(Diagram|Image|Chart)\s*(\d+(?:\.\d+)?)", re.I),
        ]

    def propose_relations(
        self,
        elements: list[dict[str, Any]],
        max_proposals: int = 10,
    ) -> list[RelationProposal]:
        """Propose relations between elements.

        Args:
            elements: List of detected elements (as dicts).
            max_proposals: Maximum number of proposals to return.

        Returns:
            List of relation proposals.
        """
        proposals = []

        # Group elements by type
        headers = [e for e in elements if e.get("element_type") == "header"]
        tables = [e for e in elements if e.get("element_type") == "table"]
        figures = [e for e in elements if e.get("element_type") == "figure"]
        text_blocks = [e for e in elements if e.get("element_type") == "text"]

        # 1. Propose parent-child relations for headers
        proposals.extend(self._propose_header_hierarchy(headers))

        # 2. Propose caption-of relations
        proposals.extend(self._propose_caption_relations(elements, tables, figures))

        # 3. Propose reference relations (text mentioning figures/tables)
        proposals.extend(self._propose_reference_relations(text_blocks, tables, figures))

        # Sort by confidence and limit
        proposals.sort(key=lambda p: p.confidence, reverse=True)
        return proposals[:max_proposals]

    def _propose_header_hierarchy(self, headers: list[dict[str, Any]]) -> list[RelationProposal]:
        """Propose parent-child relations between headers based on numbering."""
        proposals = []

        # Extract section numbers
        numbered_headers = []
        for h in headers:
            text = h.get("text", "")
            match = self.section_pattern.match(text.strip())
            if match:
                number = match.group(1)
                title = match.group(2)
                parts = number.split(".")
                numbered_headers.append(
                    {"element": h, "number": number, "parts": parts, "title": title}
                )

        # Find parent-child relationships
        for i, child in enumerate(numbered_headers):
            child_parts = child["parts"]
            if len(child_parts) <= 1:
                continue  # Top-level, no parent

            # Look for parent (one level up)
            parent_number = ".".join(child_parts[:-1])
            for parent in numbered_headers:
                if parent["number"] == parent_number:
                    proposals.append(
                        RelationProposal(
                            relation_type=RelationType.PARENT_CHILD,
                            source_element=parent["element"],
                            target_element=child["element"],
                            confidence=0.9,
                            reasoning=f"Section {child['number']} appears to be a subsection of {parent_number}",
                            proposal_id=f"rel_{parent['number']}_{child['number']}",
                        )
                    )
                    break

        return proposals

    def _propose_caption_relations(
        self,
        all_elements: list[dict[str, Any]],
        tables: list[dict[str, Any]],
        figures: list[dict[str, Any]],
    ) -> list[RelationProposal]:
        """Propose caption-of relations between text and figures/tables."""
        proposals = []

        for elem in all_elements:
            text = elem.get("text", "")
            if not text:
                continue

            # Check if this looks like a caption
            for pattern in self.caption_patterns:
                match = pattern.match(text.strip())
                if match:
                    caption_type = match.group(1).lower()
                    caption_num = match.group(2)

                    # Find the corresponding figure/table
                    targets = figures if "fig" in caption_type else tables
                    if not targets:
                        targets = figures + tables

                    # Find nearest target on same page
                    elem_page = elem.get("page_num", 0)
                    elem_bbox = elem.get("bbox", [0, 0, 0, 0])

                    best_target = None
                    best_distance = float("inf")

                    for target in targets:
                        if target.get("page_num", 0) != elem_page:
                            continue
                        target_bbox = target.get("bbox", [0, 0, 0, 0])
                        # Distance from caption to target (vertical)
                        # Handle caption above or below the figure/table
                        dist_above = abs(
                            target_bbox[1] - elem_bbox[3]
                        )  # Caption above: caption bottom to figure top
                        dist_below = abs(
                            elem_bbox[1] - target_bbox[3]
                        )  # Caption below: figure bottom to caption top
                        dist = min(dist_above, dist_below)
                        if dist < best_distance:
                            best_distance = dist
                            best_target = target

                    if best_target and best_distance < 100:  # Within 100 points
                        proposals.append(
                            RelationProposal(
                                relation_type=RelationType.CAPTION_OF,
                                source_element=elem,
                                target_element=best_target,
                                confidence=0.85,
                                reasoning=f"Text starts with '{caption_type.title()} {caption_num}' near a {best_target.get('element_type')}",
                                proposal_id=f"caption_{elem.get('element_idx', 0)}_{best_target.get('element_idx', 0)}",
                            )
                        )
                    break

        return proposals

    def _propose_reference_relations(
        self,
        text_blocks: list[dict[str, Any]],
        tables: list[dict[str, Any]],
        figures: list[dict[str, Any]],
    ) -> list[RelationProposal]:
        """Propose reference relations (text mentioning figures/tables)."""
        proposals = []

        # Patterns for in-text references
        ref_patterns = [
            re.compile(r"(Figure|Fig\.?)\s*(\d+(?:\.\d+)?)", re.I),
            re.compile(r"(Table|Tab\.?)\s*(\d+(?:\.\d+)?)", re.I),
            re.compile(r"see\s+(Figure|Fig\.?|Table|Tab\.?)\s*(\d+)", re.I),
        ]

        for text_elem in text_blocks:
            text = text_elem.get("text", "")
            if not text:
                continue

            for pattern in ref_patterns:
                matches = pattern.findall(text)
                for match in matches:
                    ref_type = match[0].lower()
                    ref_num = match[1]

                    # Find the referenced element
                    targets = figures if "fig" in ref_type else tables

                    for target in targets:
                        # Simple heuristic: check if target has matching number in metadata
                        target_text = target.get("text", "")
                        if (
                            ref_num in target_text
                            or f"{ref_type} {ref_num}".lower() in target_text.lower()
                        ):
                            proposals.append(
                                RelationProposal(
                                    relation_type=RelationType.REFERENCES,
                                    source_element=text_elem,
                                    target_element=target,
                                    confidence=0.7,
                                    reasoning=f"Text mentions '{ref_type.title()} {ref_num}'",
                                    proposal_id=f"ref_{text_elem.get('element_idx', 0)}_{target.get('element_idx', 0)}",
                                )
                            )
                            break

        return proposals


class RelationHandler:
    """Handle relation annotations and storage."""

    def __init__(self, schema: CalibrationSchema | None = None):
        """Initialize relation handler.

        Args:
            schema: CalibrationSchema instance. Creates new one if not provided.
        """
        self.schema = schema or CalibrationSchema()
        self._ensure_collection()

    def _ensure_collection(self):
        """Ensure the relations collection exists."""
        try:
            if not self.schema.db.has_collection("calibration_relations"):
                self.schema.db.create_collection("calibration_relations")
        except Exception:
            pass  # Collection might already exist

    def save_relation(
        self,
        session_key: str,
        relation: AnnotatedRelation,
    ) -> str:
        """Save an annotated relation.

        Args:
            session_key: Session this relation belongs to.
            relation: The annotated relation.

        Returns:
            Key of the saved relation document.
        """
        doc = {
            "session_key": session_key,
            "relation_type": relation.relation_type.value,
            "source_id": relation.source_id,
            "target_id": relation.target_id,
            "confirmed_by": relation.confirmed_by,
            "confidence": relation.confidence,
            "note": relation.note,
            "created_at": relation.created_at,
        }

        coll = self.schema.db.collection("calibration_relations")
        result = coll.insert(doc)
        return result["_key"]

    def get_session_relations(self, session_key: str) -> list[dict[str, Any]]:
        """Get all relations for a session.

        Args:
            session_key: Session to get relations for.

        Returns:
            List of relation documents.
        """
        try:
            coll = self.schema.db.collection("calibration_relations")
            cursor = coll.find({"session_key": session_key})
            return list(cursor)
        except Exception:
            return []

    def get_relation_stats(self, session_key: str) -> dict[str, int]:
        """Get relation statistics for a session.

        Args:
            session_key: Session to get stats for.

        Returns:
            Dict mapping relation type to count.
        """
        relations = self.get_session_relations(session_key)
        stats: dict[str, int] = {}
        for r in relations:
            rtype = r.get("relation_type", "unknown")
            stats[rtype] = stats.get(rtype, 0) + 1
        return stats


def parse_relation_response(response: str) -> tuple[str, str | None]:
    """Parse human response to relation proposal.

    Args:
        response: Natural language response.

    Returns:
        Tuple of (verdict, note) where verdict is "yes", "no", or "skip".
    """
    response = response.lower().strip()

    # Yes patterns
    yes_patterns = [
        r"^y(es)?$",
        r"^correct$",
        r"^right$",
        r"^confirm",
        r"^that'?s right",
        r"^looks good",
        r"^accept",
    ]
    for pattern in yes_patterns:
        if re.match(pattern, response):
            return ("yes", None)

    # No patterns
    no_patterns = [
        r"^n(o)?$",
        r"^wrong",
        r"^incorrect",
        r"^not related",
        r"^reject",
        r"^they'?re not",
    ]
    for pattern in no_patterns:
        if re.match(pattern, response):
            return ("no", None)

    # Skip patterns
    skip_patterns = [
        r"^skip",
        r"^pass",
        r"^unsure",
        r"^don'?t know",
        r"^not sure",
        r"^maybe",
    ]
    for pattern in skip_patterns:
        if re.match(pattern, response):
            return ("skip", None)

    # Check for note
    if response.startswith("yes,") or response.startswith("yes "):
        return ("yes", response[4:].strip())
    if response.startswith("no,") or response.startswith("no "):
        return ("no", response[3:].strip())

    # Default to skip for unclear responses
    return ("skip", f"Unclear response: {response}")


def format_relation_summary(relations: list[dict[str, Any]]) -> str:
    """Format relation summary for display.

    Args:
        relations: List of relation documents.

    Returns:
        Formatted summary string.
    """
    if not relations:
        return "No relations annotated yet."

    lines = ["## Annotated Relations", ""]

    # Group by type
    by_type: dict[str, list[dict]] = {}
    for r in relations:
        rtype = r.get("relation_type", "unknown")
        by_type.setdefault(rtype, []).append(r)

    for rtype, rels in sorted(by_type.items()):
        lines.append(f"### {rtype.replace('_', ' ').title()} ({len(rels)})")
        for r in rels[:5]:  # Show first 5
            source = r.get("source_id", "?")
            target = r.get("target_id", "?")
            lines.append(f"  - {source} → {target}")
        if len(rels) > 5:
            lines.append(f"  - ... and {len(rels) - 5} more")
        lines.append("")

    return "\n".join(lines)
