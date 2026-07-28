#!/usr/bin/env python3
"""
Stage-11: JSON Exporter — Convert assembled content to hierarchical structural JSON.

Purpose:
- Generate a machine-readable representation of the extracted content.
- Maintains strict section-by-section ordering of all elements.
- Includes Text, Tables, Figures, Equations, and Requirements.

Output:
- `data/results/pipeline/11_json_exporter/structural.json`
"""

import sys
import json
from typing import Any, Dict, Optional, List
from pathlib import Path
from loguru import logger
from rich.console import Console
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.utils.content_query import ContentRepository

# Initialize
console = Console()
STEP_NAME = "11_json_exporter"


def sanity() -> int:
    """Run sanity check step for the current module."""
    return run_step_sanity(STEP_NAME)


def run(
    input_path: Path,
    output_dir: Path = None,
    preset_config: Optional[Dict[str, Any]] = None,
):
    """
    Run the JSON Export step.
    Args:
        input_path: Path to `07_assemble_corpus` output or the db file itself.
        preset_config: Optional preset configuration for format-specific options.
    """
    pipeline_dir = input_path

    if input_path.suffix == ".json" and input_path.is_file():
        pipeline_dir = input_path.parent
        if input_path.name == "assembled_content.json":
            pipeline_dir = input_path.parent.parent  # 07_assembled/ parent
    else:
        pipeline_dir = input_path.parent.parent if input_path.is_file() else input_path

    # Find assembled content
    data_path = pipeline_dir / "07_assembled" / "assembled_content.json"
    if not data_path.exists():
        logger.error(f"assembled_content.json not found at {data_path}")
        return

    # Output setup
    stage_dir = (output_dir or pipeline_dir) / STEP_NAME
    stage_dir.mkdir(parents=True, exist_ok=True)
    json_out_path = stage_dir / "structural.json"

    logger.info(f"Loading from {data_path}")

    # Initialize Repo
    repo = ContentRepository(data_path)

    # 1. Fetch Sections
    sections = repo.get_sections()

    # 2. Fetch Document Metadata
    doc_meta = {}
    raw_meta = repo.document_metadata
    if raw_meta:
        doc_meta = {
            "title": raw_meta.get("title"),
            "summary": raw_meta.get("document_summary"),
            "page_count": raw_meta.get("page_count"),
        }

    document_structure = {
        "metadata": doc_meta,
        "sections": []
    }

    for sec_id, sec_title, p_start, sec_summary in sections:
        section_data = {
            "id": sec_id,
            "title": sec_title,
            "page_start": p_start,
            "summary": sec_summary,
            "elements": []
        }

        # Fetch Content
        items = repo.get_section_content(sec_id)

        for itype, content, sort_order, meta_json, asset_id in items:
            meta = json.loads(meta_json) if meta_json else {}
            
            element = {
                "type": itype,
                "content": content,
                "sort_order": sort_order,
                "metadata": meta,
                "asset_id": asset_id
            }
            
            # Special handling for tables (CSV to structured if possible)
            if itype == "table" and content:
                try:
                    import io
                    import pandas as pd
                    df = pd.read_csv(io.StringIO(content))
                    element["structured_data"] = df.to_dict(orient="records")
                except Exception as e:
                    logger.debug(f"Failed to parse table CSV to structured data: {e}")

            section_data["elements"].append(element)

        document_structure["sections"].append(section_data)

    # Write JSON
    with open(json_out_path, "w", encoding="utf-8") as f:
        json.dump(document_structure, f, indent=2, ensure_ascii=False)

    logger.success(f"Exported structural JSON to {json_out_path}")
    return json_out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 11: JSON Exporter")
    parser.add_argument(
        "--pipeline-dir", type=Path, required=True, help="Path to pipeline results root"
    )
    args = parser.parse_args()

    try:
        run(args.pipeline_dir)
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
