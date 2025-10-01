#!/usr/bin/env python3
"""
Marker conversion script for PDF extraction (without LLM processors)
"""

import os
import sys
import click
from pathlib import Path

# Add the parent directory to the path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from extractor.core.converters.pdf import PdfConverter
from extractor.core.config.parser import ConfigParser
from extractor.core.models import create_model_dict


# List of non-LLM processors
NON_LLM_PROCESSORS = [
    "extractor.core.processors.order.OrderProcessor",
    "extractor.core.processors.line_merge.LineMergeProcessor",
    "extractor.core.processors.blockquote.BlockquoteProcessor",
    "extractor.core.processors.code.CodeProcessor",
    "extractor.core.processors.document_toc.DocumentTOCProcessor",
    "extractor.core.processors.equation.EquationProcessor",
    "extractor.core.processors.footnote.FootnoteProcessor",
    "extractor.core.processors.ignoretext.IgnoreTextProcessor",
    "extractor.core.processors.line_numbers.LineNumbersProcessor",
    "extractor.core.processors.list.ListProcessor",
    "extractor.core.processors.page_header.PageHeaderProcessor",
    "extractor.core.processors.sectionheader.SectionHeaderProcessor",
    "extractor.core.processors.table.TableProcessor",
    "extractor.core.processors.text.TextProcessor",
    "extractor.core.processors.reference.ReferenceProcessor",
    "extractor.core.processors.debug.DebugProcessor",
]


@ConfigParser.common_options
@click.command()
@click.argument("pdf_path", type=click.Path(exists=True))
def main(pdf_path, **kwargs):
    """Convert a single PDF file using marker (without LLM processors)."""
    try:
        # Create config parser
        config_parser = ConfigParser(kwargs)
        config = config_parser.generate_config_dict()

        # Disable LLM
        config["use_llm"] = False

        # Set default output directory if not specified
        if "output_dir" not in kwargs or not kwargs["output_dir"]:
            kwargs["output_dir"] = "."

        output_dir = kwargs["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        # Create models
        print("Loading ML models...")
        models = create_model_dict(device="cuda", dtype="float16")

        # Create converter with non-LLM processors
        print("Creating PDF converter...")
        converter = PdfConverter(
            config=config,
            artifact_dict=models,
            processor_list=NON_LLM_PROCESSORS,
            renderer=config_parser.get_renderer(),
            llm_service=None,
        )

        # Convert PDF
        print(f"Processing {pdf_path}...")
        result = converter(pdf_path)

        # Save result
        pdf_name = Path(pdf_path).stem
        output_format = kwargs.get("output_format", "json")

        if output_format == "json":
            output_file = os.path.join(output_dir, f"{pdf_name}.json")
            with open(output_file, "w") as f:
                f.write(str(result))
        else:
            output_file = os.path.join(output_dir, f"{pdf_name}.{output_format}")
            with open(output_file, "w") as f:
                f.write(str(result))

        print(f"✓ Saved to {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
