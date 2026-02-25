"""3-stage pattern learner from human feedback.

Learns patterns from human corrections in three stages:
- Stage 1: Wide-net regex for candidate detection
- Stage 2: Python + rapidfuzz for fuzzy matching
- Stage 3: Headless LLM call for ambiguous cases

ALWAYS explains reasoning. ALWAYS confirms with human before saving.
"""

import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from extractor.pipeline.calibration.models import LearnedPattern
from extractor.pipeline.calibration.schema import CalibrationSchema


@dataclass
class LLMJudgeResult:
    """Result from Stage 3 LLM judge."""

    verdict: str  # "header", "table", "figure", "not_element"
    confidence: float
    reasoning: str
    raw_response: str | None = None


@dataclass
class PatternProposal:
    """A proposed pattern awaiting human confirmation."""

    element_type: str
    pattern_name: str
    stage1_regex: str | None
    stage2_python: str | None
    stage3_prompt: str | None
    confidence: float
    learned_from: list[str]  # Example keys
    reasoning: str  # Explanation of how pattern was learned
    sample_matches: list[str]  # Sample texts that match
    sample_non_matches: list[str]  # Sample texts that don't match


@dataclass
class LearningResult:
    """Result of pattern learning."""

    proposals: list[PatternProposal] = field(default_factory=list)
    accuracy: float = 0.0
    examples_used: int = 0
    message: str = ""


class PatternLearner:
    """Learn patterns from human feedback."""

    def __init__(self, schema: CalibrationSchema | None = None):
        """Initialize pattern learner.

        Args:
            schema: CalibrationSchema instance. Creates new one if not provided.
        """
        self.schema = schema or CalibrationSchema()
        self.schema.create_collections()

    def learn_from_session(self, session_key: str, min_examples: int = 3) -> LearningResult:
        """Learn patterns from a calibration session.

        Args:
            session_key: Session key to learn from.
            min_examples: Minimum examples needed for a pattern.

        Returns:
            LearningResult with proposed patterns.
        """
        examples = self.schema.list_examples(session_key=session_key)

        if not examples:
            return LearningResult(message="No examples found for session")

        # Group examples by element type and verdict
        positive_examples = defaultdict(list)  # Type -> correct examples
        negative_examples = defaultdict(list)  # Type -> rejected examples

        for ex in examples:
            element_type = ex.get("element_type")
            verdict = ex.get("human_verdict")

            if verdict == "correct":
                positive_examples[element_type].append(ex)
            elif verdict in ("not_element", "wrong_type"):
                negative_examples[element_type].append(ex)

        # Learn patterns for each element type
        proposals = []
        for element_type, positives in positive_examples.items():
            if len(positives) >= min_examples:
                proposal = self._learn_pattern(
                    element_type=element_type,
                    positives=positives,
                    negatives=negative_examples.get(element_type, []),
                )
                if proposal:
                    proposals.append(proposal)

        # Calculate overall accuracy
        total = len(examples)
        correct = sum(1 for ex in examples if ex.get("human_verdict") == "correct")
        accuracy = correct / total if total > 0 else 0.0

        return LearningResult(
            proposals=proposals,
            accuracy=accuracy,
            examples_used=len(examples),
            message=f"Learned {len(proposals)} patterns from {len(examples)} examples",
        )

    def _learn_pattern(
        self,
        element_type: str,
        positives: list[dict],
        negatives: list[dict],
    ) -> PatternProposal | None:
        """Learn a pattern for a specific element type.

        Args:
            element_type: Type of element.
            positives: Positive examples (correct detections).
            negatives: Negative examples (rejections).

        Returns:
            PatternProposal or None if no pattern found.
        """
        if element_type == "header":
            return self._learn_header_pattern(positives, negatives)
        elif element_type == "table":
            return self._learn_table_pattern(positives, negatives)
        elif element_type == "figure":
            return self._learn_figure_pattern(positives, negatives)
        else:
            return self._learn_generic_pattern(element_type, positives, negatives)

    def _learn_header_pattern(
        self, positives: list[dict], negatives: list[dict]
    ) -> PatternProposal:
        """Learn header detection pattern.

        Analyzes:
        - Text patterns (section numbers, keywords)
        - Font attributes (size, bold, color)
        """
        # Extract features
        texts = []

        for ex in positives:
            detection = ex.get("agent_detection", {})
            texts.append(detection.get("reasoning", ""))

            # Extract from text if available
            if "text" in ex:
                texts.append(ex["text"])

        # Analyze text patterns
        section_pattern = r"^\d+(\.\d+)*\s+"  # Default: 1.2.3 style
        keyword_pattern = None

        # Check for common patterns
        sum(1 for t in texts if re.match(r"^\d+\.", t.strip()))
        has_chapter = sum(1 for t in texts if re.match(r"^chapter\s+\d+", t.lower()))
        has_section = sum(1 for t in texts if re.match(r"^section\s+\d+", t.lower()))

        if has_chapter > len(positives) / 2:
            section_pattern = r"^Chapter\s+\d+"
            keyword_pattern = "chapter"
        elif has_section > len(positives) / 2:
            section_pattern = r"^Section\s+\d+"
            keyword_pattern = "section"

        # Build stage 2 Python validation
        stage2_code = self._generate_header_stage2(positives, negatives)

        # Build stage 3 prompt
        stage3_prompt = (
            f"Is the following text a {keyword_pattern or 'section'} header? "
            "Answer YES or NO with a brief reason.\n\nText: '{text}'"
        )

        reasoning = self._explain_header_pattern(positives, section_pattern, stage2_code)

        return PatternProposal(
            element_type="header",
            pattern_name=f"header_{keyword_pattern or 'section'}_pattern",
            stage1_regex=section_pattern,
            stage2_python=stage2_code,
            stage3_prompt=stage3_prompt,
            confidence=len(positives) / (len(positives) + len(negatives) + 1),
            learned_from=[ex.get("_key", "") for ex in positives],
            reasoning=reasoning,
            sample_matches=[
                ex.get("agent_detection", {}).get("reasoning", "")[:50] for ex in positives[:3]
            ],
            sample_non_matches=[
                ex.get("agent_detection", {}).get("reasoning", "")[:50] for ex in negatives[:3]
            ],
        )

    def _generate_header_stage2(self, positives: list[dict], negatives: list[dict]) -> str:
        """Generate Stage 2 Python validation code for headers."""
        # Analyze font attributes from examples
        font_checks = []

        # Check for size patterns
        sizes = []
        for ex in positives:
            det = ex.get("agent_detection", {})
            if "size" in det.get("reasoning", "").lower():
                # Try to extract size from reasoning
                match = re.search(r"(\d+)\s*pt", det.get("reasoning", ""))
                if match:
                    sizes.append(int(match.group(1)))

        if sizes:
            min_size = min(sizes)
            font_checks.append(f"font_info.get('size', 0) >= {min_size}")

        # Check for bold
        bold_count = sum(
            1
            for ex in positives
            if "bold" in ex.get("agent_detection", {}).get("reasoning", "").lower()
        )
        if bold_count > len(positives) / 2:
            font_checks.append("font_info.get('is_bold', False)")

        if font_checks:
            checks = " and ".join(font_checks)
            return f"""def validate(text, font_info):
    '''Stage 2 validation for header.'''
    if not ({checks}):
        return False
    return True
"""
        return """def validate(text, font_info):
    '''Stage 2 validation for header.'''
    return True  # No specific font checks learned
"""

    def _explain_header_pattern(self, positives: list[dict], regex: str, stage2: str) -> str:
        """Generate explanation of learned header pattern."""
        reasons = [
            f"Learned from {len(positives)} confirmed header examples.",
            f"Stage 1 regex pattern: {regex}",
        ]

        if "size" in stage2:
            reasons.append("Headers have specific minimum font size.")
        if "bold" in stage2:
            reasons.append("Headers are typically bold.")

        return " ".join(reasons)

    def _learn_table_pattern(self, positives: list[dict], negatives: list[dict]) -> PatternProposal:
        """Learn table extraction pattern (camelot params)."""
        # Analyze extraction hints
        flavors = Counter()
        line_scales = []
        edge_tols = []

        for ex in positives:
            hint = ex.get("extraction_hint", {})
            if hint:
                if hint.get("camelot_flavor"):
                    flavors[hint["camelot_flavor"]] += 1
                if hint.get("line_scale") is not None:
                    line_scales.append(hint["line_scale"])
                if hint.get("edge_tol") is not None:
                    edge_tols.append(hint["edge_tol"])

        # Determine best flavor
        best_flavor = flavors.most_common(1)[0][0] if flavors else "lattice"
        avg_line_scale = int(sum(line_scales) / len(line_scales)) if line_scales else 40
        avg_edge_tol = int(sum(edge_tols) / len(edge_tols)) if edge_tols else 500

        # Check for bordered vs borderless from metadata
        has_borders_count = sum(
            1
            for ex in positives
            if ex.get("agent_detection", {}).get("metadata", {}).get("has_borders", False)
        )
        is_bordered = has_borders_count > len(positives) / 2

        stage2_code = f"""def validate(table_data, page_context):
    '''Stage 2 validation for table.'''
    params = {{
        'flavor': '{best_flavor}',
        'line_scale': {avg_line_scale},
    }}
    if '{best_flavor}' == 'stream':
        params['edge_tol'] = {avg_edge_tol}
    return params
"""

        reasoning = (
            f"Learned from {len(positives)} confirmed table examples. "
            f"Best extraction: {best_flavor} flavor"
            f"{f', line_scale={avg_line_scale}' if line_scales else ''}"
            f"{f', edge_tol={avg_edge_tol}' if edge_tols else ''}. "
            f"{'Tables have visible borders.' if is_bordered else 'Tables are borderless.'}"
        )

        return PatternProposal(
            element_type="table",
            pattern_name=f"table_{'bordered' if is_bordered else 'borderless'}_pattern",
            stage1_regex=None,  # Tables detected by structure, not regex
            stage2_python=stage2_code,
            stage3_prompt="Is this a data table? Answer YES or NO.",
            confidence=len(positives) / (len(positives) + len(negatives) + 1),
            learned_from=[ex.get("_key", "") for ex in positives],
            reasoning=reasoning,
            sample_matches=[],
            sample_non_matches=[],
        )

    def _learn_figure_pattern(
        self, positives: list[dict], negatives: list[dict]
    ) -> PatternProposal:
        """Learn figure detection pattern."""
        # Check for caption patterns
        caption_patterns = []

        for ex in positives:
            text = ex.get("agent_detection", {}).get("reasoning", "")
            if "figure" in text.lower():
                caption_patterns.append("Figure")
            if "diagram" in text.lower():
                caption_patterns.append("Diagram")
            if "image" in text.lower():
                caption_patterns.append("Image")

        # Build caption regex
        if caption_patterns:
            unique_patterns = list(set(caption_patterns))
            caption_regex = rf"^({'|'.join(unique_patterns)})\s*\d*"
        else:
            caption_regex = r"^(Figure|Fig\.?|Diagram|Image)\s*\d*"

        stage2_code = """def validate(figure_data, page_context):
    '''Stage 2 validation for figure.'''
    # Check if has caption
    has_caption = figure_data.get('has_caption', False)
    return has_caption or figure_data.get('confidence', 0) > 0.8
"""

        reasoning = (
            f"Learned from {len(positives)} confirmed figure examples. "
            f"Caption pattern: {caption_regex}"
        )

        return PatternProposal(
            element_type="figure",
            pattern_name="figure_with_caption_pattern",
            stage1_regex=caption_regex,
            stage2_python=stage2_code,
            stage3_prompt="Is this an image/figure with a caption? Answer YES or NO.",
            confidence=len(positives) / (len(positives) + len(negatives) + 1),
            learned_from=[ex.get("_key", "") for ex in positives],
            reasoning=reasoning,
            sample_matches=[],
            sample_non_matches=[],
        )

    def _learn_generic_pattern(
        self, element_type: str, positives: list[dict], negatives: list[dict]
    ) -> PatternProposal:
        """Learn pattern for generic element type."""
        reasoning = f"Learned from {len(positives)} confirmed {element_type} examples."

        return PatternProposal(
            element_type=element_type,
            pattern_name=f"{element_type}_generic_pattern",
            stage1_regex=None,
            stage2_python="""def validate(element_data, page_context):
    '''Generic validation.'''
    return True
""",
            stage3_prompt=f"Is this a {element_type}? Answer YES or NO.",
            confidence=len(positives) / (len(positives) + len(negatives) + 1),
            learned_from=[ex.get("_key", "") for ex in positives],
            reasoning=reasoning,
            sample_matches=[],
            sample_non_matches=[],
        )

    def confirm_and_save_pattern(self, proposal: PatternProposal, preset_id: str) -> dict[str, Any]:
        """Save a confirmed pattern to ArangoDB.

        Args:
            proposal: PatternProposal that was confirmed by human.
            preset_id: Preset ID this pattern belongs to.

        Returns:
            Created pattern document.
        """
        # Generate unique key
        key = f"{preset_id}_{proposal.pattern_name}"

        # Check if pattern exists - update if so
        existing = self.schema.get_pattern(key)
        if existing:
            # Update existing pattern
            return self.schema.update_pattern(
                key,
                {
                    "stage1_regex": proposal.stage1_regex,
                    "stage2_python": proposal.stage2_python,
                    "stage3_prompt": proposal.stage3_prompt,
                    "confidence": proposal.confidence,
                    "learned_from": proposal.learned_from,
                    "confirmed_by_human": True,
                },
            )

        # Create new pattern
        pattern = LearnedPattern(
            _key=key,
            preset_id=preset_id,
            element_type=proposal.element_type,
            pattern_name=proposal.pattern_name,
            stage1_regex=proposal.stage1_regex,
            stage2_python=proposal.stage2_python,
            stage3_prompt=proposal.stage3_prompt,
            confidence=proposal.confidence,
            learned_from=proposal.learned_from,
            confirmed_by_human=True,
            created_at=datetime.now(timezone.utc),
            active=True,
        )

        result = self.schema.create_pattern(pattern.to_arango())

        # Create edges linking examples to pattern
        for example_key in proposal.learned_from:
            if example_key:
                self.schema.create_confirm_edge(
                    example_key=example_key,
                    pattern_key=key,
                    relationship="confirms",
                )

        return result

    def get_active_patterns(self, preset_id: str) -> list[dict[str, Any]]:
        """Get all active patterns for a preset.

        Args:
            preset_id: Preset ID.

        Returns:
            List of active pattern documents.
        """
        return self.schema.list_patterns(preset_id=preset_id, active_only=True)

    def should_propose_pattern(
        self, session_key: str, element_type: str, threshold: int = 5
    ) -> bool:
        """Check if we should propose a pattern for this element type.

        Args:
            session_key: Session key.
            element_type: Element type to check.
            threshold: Minimum verdicts before proposing.

        Returns:
            True if threshold met and no pattern proposed yet.
        """
        examples = self.schema.list_examples(session_key=session_key)

        # Count correct verdicts for this type
        correct_count = sum(
            1
            for ex in examples
            if ex.get("element_type") == element_type and ex.get("human_verdict") == "correct"
        )

        # Check if we already have an active pattern for this type
        session = self.schema.get_session(session_key)
        if session:
            preset_id = session.get("preset_id", session_key)
            patterns = self.get_active_patterns(preset_id)
            has_pattern = any(p.get("element_type") == element_type for p in patterns)
            if has_pattern:
                return False

        return correct_count >= threshold

    def format_pattern_proposal(self, proposal: PatternProposal) -> str:
        """Format a pattern proposal for conversational presentation.

        Args:
            proposal: Pattern proposal to format.

        Returns:
            Human-readable pattern proposal string.
        """
        lines = [
            f"I've noticed a pattern for {proposal.element_type.title()}s in this document:",
            "",
        ]

        # Add pattern details based on element type
        if proposal.element_type == "header":
            if proposal.stage1_regex:
                lines.append(f"- Text pattern: Matches `{proposal.stage1_regex}`")
            if proposal.stage2_python and "size" in proposal.stage2_python:
                match = re.search(r"size.*>=\s*(\d+)", proposal.stage2_python)
                if match:
                    lines.append(f"- Font size: >= {match.group(1)}pt")
            if proposal.stage2_python and "is_bold" in proposal.stage2_python:
                lines.append("- Style: Bold text")

        elif proposal.element_type == "table":
            if "lattice" in (proposal.stage2_python or ""):
                lines.append("- Detection: Grid lines / bordered table")
            elif "stream" in (proposal.stage2_python or ""):
                lines.append("- Detection: Whitespace-separated columns")

        elif proposal.element_type == "figure":
            if proposal.stage1_regex:
                lines.append(f"- Caption pattern: Matches `{proposal.stage1_regex}`")

        # Add confidence
        lines.append(f"- Confidence: {proposal.confidence * 100:.0f}%")
        lines.append(f"- Based on: {len(proposal.learned_from)} examples")

        lines.append("")
        lines.append("Should I use this pattern? (yes/no/refine)")

        return "\n".join(lines)

    def apply_human_refinement(self, proposal: PatternProposal, refinement: str) -> PatternProposal:
        """Apply human refinement to a pattern proposal.

        Args:
            proposal: Original pattern proposal.
            refinement: Human refinement text.

        Returns:
            Updated pattern proposal.
        """
        # Add refinement to reasoning
        proposal.reasoning += f" Human refinement: {refinement}"

        # Try to extract specific constraints from refinement
        refinement_lower = refinement.lower()

        # Check for position constraints (start of line)
        if re.search(r"start\s+of\s+(a\s+)?line", refinement_lower):
            if proposal.stage1_regex and not proposal.stage1_regex.startswith("^"):
                proposal.stage1_regex = "^" + proposal.stage1_regex

        # Check for size constraints
        size_match = re.search(r"(\d+)\s*pt", refinement_lower)
        if size_match:
            new_size = size_match.group(1)
            if proposal.stage2_python:
                # Update size in stage2 python
                proposal.stage2_python = re.sub(
                    r"size.*>=\s*\d+",
                    f"size', 0) >= {new_size}",
                    proposal.stage2_python,
                )

        # Check for "only if" conditions
        if "only if" in refinement_lower or "must" in refinement_lower:
            proposal.stage3_prompt = proposal.stage3_prompt.rstrip(".") + f". Note: {refinement}"

        return proposal

    def get_pattern_summary(self, session_key: str) -> str:
        """Get a human-readable summary of learned patterns.

        Used when human asks "what have you learned?" or "show patterns".

        Args:
            session_key: Session key to summarize.

        Returns:
            Formatted string summary of learned patterns.
        """
        session = self.schema.get_session(session_key)
        if not session:
            return "No session found."

        preset_id = session.get("preset_id", session_key)
        patterns = self.get_active_patterns(preset_id)

        if not patterns:
            return "No patterns learned yet. Keep reviewing elements!"

        # Get example counts and accuracy per type
        examples = self.schema.list_examples(session_key=session_key)
        type_stats: dict[str, dict] = {}

        for ex in examples:
            elem_type = ex.get("element_type", "unknown")
            verdict = ex.get("human_verdict", "")

            if elem_type not in type_stats:
                type_stats[elem_type] = {"total": 0, "correct": 0}

            type_stats[elem_type]["total"] += 1
            if verdict == "correct":
                type_stats[elem_type]["correct"] += 1

        # Build summary
        lines = [
            f"Learned patterns for {preset_id}:",
            "",
        ]

        for i, pattern in enumerate(patterns, 1):
            elem_type = pattern.get("element_type", "unknown")
            stats = type_stats.get(elem_type, {"total": 0, "correct": 0})
            accuracy = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0

            lines.append(
                f"{i}. {elem_type.title()}s ({stats['total']} examples, {accuracy:.0f}% accuracy)"
            )

            # Add pattern details
            if pattern.get("stage1_regex"):
                lines.append(f"   - Pattern: `{pattern['stage1_regex']}`")
            if pattern.get("stage2_python"):
                # Extract key validation criteria
                stage2 = pattern["stage2_python"]
                if "size" in stage2:
                    match = re.search(r"size.*>=\s*(\d+)", stage2)
                    if match:
                        lines.append(f"   - Font size: >= {match.group(1)}pt")
                if "is_bold" in stage2:
                    lines.append("   - Style: Bold")
                if "flavor" in stage2:
                    match = re.search(r"flavor.*?'(\w+)'", stage2)
                    if match:
                        lines.append(f"   - Extraction: {match.group(1)} mode")

            lines.append("")

        return "\n".join(lines)

    async def stage3_llm_judge(
        self,
        element_text: str,
        element_type: str,
        confidence: float,
        reasoning: str,
        context: str | None = None,
    ) -> LLMJudgeResult:
        """Get Stage 3 LLM judgment for ambiguous elements.

        Used when confidence is low (<0.7) or patterns conflict.

        Args:
            element_text: Text content of the element.
            element_type: Detected element type.
            confidence: Agent's confidence in the detection.
            reasoning: Agent's reasoning for the detection.
            context: Optional page context.

        Returns:
            LLMJudgeResult with verdict and reasoning.
        """
        try:
            from scillm import acompletion
        except ImportError:
            return LLMJudgeResult(
                verdict=element_type,
                confidence=confidence,
                reasoning="LLM judge unavailable (scillm not installed)",
            )

        # Build prompt
        prompt = f"""You are an expert document analyst. Evaluate whether this text is correctly classified.

Element Classification:
- Detected as: {element_type}
- Confidence: {confidence * 100:.0f}%
- Agent's reasoning: {reasoning}

Text content:
"{element_text[:500]}"

{f"Page context: {context[:200]}" if context else ""}

Question: Is this correctly classified as a {element_type}?

Respond in JSON format:
{{
    "verdict": "header" | "table" | "figure" | "not_element",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

        try:
            # Get API configuration
            api_base = os.environ.get("CHUTES_API_BASE") or os.environ.get("OPENROUTER_API_BASE")
            api_key = os.environ.get("CHUTES_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
            model = os.environ.get("CHUTES_MODEL_ID", "anthropic/claude-3-haiku")

            if not api_key:
                return LLMJudgeResult(
                    verdict=element_type,
                    confidence=confidence,
                    reasoning="LLM judge unavailable (no API key configured)",
                )

            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                api_base=api_base,
                api_key=api_key,
                response_format={"type": "json_object"},
                timeout=30,
            )

            content = response.choices[0].message.content
            import json

            result = json.loads(content)

            return LLMJudgeResult(
                verdict=result.get("verdict", element_type),
                confidence=result.get("confidence", confidence),
                reasoning=result.get("reasoning", "No reasoning provided"),
                raw_response=content,
            )

        except Exception as e:
            return LLMJudgeResult(
                verdict=element_type,
                confidence=confidence,
                reasoning=f"LLM judge error: {str(e)}",
            )

    def should_use_llm_judge(self, confidence: float, threshold: float = 0.7) -> bool:
        """Check if LLM judge should be invoked.

        Args:
            confidence: Agent's confidence in detection.
            threshold: Confidence threshold below which to use LLM.

        Returns:
            True if LLM judge should be used.
        """
        return confidence < threshold

    def format_llm_judge_result(
        self, agent_type: str, agent_reasoning: str, llm_result: LLMJudgeResult
    ) -> str:
        """Format LLM judge result for conversation.

        Shows both agent and LLM reasoning for human to make final call.

        Args:
            agent_type: Agent's detected type.
            agent_reasoning: Agent's reasoning.
            llm_result: LLM judge result.

        Returns:
            Formatted string for conversation.
        """
        lines = [
            "Low confidence detection - here's what both analyses show:",
            "",
            "**Agent Analysis:**",
            f"- Type: {agent_type}",
            f"- Reasoning: {agent_reasoning}",
            "",
            "**LLM Judge Analysis:**",
            f"- Type: {llm_result.verdict}",
            f"- Confidence: {llm_result.confidence * 100:.0f}%",
            f"- Reasoning: {llm_result.reasoning}",
            "",
            "What's your verdict?",
        ]
        return "\n".join(lines)
