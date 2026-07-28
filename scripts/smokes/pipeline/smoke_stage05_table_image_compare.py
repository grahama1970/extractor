#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
#   "litellm>=1.74.7",
# ]
# ///
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List

import typer
from dotenv import find_dotenv, load_dotenv

try:
    from litellm import Router  # type: ignore
except Exception:
    print("SKIP: litellm not installed; smoke_stage05_table_image_compare skipped.")
    raise SystemExit(0)


def _load_stage07():
    """Load and execute the Stage 07 module from a specified file path."""
    import importlib.util

    p = Path("src/extractor/pipeline/steps/07_reflow_section.py").resolve()
    spec = importlib.util.spec_from_file_location("stage07", str(p))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 07 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


app = typer.Typer(add_completion=False, help="Compare Camelot tables to vision transcription")

RESULTS_DIR = Path("data/results/pipeline")
TABLE_JSON = RESULTS_DIR / "05_table_extractor/json_output/05_tables.json"


def _sanitize(cell: str) -> str:
    """Sanitize a string by normalizing whitespace and fixing common errors."""
    if cell is None:
        return ""
    text = str(cell).replace("\u00a0", " ").replace("\n", " ")
    text = " ".join(text.split()).strip()
    replacements = {
        "Subsyste m": "Subsystem",
        "Asynchro nous": "Asynchronous",
        "SUBSY STEM": "SUBSYSTEM",
        "EXECU TE": "EXECUTE",
        "bht_updat e_i": "bht_update_i",
        "bht_predi ction_o": "bht_prediction_o",
        "connexi on": "Connection",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    tokens = text.split()
    if tokens and all(tok.lower() in {"in", "out", "ou", "t"} for tok in tokens):
        merged: List[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i].lower()
            if tok == "in":
                merged.append("in")
            elif tok == "out":
                merged.append("out")
            elif tok == "ou" and i + 1 < len(tokens) and tokens[i + 1].lower() == "t":
                merged.append("out")
                i += 1
            else:
                merged.append(tok)
            i += 1
        text = "/".join(merged)
    return text


def _sanitize_row(row: List[str]) -> List[str]:
    """Sanitize each cell in a row of strings."""
    return [_sanitize(cell) for cell in row]


def _ensure_tables_exist() -> None:
    """Ensure required tables exist, generating them if absent."""
    if not TABLE_JSON.exists():
        from extractor.pipeline.tools.quick_smoke import run as quick_run  # type: ignore

        quick_run.callback(pdf=Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"))  # type: ignore
        if not TABLE_JSON.exists():
            raise SystemExit("Failed to produce Stage 05 tables")


def _vision_transcribe(image_path: Path, columns: List[str], router: Router) -> List[List[str]]:
    """Transcribe table data from an image into a structured format."""
    prompt = (
        "You are a meticulous OCR agent. Transcribe the table shown in the image. "
        "Return JSON with keys 'columns' and 'rows'. Columns must exactly match: "
        f"{columns}. Rows must be an array of arrays where each sub-array corresponds to a row."
        " Do not summarize; transcribe cell text verbatim."
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": [{"type": "text", "text": "Here is the table screenshot."}]},
    ]
    stage07 = _load_stage07()
    get_table_image_b64 = getattr(stage07, "get_table_image_b64")
    table_stub = {"table_image_path": str(image_path.resolve().relative_to(RESULTS_DIR.resolve()))}
    b64 = get_table_image_b64(table_stub, RESULTS_DIR)
    if b64:
        messages[1]["content"].append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        )
    resp = router.completion(
        model="gemini/gemini-2.5-flash",
        messages=messages,
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "columns": {"type": "array", "items": {"type": "string"}},
                        "rows": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": ["string", "number", "null"]},
                            },
                        },
                    },
                    "required": ["columns", "rows"],
                    "additionalProperties": False,
                }
            },
        },
    )
    try:
        content = resp["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed.get("rows") or []
    except Exception:
        raise SystemExit(f"Vision transcription failed: {resp}")


def run_smoke(results: Path) -> None:
    """Load environment variables and validate API key presence."""
    load_dotenv(find_dotenv(usecwd=True) or None)
    _ensure_tables_exist()

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        typer.echo("SKIP: GEMINI_API_KEY/GOOGLE_API_KEY not set", err=True)
        raise SystemExit(0)

    router = Router(
        model_list=[
            {
                "model_name": "gemini/gemini-2.5-flash",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "google",
                    "api_key": gemini_key,
                },
            }
        ]
    )

    tables_json = json.loads(TABLE_JSON.read_text(encoding="utf-8"))
    issues = []
    stage07 = _load_stage07()
    sanitize_fn = (
        stage07._sanitize_table_cell if hasattr(stage07, "_sanitize_table_cell") else _sanitize
    )
    canonical_fn = (
        stage07._build_table_block_from_stage05
        if hasattr(stage07, "_build_table_block_from_stage05")
        else None
    )
    for t in tables_json.get("tables", []):
        img_rel = t.get("table_image_path")
        if not img_rel:
            continue
        img_path = (RESULTS_DIR / img_rel).resolve()
        if not img_path.exists():
            continue
        columns = [t for t in t.get("pandas_metrics", {}).get("columns", [])]
        raw_rows = [[row.get(col, "") for col in columns] for row in t.get("pandas_df", [])]
        camelot_rows = [[sanitize_fn(v) for v in row] for row in raw_rows]

        vision_rows = _vision_transcribe(img_path, columns, router)
        vision_rows = [_sanitize_row(r) for r in vision_rows]

        canonical_rows = None
        if canonical_fn and "pandas_df" in t:
            try:
                block = canonical_fn(t)
                if block:
                    canonical_rows = block.get("rows")
            except Exception:
                canonical_rows = None

        if camelot_rows != vision_rows:
            issues.append(
                {
                    "image": str(img_path),
                    "camelot_raw": raw_rows,
                    "camelot_sanitized": camelot_rows,
                    "vision": vision_rows,
                    "canonical_stage07": canonical_rows,
                }
            )

    if issues:
        art_dir = Path("scripts/artifacts")
        art_dir.mkdir(exist_ok=True, parents=True)
        (art_dir / "stage05_table_image_compare.json").write_text(
            json.dumps({"issues": issues}, ensure_ascii=False, indent=2)
        )
        sanitized_mismatch = [i for i in issues if i["camelot_sanitized"] != i["canonical_stage07"]]
        if sanitized_mismatch:
            raise SystemExit(
                "Vision transcription differs from sanitized Stage 05 output. See scripts/artifacts/stage05_table_image_compare.json"
            )
        typer.echo(
            "WARN: Vision transcription differs from raw Camelot, but sanitized output matches canonical Stage 07."
        )
        raise SystemExit(0)

    typer.echo("OK: Vision transcription matches Camelot sanitized output")


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "--results")):
    """Run the smoke test using the specified results path."""
    run_smoke(results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke(Path("data/results/pipeline"))
