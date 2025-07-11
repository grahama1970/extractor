"""Simple public API and CLI for converting PDFs (and later other formats) to JSON.

Designed to give a **stable, testable** entry-point independent of the larger
config machinery.  It wraps the heavy-duty `PdfConverter` but forces the
`JSONRenderer`, then returns a plain Python `dict` (or prints JSON when used
as CLI).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from extractor.core.converters.pdf import PdfConverter
from extractor.core.renderers.json import JSONRenderer

try:
    # Model weights / artifact registry helper
    from extractor.core.models import create_model_dict  # type: ignore
except ImportError:
    create_model_dict = lambda: {}


def convert_pdf_to_json(pdf_path: str, **config_overrides: Any) -> Dict[str, Any]:
    """Convert a PDF to a JSON serialisable document structure.

    Parameters
    ----------
    pdf_path : str
        Path to local PDF file.
    **config_overrides
        Optional keyword args forwarded to the underlying converter config
        (e.g., ``max_pages=5`` or ``use_llm=True``).  Only simple JSON-serialisable
        values should be passed.

    Returns
    -------
    dict
        The document represented as a plain Python dictionary, suitable for
        ``json.dumps`` or further processing.
    """

    pdf_path = str(pdf_path)
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Build minimal config dict
    config: Dict[str, Any] = {
        "disable_multiprocessing": True,
        "disable_tqdm": True,
    }
    config.update({k: v for k, v in config_overrides.items() if v is not None})

    # Prepare converter with forced JSON renderer
    models = create_model_dict()
    converter = PdfConverter(
        artifact_dict=models,
        renderer="extractor.core.renderers.json.JSONRenderer",
        config=config,
    )

    json_output = converter(pdf_path)  # This is a JSONOutput (pydantic BaseModel)
    return json_output.model_dump()


# ---------------------------------------------------------------------------
# Generic converter dispatch helpers
# ---------------------------------------------------------------------------

_EXT_TO_FUNC = {
    ".pdf": "convert_pdf_to_json",
    ".docx": "convert_docx_to_json",
    ".pptx": "convert_pptx_to_json",
    ".html": "convert_html_to_json",
    ".htm": "convert_html_to_json",
    ".xml": "convert_html_to_json",
}

def _import_converter(module_path: str, class_name: str):
    """Attempt dynamic import and return class or raise informative error."""
    from importlib import import_module
    try:
        mod = import_module(module_path)
        return getattr(mod, class_name)
    except ModuleNotFoundError as e:
        raise NotImplementedError(f"{module_path} is not available: {e}")


def _convert_via_class(converter_cls, file_path: str, **config_overrides):
    config = {"disable_multiprocessing": True, "disable_tqdm": True}
    config.update({k: v for k, v in config_overrides.items() if v is not None})
    models = create_model_dict()
    converter = converter_cls(
        artifact_dict=models,
        renderer="extractor.core.renderers.json.JSONRenderer",
        config=config,
    )
    json_output = converter(file_path)
    return json_output.model_dump()


def convert_docx_to_json(docx_path: str, **config_overrides):
    converter_cls = _import_converter("extractor.core.converters.docx", "DocxConverter")
    return _convert_via_class(converter_cls, docx_path, **config_overrides)


def convert_pptx_to_json(pptx_path: str, **config_overrides):
    converter_cls = _import_converter("extractor.core.converters.pptx", "PptxConverter")
    return _convert_via_class(converter_cls, pptx_path, **config_overrides)


def convert_html_to_json(html_path: str, **config_overrides):
    converter_cls = _import_converter("extractor.core.converters.html", "HtmlConverter")
    return _convert_via_class(converter_cls, html_path, **config_overrides)


def convert_file_to_json(file_path: str, **config_overrides):
    """Auto-dispatch conversion based on file extension."""
    ext = Path(file_path).suffix.lower()
    func_name = _EXT_TO_FUNC.get(ext)
    if not func_name:
        raise ValueError(f"Unsupported file type: {ext}")
    return globals()[func_name](file_path, **config_overrides)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a PDF to Extractor JSON and print/save the result",
        prog="extractor-convert",
    )
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument("--out", "-o", help="Output path (.json). If omitted, prints to stdout")
    parser.add_argument("--max-pages", type=int, help="Limit pages processed")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM-powered processors")

    args = parser.parse_args()

    try:
        doc_dict = convert_pdf_to_json(
            args.pdf,
            max_pages=args.max_pages,
            use_llm=args.use_llm,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(json.dumps(doc_dict, indent=2), encoding="utf-8")
        print(f"Saved JSON to {out_path}")
    else:
        json.dump(doc_dict, sys.stdout, indent=2)
        print()  # final newline


if __name__ == "__main__":
    _cli()
