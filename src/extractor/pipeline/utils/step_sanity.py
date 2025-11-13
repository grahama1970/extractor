from __future__ import annotations

"""Registry + runners for extractor pipeline per-step sanity checks."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .sanity_utils import SanityIssue, emit_sanity, read_json


@dataclass
class OutputCheck:
    rel_path: str
    kind: str = "json"  # json | file
    key: str | None = None
    min_items: int | None = None
    description: str | None = None


@dataclass
class StepSanitySpec:
    step: str
    description: str
    outputs: List[OutputCheck]
    extra: Optional[Callable[["SanityContext"], List[SanityIssue]]] = None


@dataclass
class SanityContext:
    step: str
    results_root: Path
    outputs_data: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    flags: Dict[str, Any] = field(default_factory=dict)


REGISTRY: Dict[str, StepSanitySpec] = {}


def register_step_sanity(spec: StepSanitySpec) -> None:
    REGISTRY[spec.step] = spec


def _default_results_root() -> Path:
    override = os.getenv("EXTRACTOR_RESULTS_ROOT")
    return Path(override) if override else Path("data/results/pipeline")


def _manifest_flags(root: Path) -> Dict[str, Any]:
    manifest = root / "manifest.json"
    if not manifest.exists():
        return {}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return {}
    flags = data.get("flags") if isinstance(data, dict) else {}
    return flags if isinstance(flags, dict) else {}


def _env_flag(*names: str) -> Optional[bool]:
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}
    for name in names:
        raw = os.getenv(name)
        if raw is None:
            continue
        text = raw.strip().lower()
        if text in truthy:
            return True
        if text in falsy:
            return False
        return bool(text)
    return None


def _count_items(obj: Any) -> int:
    if isinstance(obj, (list, tuple, set)):
        return len(obj)
    if isinstance(obj, dict):
        return len(obj.keys())
    return 0


def _missing_skip_reason(step: str, rel_path: str, *, summary_only: bool) -> Optional[str]:
    if step == "09_section_summarizer" and summary_only:
        return "summary_only"
    return None


def run_step_sanity(step: str, *, results_root: Path | None = None) -> int:
    spec = REGISTRY.get(step)
    if spec is None:
        raise ValueError(f"No sanity spec registered for {step}")
    root = results_root or _default_results_root()
    manifest_flags = _manifest_flags(root)
    summary_only_flag = _env_flag("SUMMARY_ONLY", "EXTRACTOR_SUMMARY_ONLY")
    if summary_only_flag is None:
        summary_only_flag = bool(manifest_flags.get("summary_only"))
    context_flags: Dict[str, Any] = dict(manifest_flags)
    context_flags["summary_only"] = bool(summary_only_flag)
    issues: List[SanityIssue] = []
    outputs_summary: List[Dict[str, Any]] = []
    outputs_data: Dict[str, Any] = {}
    missing_skip_reasons: List[str] = []

    for requirement in spec.outputs:
        rel = requirement.rel_path
        abs_path = root / rel
        entry: Dict[str, Any] = {
            "path": str(abs_path),
            "exists": abs_path.exists(),
        }
        if requirement.description:
            entry["description"] = requirement.description
        if not abs_path.exists():
            reason = _missing_skip_reason(step, rel, summary_only=bool(summary_only_flag))
            if reason:
                entry["skip_reason"] = reason
                missing_skip_reasons.append(reason)
            else:
                issues.append(SanityIssue("missing_output", {"path": str(abs_path)}))
            outputs_summary.append(entry)
            continue
        if requirement.kind == "json":
            data = read_json(abs_path)
            outputs_data[rel] = data
            entry["keys"] = sorted(list(data.keys()))[:8]
            if requirement.key:
                items = data.get(requirement.key) or []
                count = _count_items(items)
                entry[f"{requirement.key}_count"] = count
                if requirement.min_items is not None and count < requirement.min_items:
                    issues.append(
                        SanityIssue(
                            "insufficient_items",
                            {
                                "path": str(abs_path),
                                "key": requirement.key,
                                "count": count,
                                "min_expected": requirement.min_items,
                            },
                        )
                    )
        elif requirement.kind == "file":  # best-effort size metadata
            try:
                entry["size_bytes"] = abs_path.stat().st_size
            except Exception:
                entry["size_bytes"] = 0
        outputs_summary.append(entry)

    context = SanityContext(
        step=step,
        results_root=root,
        outputs_data=outputs_data,
        summary={
            "description": spec.description,
            "outputs": outputs_summary,
        },
        flags=context_flags,
    )
    skipped_reason: Optional[str] = None
    if spec.outputs and len(missing_skip_reasons) == len(spec.outputs) and missing_skip_reasons:
        # All outputs were intentionally skipped for a known reason.
        skipped_reason = missing_skip_reasons[0]
        context.summary["skipped"] = skipped_reason
    if spec.extra and not skipped_reason:
        extra_issues = spec.extra(context) or []
        issues.extend(extra_issues)

    return emit_sanity(step, ok=not issues, issues=issues, **context.summary)


# ---------------------------------------------------------------------------
# Default specs derived from CONTRACT.md
# ---------------------------------------------------------------------------


def _count_key(context: SanityContext, rel_path: str, key: str) -> int:
    data = context.outputs_data.get(rel_path) or {}
    items = data.get(key) or []
    return _count_items(items)


def _extra_requirements(context: SanityContext) -> List[SanityIssue]:
    rel = "07_requirements_miner/json_output/07_requirements.json"
    count = _count_key(context, rel, "requirements")
    if count < 1:
        return [SanityIssue("no_requirements", {"path": str(context.results_root / rel)})]
    return []


def _extra_summaries(context: SanityContext) -> List[SanityIssue]:
    rel = "09_section_summarizer/json_output/09_summaries.json"
    data = context.outputs_data.get(rel) or {}
    summaries = data.get("summaries") or []
    touched = sum(1 for s in summaries if s.get("success"))
    context.summary["summaries_success"] = touched
    if touched == 0:
        return [SanityIssue("no_successful_summaries", {"path": str(context.results_root / rel)})]
    return []


def _extra_pdf_annotations(context: SanityContext) -> List[SanityIssue]:
    rel = "09a_pdf_annotator/json_output/annotations.json"
    overlays = _count_key(context, rel, "overlays")
    context.summary["overlay_count"] = overlays
    if overlays == 0:
        return [SanityIssue("no_overlays", {"path": str(context.results_root / rel)})]
    return []


def _extra_graph_edges(context: SanityContext) -> List[SanityIssue]:
    rel = "11_arango_create_graph/json_output/11_graph_edges.json"
    edges = _count_key(context, rel, "edges")
    context.summary["edge_count"] = edges
    if edges == 0:
        return [SanityIssue("no_graph_edges", {"path": str(context.results_root / rel)})]
    return []


def _register_default_specs() -> None:
    register_step_sanity(
        StepSanitySpec(
            step="01_annotation_processor",
            description="Annotations JSON exists with entries",
            outputs=[
                OutputCheck(
                    "01_annotation_processor/json_output/01_annotations.json",
                    key="annotations",
                    min_items=1,
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="02_marker_extractor",
            description="Marker blocks present",
            outputs=[
                OutputCheck(
                    "02_marker_extractor/json_output/02_marker_blocks.json",
                    key="blocks",
                    min_items=1,
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="03_suspicious_headers",
            description="Verified header blocks emitted",
            outputs=[
                OutputCheck(
                    "03_suspicious_headers/json_output/03_verified_blocks.json",
                    key="blocks",
                    min_items=1,
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="04_section_builder",
            description="Sections JSON present",
            outputs=[
                OutputCheck(
                    "04_section_builder/json_output/04_sections.json",
                    key="sections",
                    min_items=1,
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="05_table_extractor",
            description="Tables JSON present",
            outputs=[
                OutputCheck(
                    "05_table_extractor/json_output/05_tables.json",
                    key="tables",
                    min_items=1,
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="06_figure_extractor",
            description="Figures JSON present",
            outputs=[
                OutputCheck(
                    "06_figure_extractor/json_output/06_figures.json",
                    key="figures",
                    min_items=None,
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="06a_title_caption_enricher",
            description="Enriched table/figure titles recorded",
            outputs=[
                OutputCheck(
                    "06a_title_caption_enricher/json_output/05_tables.enriched.json",
                    key="tables",
                    min_items=1,
                    description="Enriched tables",
                ),
                OutputCheck(
                    "06a_title_caption_enricher/json_output/06_figures.enriched.json",
                    key="figures",
                    min_items=1,
                    description="Enriched figures",
                ),
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="06b_layout_sketcher",
            description="Layout sketches available",
            outputs=[
                OutputCheck(
                    "06b_layout_sketcher/json_output/06b_layout_sketch.json",
                    key="sections",
                    min_items=1,
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="07_reflow_section",
            description="Reflowed sections JSON present",
            outputs=[
                OutputCheck(
                    "07_reflow_section/json_output/07_reflowed.json",
                    key="reflowed_sections",
                    min_items=1,
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="07_requirements_miner",
            description="Requirements mined",
            outputs=[
                OutputCheck(
                    "07_requirements_miner/json_output/07_requirements.json",
                    key="requirements",
                    min_items=1,
                )
            ],
            extra=_extra_requirements,
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="08_lean4_theorem_prover",
            description="Lean4 theorem results present",
            outputs=[
                OutputCheck(
                    "08_lean4_theorem_prover/json_output/08_theorems.json",
                    key="proof_results",
                    min_items=1,
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="09_section_summarizer",
            description="Section summaries available",
            outputs=[
                OutputCheck(
                    "09_section_summarizer/json_output/09_summaries.json",
                    key="summaries",
                    min_items=1,
                )
            ],
            extra=_extra_summaries,
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="09a_pdf_annotator",
            description="PDF overlays emitted",
            outputs=[
                OutputCheck(
                    "09a_pdf_annotator/json_output/annotations.json",
                    key="overlays",
                    min_items=1,
                ),
                OutputCheck(
                    "09a_pdf_annotator/json_output/legend.json",
                    kind="json",
                ),
            ],
            extra=_extra_pdf_annotations,
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="09b_audit",
            description="Milestone audit (01–09a)",
            outputs=[
                OutputCheck(
                    "09b_audit/json_output/09b_audit.json",
                    kind="json",
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="10_arangodb_exporter",
            description="Flattened data for Arango export exists",
            outputs=[
                OutputCheck(
                    "10_arangodb_exporter/json_output/10_flattened_data.json",
                    kind="json",
                )
            ],
        )
    )
    register_step_sanity(
        StepSanitySpec(
            step="11_arango_create_graph",
            description="Graph edges JSON available",
            outputs=[
                OutputCheck(
                    "11_arango_create_graph/json_output/11_graph_edges.json",
                    key="edges",
                    min_items=1,
                )
            ],
            extra=_extra_graph_edges,
        )
    )


_register_default_specs()


__all__ = [
    "OutputCheck",
    "SanityContext",
    "SanityIssue",
    "StepSanitySpec",
    "register_step_sanity",
    "run_step_sanity",
]
