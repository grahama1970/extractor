#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
"""XML vs PDF parity smoke (Stage 10)."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Dict

import typer

from extractor.core.providers.xml import XMLProvider
from extractor.core.schema.unified_document import HierarchyNode

app = typer.Typer(add_completion=False)


def _load_flatten_function():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "extractor"
        / "pipeline"
        / "steps"
        / "10_arangodb_exporter.py"
    )
    spec = importlib.util.spec_from_file_location("pipeline_stage10", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Stage 10 module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.flatten_document_to_pdf_objects


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@app.command()
def main(
    pdf_stage10: Path = typer.Option(
        Path("data/results/pipeline/10_arangodb_exporter/json_output/10_flattened_data.json"),
        exists=True,
    ),
    xml_path: Path = typer.Option(
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.xml"
        ),
        exists=True,
    ),
    results_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/xml")),
) -> None:
    flatten = _load_flatten_function()

    # Run XML Extraction
    print(f"Extracting XML: {xml_path}")
    provider = XMLProvider()
    unified = provider.extract_document(str(xml_path))

    # Ensure hierarchy
    if getattr(unified, "hierarchy", None) is None:
        root = HierarchyNode(id="root", block_id=None, title=xml_path.stem, level=1, children=[])
        for block in unified.blocks:
            if getattr(block, "parent_id", None) is None:
                block.parent_id = root.id
        unified.hierarchy = root

    unified_payload = unified.model_dump(by_alias=True, mode="json")

    # Flatten
    pipeline_payload = {
        "unified_document": unified_payload,
        "source_files": {"sections": str(xml_path)},
    }

    xml_flattened = flatten(
        pipeline_data=pipeline_payload,
        summaries_data={"summaries": []},
        skip_embeddings=True,
        fast_embeddings=True,
    )

    # Save output
    results_dir.mkdir(parents=True, exist_ok=True)
    xml_flat_path = results_dir / "10_flattened_data.json"
    xml_flat_path.write_text(json.dumps(xml_flattened, indent=2))
    print(f"Saved flattened XML to {xml_flat_path}")

    # Load PDF flattened
    pdf_flattened = json.loads(pdf_stage10.read_text())

    # Compare counts
    print(f"PDF Blocks: {len(pdf_flattened)}")
    print(f"XML Blocks: {len(xml_flattened)}")

    # Simple Parity Check (Count)
    # We expect some deviation, but not massive.
    # Let's just report the stats for now as the "smoke" test.

    pdf_types: Dict[str, int] = {}
    x_types: Dict[str, int] = {}
    for obj in pdf_flattened:
        pdf_types[obj["object_type"]] = pdf_types.get(obj["object_type"], 0) + 1
    for obj in xml_flattened:
        x_types[obj["object_type"]] = x_types.get(obj["object_type"], 0) + 1

    print("PDF Types:", pdf_types)
    print("XML Types:", x_types)

    # Fail if XML has 0 blocks
    if len(xml_flattened) == 0:
        print("FAIL: XML extraction produced 0 blocks")
        raise typer.Exit(code=1)

    print("PASS: XML extraction successful")


if __name__ == "__main__":
    app()
