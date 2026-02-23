#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 10 flatten minimal")


def _load_stage10():
    spec = importlib.util.spec_from_file_location(
        "stage10", "src/extractor/pipeline/steps/10_arangodb_exporter.py"
    )
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 10 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@app.command()
def main():
    load_dotenv(find_dotenv())
    mod = _load_stage10()
    flatten = getattr(mod, "flatten_document_to_pdf_objects")
    pipeline_data = {
        "reflowed_sections": [
            {
                "id": "s1",
                "title": "Intro",
                "level": 1,
                "page_start": 0,
                "bbox": [0, 0, 100, 50],
                "reflow_status": "success",
                "reflowed_text": "Hello world",
                "tables": [
                    {
                        "title": "INFERRED: T1",
                        "headers": ["A"],
                        "page_index": 0,
                        "bbox": [0, 60, 200, 120],
                    }
                ],
                "figures": [
                    {"title": "F1", "ai_description": "desc", "page": 0, "bbox": [0, 130, 100, 200]}
                ],
            }
        ]
    }
    summaries = {
        "summaries": [
            {
                "section_id": "s1",
                "success": True,
                "summary_data": {"summary": "hi", "key_concepts": []},
            }
        ]
    }
    objs = flatten(pipeline_data, summaries)
    if not isinstance(objs, list) or len(objs) < 3:
        raise SystemExit(1)
    if not all("object_index_in_doc" in o for o in objs):
        raise SystemExit(1)
    typer.echo("OK: Stage 10 flattened objects with ordering key")


if __name__ == "__main__":
    app()
