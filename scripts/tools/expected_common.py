from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


# Map step → list of relative files under <step>/json_output
STEP_FILES: Dict[str, List[str]] = {
    "01": ["01_annotation_processor/json_output/01_annotations.json"],
    "02": ["02_marker_extractor/json_output/02_marker_blocks.json"],
    "04": ["04_section_builder/json_output/04_sections.json"],
    "05": ["05_table_extractor/json_output/05_tables.json"],
    "06": ["06_figure_extractor/json_output/06_figures.json"],
    "07": ["07_reflow_section/json_output/07_reflowed.json"],
    "09": ["09_section_summarizer/json_output/09_summaries.json"],
}


VOLATILE_KEYS = {"run_id", "stage_start_ts", "generated_at", "timestamp"}


def _strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalized_json(path: Path):
    data = _strip_volatile(load_json(path))
    # Stable string for comparisons
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

