from __future__ import annotations

from typing import Dict, List

from tools.contract_loop.sanity_config_contract import SanityCommand


PROJECT_SANITY_COMMANDS: List[SanityCommand] = [
    SanityCommand(
        name="camelot_sanity",
        cmd=["uv", "run", "src/extractor/pipeline/sanity/camelot_sanity.py"],
    ),
    SanityCommand(
        name="s08_prove_simple",
        cmd=["uv", "run", "src/extractor/pipeline/sanity/s08_prove_simple_sanity.py"],
    ),
    SanityCommand(
        name="scillm_quick_doctor",
        cmd=[
            "python",
            "scripts/tools/scillm_quick_doctor.py",
        ],
    ),
    SanityCommand(
        name="scillm_quick_doctor",
        cmd=[
            "python",
            "scripts/tools/scillm_quick_doctor.py",
        ],
    ),
]


STEP_SANITY_COMMANDS: Dict[str, List[SanityCommand]] = {
    "01_annotation_processor": [
        SanityCommand(
            name="smoke_stage01_artifacts",
            cmd=["./scripts/smokes/smoke_stage01_artifacts.py"],
            step="01_annotation_processor",
        )
    ],
    "02_marker_extractor": [
        SanityCommand(
            name="smoke_stage02_marker",
            cmd=["./scripts/smokes/smoke_stage02_marker.py"],
            step="02_marker_extractor",
        )
    ],
    "03_suspicious_headers": [
        SanityCommand(
            name="smoke_stage03_header_text",
            cmd=["./scripts/smokes/smoke_stage03_header_text.py"],
            step="03_suspicious_headers",
        )
    ],
    "04_section_builder": [
        SanityCommand(
            name="smoke_stage04_sections",
            cmd=["./scripts/smokes/smoke_stage04_sections.py"],
            step="04_section_builder",
        )
    ],
    "04a_layout_audit": [
        SanityCommand(
            name="smoke_stage04a_layout_audit",
            cmd=["./scripts/smokes/smoke_stage04a_layout_audit.py"],
            step="04a_layout_audit",
        )
    ],
    "05_table_extractor": [
        SanityCommand(
            name="smoke_stage05_tables",
            cmd=["./scripts/smokes/smoke_stage05_tables.py"],
            step="05_table_extractor",
        )
    ],
    "05b_table_describer": [
        SanityCommand(
            name="smoke_stage05b_table_describer",
            cmd=["./scripts/smokes/smoke_stage05b_table_describer.py"],
            step="05b_table_describer",
        )
    ],
    "05c_table_merger": [
        SanityCommand(
            name="smoke_stage05c_table_merger",
            cmd=["./scripts/smokes/smoke_stage05c_table_merger.py"],
            step="05c_table_merger",
        )
    ],
    "06_figure_extractor": [
        SanityCommand(
            name="smoke_stage06_figures",
            cmd=["./scripts/smokes/smoke_stage06_figures.py"],
            step="06_figure_extractor",
        )
    ],
    "06b_figure_describer": [
        SanityCommand(
            name="smoke_stage06b_figure_describer",
            cmd=["./scripts/smokes/smoke_stage06b_figure_describer.py"],
            step="06b_figure_describer",
        )
    ],
    "07_assemble_corpus": [
        SanityCommand(
            name="smoke_stage07_text",
            cmd=["./scripts/smokes/smoke_stage07_text.py"],
            step="07_assemble_corpus",
        )
    ],
    "08_extract_requirements": [
        SanityCommand(
            name="s08_requirements_parallel",
            cmd=["uv", "run", "src/extractor/pipeline/sanity/s08_requirements_sanity.py"],
            step="08_extract_requirements",
        )
    ],
    "08_lean4_theorem_prover": [
        SanityCommand(
            name="smoke_stage08_lean4",
            cmd=["./scripts/smokes/smoke_stage08_lean4.py"],
            step="08_lean4_theorem_prover",
            optional=True,
        )
    ],
    "09_section_summarizer": [
        SanityCommand(
            name="smoke_stage09_summary",
            cmd=["./scripts/smokes/smoke_stage09_summary.py"],
            step="09_section_summarizer",
        )
    ],
    "10_arangodb_exporter": [
        SanityCommand(
            name="smoke_stage10_flatten",
            cmd=["./scripts/smokes/smoke_stage10_flatten.py"],
            step="10_arangodb_exporter",
        )
    ],
    "10_markdown_exporter": [
        SanityCommand(
            name="smoke_stage10_markdown",
            cmd=["./scripts/smokes/smoke_stage10_markdown.py"],
            step="10_markdown_exporter",
        )
    ],
    "14_report_generator": [
        SanityCommand(
            name="smoke_stage14_report",
            cmd=["./scripts/smokes/smoke_stage14_report.py"],
            step="14_report_generator",
        )
    ],
}


__all__ = ["PROJECT_SANITY_COMMANDS", "STEP_SANITY_COMMANDS"]
