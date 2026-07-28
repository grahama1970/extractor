"""
Agent-first PDF extraction API — designed for project-agent-in-the-loop processing.

The key insight: deterministic PDF extraction is impossible. This module provides
the fast Rust substrate (via pdf_oxide) and emits structured results WITH confidence
scores so the project agent (/pdf-lab, /learn-datalake, /review-pdf) can reason
over extraction results and converge.

Cascade: heuristic → classifier → agent → human

Usage:
    from extractor.pipeline.utils.pdf_agentic import AgentAwareExtractor
    from extractor.pipeline.utils.pdf_backend import open_pdf

    with open_pdf("doc.pdf") as doc:
        extractor = AgentAwareExtractor(doc)
        result = extractor.extract_document()

        # What needs the agent's attention?
        work_items = extractor.get_agent_work_items()
        for item in work_items:
            print(f"Page {item['page_num']}: {item['field']} needs attention")
            print(f"  Confidence: {item['confidence']}")
            print(f"  Suggested skills: {item['suggested_skills']}")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from extractor.pipeline.utils.pdf_backend import BackendDoc, Rect


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    """Single extraction result with confidence and provenance.

    Every extracted value carries metadata about HOW it was extracted,
    how confident we are, and whether the agent or human should review it.
    """

    value: Any
    confidence: float
    extractor: str  # "heuristic" | "classifier" | "agent" | "human"
    needs_agent: bool  # confidence < 0.70 → agent should decide
    needs_human: bool  # confidence < 0.50 → park for /interview
    page_num: int
    bbox: Optional[Rect] = None
    corrections: list[dict] = field(default_factory=list)
    skill_used: Optional[str] = None  # which skill resolved this

    def apply_correction(
        self,
        new_value: Any,
        *,
        skill_used: str,
        confidence: float,
        corrector: str = "agent",
    ):
        """Record a correction with full provenance chain."""
        self.corrections.append({
            "type": f"{corrector}_correction",
            "skill": skill_used,
            "original": self.value,
            "new_value": new_value,
            "original_confidence": self.confidence,
            "new_confidence": confidence,
            "timestamp": time.time(),
        })
        self.value = new_value
        self.confidence = confidence
        self.extractor = corrector
        self.skill_used = skill_used
        self.needs_agent = confidence < 0.70
        self.needs_human = confidence < 0.50

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "extractor": self.extractor,
            "needs_agent": self.needs_agent,
            "needs_human": self.needs_human,
            "page_num": self.page_num,
            "bbox": self.bbox.as_tuple() if self.bbox else None,
            "corrections": self.corrections,
            "skill_used": self.skill_used,
        }


@dataclass
class PageExtractionResult:
    """All extraction results for a single page."""

    page_num: int
    text: Optional[ExtractionResult] = None
    table_strategy: Optional[ExtractionResult] = None
    tables: list[ExtractionResult] = field(default_factory=list)
    figures: list[ExtractionResult] = field(default_factory=list)
    sections: list[ExtractionResult] = field(default_factory=list)
    annotations: list[ExtractionResult] = field(default_factory=list)

    def fields(self):
        """Iterate over all non-None extraction results as (name, result) pairs."""
        if self.text:
            yield "text", self.text
        if self.table_strategy:
            yield "table_strategy", self.table_strategy
        for i, t in enumerate(self.tables):
            yield f"table_{i}", t
        for i, f in enumerate(self.figures):
            yield f"figure_{i}", f
        for i, s in enumerate(self.sections):
            yield f"section_{i}", s
        for i, a in enumerate(self.annotations):
            yield f"annotation_{i}", a

    def get_field(self, name: str) -> Optional[ExtractionResult]:
        """Get a specific field by name."""
        if name == "text":
            return self.text
        if name == "table_strategy":
            return self.table_strategy
        if name.startswith("table_"):
            idx = int(name.split("_")[1])
            return self.tables[idx] if idx < len(self.tables) else None
        if name.startswith("figure_"):
            idx = int(name.split("_")[1])
            return self.figures[idx] if idx < len(self.figures) else None
        if name.startswith("section_"):
            idx = int(name.split("_")[1])
            return self.sections[idx] if idx < len(self.sections) else None
        if name.startswith("annotation_"):
            idx = int(name.split("_")[1])
            return self.annotations[idx] if idx < len(self.annotations) else None
        return None


# ---------------------------------------------------------------------------
# Classifier interface (loads ONNX via pdf_oxide or falls back to sklearn)
# ---------------------------------------------------------------------------

class ClassifierRouter:
    """Routes classification requests through the best available backend.

    Priority: Rust ONNX (pdf_oxide) → /assistant HTTP → Python sklearn fallback.
    """

    def __init__(self):
        """Perform init operation."""
        self._rust_available = False
        self._sklearn_models: dict[str, Any] = {}
        self._probe_rust()

    def _probe_rust(self):
        """Check if pdf_oxide has ONNX classifiers compiled in."""
        try:
            import pdf_oxide
            # Check if ml module exists (Phase 3 deliverable)
            self._rust_available = hasattr(pdf_oxide, "TableStrategyClassifier")
        except ImportError:
            self._rust_available = False

    def classify_table_strategy(self, features: list[float]) -> tuple[str, float]:
        """Classify table extraction strategy from 21 features.

        Returns (strategy_name, confidence).
        """
        if self._rust_available:
            import pdf_oxide
            clf = pdf_oxide.TableStrategyClassifier()
            return clf.predict(features)

        # Sklearn fallback
        return self._sklearn_classify("table-strategy", features, n_features=21)

    def classify_merge(self, features: list[float]) -> tuple[str, float]:
        """Classify cross-page table merge decision from 8 features."""
        if self._rust_available:
            import pdf_oxide
            clf = pdf_oxide.MergeClassifier()
            return clf.predict(features)
        return self._sklearn_classify("merge-tabular", features, n_features=8)

    def classify_glossary(self, features: list[float]) -> tuple[str, float]:
        """Classify whether a section is a glossary from 4 features."""
        if self._rust_available:
            import pdf_oxide
            clf = pdf_oxide.GlossaryClassifier()
            return clf.predict(features)
        return self._sklearn_classify("glossary-section", features, n_features=4)

    def _sklearn_classify(
        self, model_name: str, features: list[float], n_features: int
    ) -> tuple[str, float]:
        """Fallback: use sklearn model via joblib."""
        import numpy as np

        model = self._load_sklearn(model_name)
        if model is None:
            return ("unknown", 0.0)

        X = np.array(features[:n_features], dtype=np.float32).reshape(1, -1)
        pred = model.predict(X)[0]
        proba = model.predict_proba(X)[0]
        confidence = float(np.max(proba))
        return (str(pred), confidence)

    def _load_sklearn(self, name: str) -> Any:
        """Perform load sklearn operation."""
        if name in self._sklearn_models:
            return self._sklearn_models[name]
        try:
            import joblib
            from pathlib import Path

            # Search known paths
            candidates = [
                Path(__file__).parents[4] / "models" / f"{name}" / "model.joblib",
                Path.home() / "workspace" / "experiments" / "extractor" / "models" / f"{name}" / "model.joblib",
            ]
            for p in candidates:
                if p.exists():
                    model = joblib.load(p)
                    self._sklearn_models[name] = model
                    return model
        except Exception:
            pass
        return None


# Singleton router
_classifier_router: Optional[ClassifierRouter] = None


def get_classifier_router() -> ClassifierRouter:
    """Return classifier router."""
    global _classifier_router
    if _classifier_router is None:
        _classifier_router = ClassifierRouter()
    return _classifier_router


# ---------------------------------------------------------------------------
# Agent-aware extractor
# ---------------------------------------------------------------------------

# Confidence thresholds for cascade routing
AGENT_THRESHOLD = 0.70  # Below this → agent should intervene
HUMAN_THRESHOLD = 0.50  # Below this → park for human /interview

# Skill suggestions per extraction field
SKILL_MAP: dict[str, list[str]] = {
    "text": ["/pdf-lab", "/normalize"],
    "table_strategy": ["/table-lab", "/pdf-lab", "/create-table-classifier"],
    "tables": ["/table-lab", "/pdf-lab", "/debug-table"],
    "figures": ["/figure-lab", "/pdf-lab"],
    "sections": ["/pdf-lab"],
    "annotations": ["/pdf-lab"],
}


class AgentAwareExtractor:
    """Extraction substrate that emits structured results for the project agent.

    This does NOT call LLMs or agents. It runs heuristic + classifier layers
    and provides the data the agent needs to make decisions.

    The cascade:
      1. Heuristic (Rust-fast): text extraction, path-based table detection
         ↓ confidence < 0.90
      2. Classifier (Rust ONNX): table strategy, merge decision, glossary
         ↓ confidence < 0.70
      3. Project Agent: /pdf-lab, /review-pdf, /memory, /table-lab
         ↓ agent can't resolve
      4. Human (/interview): structured questions with pre-annotations
    """

    def __init__(self, doc: BackendDoc):
        """Perform init operation."""
        self._doc = doc
        self._results: dict[int, PageExtractionResult] = {}
        self._router = get_classifier_router()

    # -- Core extraction --

    def extract_page(self, page_num: int) -> PageExtractionResult:
        """Run heuristic + classifier layers for a single page.

        Returns results WITH confidence scores. The project agent decides
        what to do with low-confidence results.
        """
        result = PageExtractionResult(page_num=page_num)

        # Layer 1: Heuristic text extraction
        try:
            text = self._doc.extract_text(page_num)
            text_len = len(text.strip())
            # Confidence heuristic: longer text = more reliable extraction
            if text_len > 500:
                conf = 0.95
            elif text_len > 100:
                conf = 0.85
            elif text_len > 20:
                conf = 0.60  # Might be scanned/image-heavy
            else:
                conf = 0.30  # Likely scanned or empty page

            result.text = ExtractionResult(
                value=text,
                confidence=conf,
                extractor="heuristic",
                needs_agent=conf < AGENT_THRESHOLD,
                needs_human=conf < HUMAN_THRESHOLD,
                page_num=page_num,
            )
        except Exception as e:
            result.text = ExtractionResult(
                value="",
                confidence=0.0,
                extractor="heuristic",
                needs_agent=True,
                needs_human=True,
                page_num=page_num,
                corrections=[{"type": "extraction_error", "error": str(e)}],
            )

        # Layer 2: Table strategy classification (if features available)
        table_features = self._extract_table_features(page_num)
        if table_features is not None:
            try:
                strategy, conf = self._router.classify_table_strategy(table_features)
                result.table_strategy = ExtractionResult(
                    value=strategy,
                    confidence=conf,
                    extractor="classifier",
                    needs_agent=conf < AGENT_THRESHOLD,
                    needs_human=conf < HUMAN_THRESHOLD,
                    page_num=page_num,
                )
            except Exception:
                pass

        # Layer 1: Heuristic table detection
        try:
            raw_tables = self._doc.extract_tables(page_num)
            for t in raw_tables:
                # Table confidence: based on cell density and structure
                cell_count = t.row_count * t.col_count
                if cell_count > 6 and t.row_count >= 2 and t.col_count >= 2:
                    conf = 0.90
                elif cell_count > 2:
                    conf = 0.70
                else:
                    conf = 0.50

                result.tables.append(ExtractionResult(
                    value={
                        "rows": t.rows,
                        "col_count": t.col_count,
                        "row_count": t.row_count,
                    },
                    confidence=conf,
                    extractor="heuristic",
                    needs_agent=conf < AGENT_THRESHOLD,
                    needs_human=conf < HUMAN_THRESHOLD,
                    page_num=page_num,
                    bbox=t.bbox,
                ))
        except Exception:
            pass

        # Store result
        self._results[page_num] = result
        return result

    def extract_document(self) -> dict[int, PageExtractionResult]:
        """Extract all pages, returning results with confidence scores."""
        for page_num in range(self._doc.page_count):
            self.extract_page(page_num)
        return self._results

    # -- Agent interface --

    def get_agent_work_items(self) -> list[dict]:
        """Return all pages/fields where the agent should intervene.

        The project agent calls this to know what needs attention.
        This is the bridge between pdf_oxide and /pdf-lab.
        """
        items = []
        for page_num, result in self._results.items():
            for field_name, extraction in result.fields():
                if extraction.needs_agent:
                    base_field = field_name.split("_")[0] if "_" in field_name else field_name
                    items.append({
                        "page_num": page_num,
                        "field": field_name,
                        "current_value": extraction.value,
                        "confidence": extraction.confidence,
                        "extractor": extraction.extractor,
                        "suggested_skills": SKILL_MAP.get(base_field, ["/pdf-lab"]),
                        "needs_human": extraction.needs_human,
                        "bbox": extraction.bbox.as_tuple() if extraction.bbox else None,
                    })

        # Sort by confidence (lowest first — most urgent)
        items.sort(key=lambda x: x["confidence"])
        return items

    def get_human_escalation_items(self) -> list[dict]:
        """Return items that need human review via /interview.

        These are extractions where even the agent couldn't resolve
        (confidence still < 0.50 after agent intervention).
        """
        items = []
        for page_num, result in self._results.items():
            for field_name, extraction in result.fields():
                if extraction.needs_human:
                    items.append({
                        "task_type": "pdf_extraction_review",
                        "pdf_path": self._doc._path,
                        "page_num": page_num,
                        "field": field_name,
                        "current_value": extraction.value,
                        "confidence": extraction.confidence,
                        "correction_history": extraction.corrections,
                        "suggested_actions": [
                            "accept",
                            "correct",
                            "blacklist",
                            "flag_redownload",
                        ],
                    })
        return items

    def apply_agent_correction(
        self,
        page_num: int,
        field_name: str,
        new_value: Any,
        *,
        skill_used: str,
        confidence: float,
    ):
        """Record an agent's correction with provenance.

        Called by /pdf-lab, /table-lab, etc. when they fix an extraction.
        """
        result = self._results.get(page_num)
        if result is None:
            return
        extraction = result.get_field(field_name)
        if extraction is None:
            return
        extraction.apply_correction(
            new_value,
            skill_used=skill_used,
            confidence=confidence,
            corrector="agent",
        )

    def apply_human_correction(
        self,
        page_num: int,
        field_name: str,
        new_value: Any,
    ):
        """Record a human correction from /interview."""
        result = self._results.get(page_num)
        if result is None:
            return
        extraction = result.get_field(field_name)
        if extraction is None:
            return
        extraction.apply_correction(
            new_value,
            skill_used="/interview",
            confidence=0.99,  # Human is ground truth
            corrector="human",
        )

    # -- Summary --

    def summary(self) -> dict:
        """Overall extraction quality summary for the project agent."""
        total_fields = 0
        agent_needed = 0
        human_needed = 0
        avg_confidence = 0.0
        by_extractor: dict[str, int] = {}
        by_field: dict[str, list[float]] = {}

        for page_num, result in self._results.items():
            for field_name, extraction in result.fields():
                total_fields += 1
                avg_confidence += extraction.confidence
                if extraction.needs_agent:
                    agent_needed += 1
                if extraction.needs_human:
                    human_needed += 1
                by_extractor[extraction.extractor] = (
                    by_extractor.get(extraction.extractor, 0) + 1
                )
                base = field_name.split("_")[0]
                by_field.setdefault(base, []).append(extraction.confidence)

        return {
            "page_count": self._doc.page_count,
            "total_fields": total_fields,
            "avg_confidence": avg_confidence / max(total_fields, 1),
            "agent_work_items": agent_needed,
            "human_escalations": human_needed,
            "by_extractor": by_extractor,
            "by_field": {
                k: sum(v) / len(v)
                for k, v in by_field.items()
            },
        }

    # -- Internal helpers --

    def _extract_table_features(self, page_num: int) -> Optional[list[float]]:
        """Extract 21 features for the table strategy classifier.

        Returns None if not enough data to classify.
        """
        try:
            spans = self._doc.extract_spans(page_num)
            if not spans:
                return None

            page_rect = self._doc.page_rect(page_num)

            # Basic features — these mirror what the training data expects
            font_sizes = [s.font_size for s in spans if s.font_size > 0]
            if not font_sizes:
                return None

            n_spans = len(spans)
            n_bold = sum(1 for s in spans if s.is_bold)
            n_italic = sum(1 for s in spans if s.is_italic)
            avg_font = sum(font_sizes) / len(font_sizes)
            min_font = min(font_sizes)
            max_font = max(font_sizes)
            font_variance = (
                sum((f - avg_font) ** 2 for f in font_sizes) / len(font_sizes)
            )
            page_width = page_rect.width
            page_height = page_rect.height

            # Text density
            total_text = sum(len(s.text) for s in spans)
            text_density = total_text / max(page_width * page_height, 1.0)

            # Unique fonts
            unique_fonts = len({s.font_name for s in spans})

            # Vertical distribution — how many distinct Y positions
            y_positions = sorted({round(s.bbox.y0, 1) for s in spans})
            n_rows_approx = len(y_positions)

            # Horizontal alignment — do spans align in columns?
            x_starts = sorted({round(s.bbox.x0, 1) for s in spans})
            n_cols_approx = min(len(x_starts), 20)

            # 21 features (padded to match training)
            features = [
                float(n_spans),
                float(n_bold),
                float(n_italic),
                avg_font,
                min_font,
                max_font,
                font_variance,
                page_width,
                page_height,
                text_density,
                float(unique_fonts),
                float(n_rows_approx),
                float(n_cols_approx),
                float(n_bold) / max(n_spans, 1),
                float(n_italic) / max(n_spans, 1),
                float(total_text),
                float(len(y_positions)),
                float(len(x_starts)),
                max_font - min_font,
                page_width / max(page_height, 1.0),
                float(total_text) / max(n_spans, 1),
            ]
            return features[:21]
        except Exception:
            return None
