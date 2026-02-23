"""
Module: pdf.py
Description: PDF to markdown conversion with advanced table and image extraction

External Dependencies:
- pypdf: https://pypdf.readthedocs.io/
- surya-ocr: https://github.com/VikParuchuri/surya
- camelot-py: https://camelot-py.readthedocs.io/
- litellm: https://docs.litellm.ai/

Sample Input:
>>> pdf_path = "document.pdf"
>>> settings = {"ocr_all_pages": False, "max_pages": 10}

Expected Output:
>>> markdown_text = "# Document Title\\n\\nContent extracted from PDF..."
>>> # Includes tables, images, equations, and structured text

Example Usage:
>>> from extractor.core.converters.pdf import convert_single_pdf
>>> markdown = convert_single_pdf("research_paper.pdf", max_pages=5)
>>> print(markdown[:100])
'# Research Paper Title\\n\\n## Abstract\\n\\nThis paper presents...'
"""

import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"  # disables a tokenizers warning

from collections import defaultdict
from typing import Annotated, Any, Dict, List, Optional, Type, Tuple

from extractor.core.processors import BaseProcessor

try:
    from extractor.core.processors.llm.llm_table_merge import LLMTableMergeProcessor
except Exception:  # pragma: no cover

    class LLMTableMergeProcessor:  # type: ignore
        ...


from extractor.core.providers.registry import provider_from_filepath
from extractor.core.builders.document import DocumentBuilder
from extractor.core.builders.layout import LayoutBuilder

try:
    from extractor.core.builders.llm_layout import LLMLayoutBuilder
except Exception:  # pragma: no cover

    class LLMLayoutBuilder:  # type: ignore
        ...


from extractor.core.builders.line import LineBuilder
from extractor.core.builders.ocr import OcrBuilder
from extractor.core.builders.structure import StructureBuilder
from extractor.core.converters import BaseConverter
from extractor.core.processors.blockquote import BlockquoteProcessor
from extractor.core.processors.code_processor import CodeProcessor
from extractor.core.processors.debug import DebugProcessor
from extractor.core.processors.document_toc import DocumentTOCProcessor

try:
    from extractor.core.processors.equation import EquationProcessor
except Exception:  # pragma: no cover

    class EquationProcessor:  # type: ignore
        def __init__(self, *args, **kwargs): ...
        def __call__(self, *args, **kwargs): ...


from extractor.core.processors.footnote import FootnoteProcessor
from extractor.core.processors.ignoretext import IgnoreTextProcessor
from extractor.core.processors.line_numbers import LineNumbersProcessor
from extractor.core.processors.list import ListProcessor

try:
    from extractor.core.processors.llm.llm_complex import LLMComplexRegionProcessor
    from extractor.core.processors.llm.llm_form import LLMFormProcessor
    from extractor.core.processors.llm.llm_image_description import LLMImageDescriptionProcessor
    from extractor.core.processors.llm.llm_table import LLMTableProcessor
    from extractor.core.processors.llm.llm_inlinemath import LLMInlineMathLinesProcessor
except Exception:  # pragma: no cover

    class _NoOp:  # type: ignore
        ...

    LLMComplexRegionProcessor = _NoOp
    LLMFormProcessor = _NoOp
    LLMImageDescriptionProcessor = _NoOp
    LLMTableProcessor = _NoOp
    LLMInlineMathLinesProcessor = _NoOp
from extractor.core.processors.page_header import PageHeaderProcessor
from extractor.core.processors.reference import ReferenceProcessor
from extractor.core.processors.sectionheader import SectionHeaderProcessor
from extractor.core.processors.font_header import FontHeaderProcessor

try:
    from extractor.core.processors.table import TableProcessor
except Exception:  # pragma: no cover

    class TableProcessor:  # type: ignore
        def __init__(self, *args, **kwargs): ...
        def __call__(self, *args, **kwargs): ...


from extractor.core.processors.text import TextProcessor

try:
    from extractor.core.processors.llm.llm_equation import LLMEquationProcessor
except Exception:  # pragma: no cover

    class LLMEquationProcessor:  # type: ignore
        ...


try:
    from extractor.core.renderers.markdown import MarkdownRenderer
except Exception:
    # Lightweight fallback so import-time dependencies don't block Stage 02
    class MarkdownRenderer:  # type: ignore
        def __init__(self, *args, **kwargs): ...

        def __call__(self, document):  # pragma: no cover - fallback path
            return ""


from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block
from extractor.core.schema.registry import register_block_class
from extractor.core.util import strings_to_classes

try:
    from extractor.core.processors.llm.llm_handwriting import LLMHandwritingProcessor
except Exception:  # pragma: no cover

    class LLMHandwritingProcessor:  # type: ignore
        ...


from extractor.core.processors.order import OrderProcessor

# MARKER FORK ADDITION START - LiteLLM service
try:
    from extractor.core.services.litellm import LiteLLMService
except Exception:  # pragma: no cover

    class LiteLLMService:  # type: ignore
        ...


# MARKER FORK ADDITION END
from extractor.core.processors.line_merge import LineMergeProcessor

try:
    from extractor.core.processors.llm.llm_mathblock import LLMMathBlockProcessor
except Exception:  # pragma: no cover

    class LLMMathBlockProcessor:  # type: ignore
        ...


# Extractor-Specific Imports (Fork)
from extractor.core.processors.suspicious_header_fixer import SuspiciousHeaderFixer
from extractor.core.processors.block_relabel import BlockRelabelProcessor


class PdfConverter(BaseConverter):
    """
    A converter for processing and rendering PDF files into Markdown, JSON, HTML and other formats.
    """

    override_map: Annotated[
        Dict[BlockTypes, Type[Block]],
        "A mapping to override the default block classes for specific block types.",
        "The keys are `BlockTypes` enum values, representing the types of blocks,",
        "and the values are corresponding `Block` class implementations to use",
        "instead of the defaults.",
    ] = defaultdict()
    use_llm: Annotated[
        bool,
        "Enable higher quality processing with LLMs.",
    ] = False
    default_processors: Tuple[BaseProcessor, ...] = (
        OrderProcessor,
        BlockRelabelProcessor,
        LineMergeProcessor,
        BlockquoteProcessor,
        CodeProcessor,
        DocumentTOCProcessor,
        EquationProcessor,
        FootnoteProcessor,
        IgnoreTextProcessor,
        LineNumbersProcessor,
        ListProcessor,
        PageHeaderProcessor,
        SectionHeaderProcessor,
        FontHeaderProcessor,  # Font-based header detection after initial SectionHeaderProcessor
        # Table extraction happens in later pipeline stages (05_table_extractor.py)
        TableProcessor,
        TextProcessor,
        # FontCaptureProcessor deprecated: font metadata is gathered directly
        # via provider spans or PyMuPDF in downstream processors.
        ReferenceProcessor,
        SuspiciousHeaderFixer,  # ← fix mis-classifications
        DebugProcessor,
    )

    # LLM processors to be added conditionally when use_llm=True
    llm_processors: Tuple[BaseProcessor, ...] = (
        LLMTableProcessor,
        LLMTableMergeProcessor,
        LLMFormProcessor,
        LLMInlineMathLinesProcessor,
        LLMComplexRegionProcessor,
        LLMImageDescriptionProcessor,
        LLMEquationProcessor,
        LLMHandwritingProcessor,
        LLMMathBlockProcessor,
    )

    def __init__(
        self,
        artifact_dict: Dict[str, Any],
        processor_list: Optional[List[str]] = None,
        renderer: str | None = None,
        llm_service: str | None = None,
        config=None,
    ):
        super().__init__(config)

        if config is None:
            config = {}

        for block_type, override_block_type in self.override_map.items():
            register_block_class(block_type, override_block_type)

        if processor_list:
            if isinstance(processor_list, str):
                if processor_list == "default":
                    # Just use default processors
                    processor_list = self.default_processors
                elif processor_list.startswith("default+"):
                    # Use default processors and append the additional ones
                    additional_processors_str = processor_list.replace("default+", "")
                    # Support comma-separated list of additional processors
                    additional_processors = [
                        p.strip() for p in additional_processors_str.split(",") if p.strip()
                    ]
                    processor_list = list(self.default_processors) + strings_to_classes(
                        additional_processors
                    )
                else:
                    # Assume it's a comma-separated list of processor classes
                    processor_list = strings_to_classes(
                        processor_list if isinstance(processor_list, list) else [processor_list]
                    )
            else:
                processor_list = strings_to_classes(processor_list)
        else:
            processor_list = self.default_processors

        if renderer:
            renderer = strings_to_classes([renderer])[0]
        else:
            renderer = MarkdownRenderer

        if llm_service:
            llm_service_cls = strings_to_classes([llm_service])[0]
            llm_service = self.resolve_dependencies(llm_service_cls)
        elif config.get("use_llm", False):
            # MARKER FORK ADDITION START - Use LiteLLM as default LLM service
            llm_service = self.resolve_dependencies(LiteLLMService)
            # MARKER FORK ADDITION END

        # Inject llm service into artifact_dict so it can be picked up by processors, etc.
        artifact_dict["llm_service"] = llm_service
        self.llm_service = llm_service

        self.artifact_dict = artifact_dict
        self.renderer = renderer

        # Ensure processor_list is a list of classes, not strings
        if isinstance(processor_list, tuple):
            processor_list = list(processor_list)

        # Drop EquationProcessor when no real texify is available (offline mode)
        os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() not in {"0", "false"}
        try:
            from extractor.core.processors.equation import EquationProcessor as _EqProc  # type: ignore
        except Exception:
            _EqProc = None  # type: ignore

        def _has_real_texify(model):
            if not model:
                return False
            try:
                if getattr(model, "is_dummy", False):
                    return False
            except Exception:
                return False
            return True

        if _EqProc in processor_list and not _has_real_texify(
            self.artifact_dict.get("texify_model")
        ):
            # Always drop EquationProcessor unless a real texify model is available
            processor_list = [p for p in processor_list if p is not _EqProc]

        # Drop TableProcessor if no table_rec model available in offline mode
        try:
            from extractor.core.processors.table import TableProcessor as _TblProc  # type: ignore
        except Exception:
            _TblProc = None  # type: ignore
        if _TblProc in processor_list and not self.artifact_dict.get("table_rec_model"):
            # Drop if table recognition model is not available
            processor_list = [p for p in processor_list if p is not _TblProc]

        # Add LLM processors if use_llm is enabled
        if self.use_llm and processor_list == list(self.default_processors):
            # Only add LLM processors if we're using default processors
            processor_list = list(processor_list) + list(self.llm_processors)

        processor_list = self.initialize_processors(processor_list)
        self.processor_list = processor_list

        self.layout_builder_class = LayoutBuilder
        if self.use_llm:
            self.layout_builder_class = LLMLayoutBuilder

    def build_document(self, filepath: str):
        provider_cls = provider_from_filepath(filepath)
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)
        provider = provider_cls(filepath, self.config)
        document = DocumentBuilder(self.config)(provider, layout_builder, line_builder, ocr_builder)
        structure_builder_cls = self.resolve_dependencies(StructureBuilder)
        structure_builder_cls(document)

        for processor in self.processor_list:
            processor(document)

        return document

    def __call__(self, filepath: str):
        document = self.build_document(filepath)
        renderer = self.resolve_dependencies(self.renderer)
        return renderer(document)


def convert_single_pdf(pdf_path: str, **kwargs) -> str:
    """Convert a single PDF to markdown

    Args:
        pdf_path: Path to the PDF file
        **kwargs: Additional options:
            - max_pages: Maximum number of pages to process
            - langs: List of languages in the document
            - use_llm: Enable LLM processing for better quality
            - batch_multiplier: Increase batch size for faster processing (more VRAM)

    Returns:
        Markdown string representation of the PDF
    """
    # Try full Surya-based conversion first
    try:
        from extractor.core.models import create_model_dict

        # Create model dictionary
        # Check environment variable to force CPU usage
        device = None
        if os.getenv("FORCE_CPU", "").lower() == "true":
            device = "cpu"
            print("📱 Forcing CPU usage for Marker models (FORCE_CPU=true)")

        models = create_model_dict(device=device)

        # Try to use ConfigParser if available
        try:
            from extractor.core.config.parser import ConfigParser

            # Create CLI-like options dict
            cli_options = {
                "max_pages": kwargs.get("max_pages"),
                "languages": ",".join(
                    kwargs.get("langs", ["English"])
                ),  # ConfigParser expects comma-separated string
                "disable_multiprocessing": True,
                "disable_tqdm": True,
                "output_format": "markdown",
            }

            # Remove None values
            cli_options = {k: v for k, v in cli_options.items() if v is not None}

            # Use ConfigParser to generate config
            config_parser = ConfigParser(cli_options)
            config = config_parser.generate_config_dict()

            # Create the PDF converter with proper config
            converter = PdfConverter(
                artifact_dict=models,
                config=config,
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
            )

        except ImportError:
            # Fallback if ConfigParser not available
            config = {
                "max_pages": kwargs.get("max_pages"),
                "langs": kwargs.get("langs", ["English"]),
                "use_llm": kwargs.get("use_llm", False),
                "batch_multiplier": kwargs.get("batch_multiplier", 1),
                "disable_multiprocessing": True,
                "disable_tqdm": True,
            }

            # Remove None values
            config = {k: v for k, v in config.items() if v is not None}

            # Create the PDF converter
            converter = PdfConverter(artifact_dict=models, config=config)

        # Convert the PDF
        markdown_output = converter(pdf_path)
        return markdown_output

    except Exception as e:
        # FAIL FAST - NO FALLBACK TO PYMUPDF EVER!
        print(f"❌ FATAL: Surya conversion failed: {e}")
        print("❌ FAILING FAST AS REQUIRED - NO FALLBACK")
        raise Exception(f"PDF conversion failed: {str(e)}. NO FALLBACK TO PYMUPDF.")


if __name__ == "__main__":
    # Test PDF conversion functionality with REAL PDF files
    print("🧪 Testing PDF Converter with Real Data")
    print("=" * 50)

    import os
    import time
    from pathlib import Path

    # Test 1: Convert the actual research paper PDF
    print("\n📝 Test 1: Convert Real Research Paper (2505.03335v2.pdf)")
    test_pdf_path = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"

    if os.path.exists(test_pdf_path):
        try:
            start_time = time.time()
            result = convert_single_pdf(test_pdf_path, max_pages=5)
            elapsed_time = time.time() - start_time

            # Check that we got real content, not placeholder
            assert isinstance(result, str), "Result should be string"
            assert len(result) > 1000, f"Result too short ({len(result)} chars), likely placeholder"
            assert "placeholder" not in result.lower(), "Result contains placeholder text"
            assert "Error Converting" not in result, "Result is error message"

            print("✅ PDF conversion successful!")
            print(f"   - Processed in {elapsed_time:.2f} seconds")
            print(f"   - Output length: {len(result):,} characters")
            print(f"   - First 200 chars: {result[:200]}...")

            # Save output for inspection
            output_path = Path(test_pdf_path).parent / f"{Path(test_pdf_path).stem}_extracted.md"
            with open(output_path, "w") as f:
                f.write(result)
            print(f"   - Saved to: {output_path}")

        except Exception as e:
            print(f"❌ PDF conversion failed: {e}")
            import traceback

            traceback.print_exc()
    else:
        print(f"⚠️  Test PDF not found: {test_pdf_path}")

    # Test 2: Check if we can extract title from the PDF
    print("\n📝 Test 2: Verify Content Extraction Quality")
    if "result" in locals() and len(result) > 1000:
        # Check for expected content in the research paper
        content_checks = {
            "title": "Absolute Zero" in result or "absolute zero" in result,
            "sections": "#" in result,  # Markdown headers
            "paragraphs": "\n\n" in result,  # Paragraph breaks
            "length": len(result) > 10000,  # Substantial content
        }

        print("Content quality checks:")
        for check, passed in content_checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check}: {'PASS' if passed else 'FAIL'}")

        # Try to find specific content
        if "Abstract" in result or "abstract" in result:
            print("   ✅ Found abstract section")
        if "Introduction" in result or "introduction" in result:
            print("   ✅ Found introduction section")

    # Test 3: Compare with other format extractions
    print("\n📝 Test 3: Check Other Format Files")
    other_formats = [
        "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.docx",
        "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.md",
        "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2_extracted.txt",
    ]

    for file_path in other_formats:
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"   ✓ Found {Path(file_path).name} ({file_size:,} bytes)")
        else:
            print(f"   ✗ Missing {Path(file_path).name}")

    # Test 4: Check processor availability
    print("\n📝 Test 4: Available Processors")
    try:
        available_processors = []
        for processor in PdfConverter.default_processors:
            available_processors.append(processor.__name__)

        print(f"✅ Found {len(available_processors)} processors")
        key_processors = [
            "TableProcessor",
            "EquationProcessor",
            "TextProcessor",
            "SectionHeaderProcessor",
        ]
        for proc in key_processors:
            if any(proc in p for p in available_processors):
                print(f"   ✓ {proc} available")
            else:
                print(f"   ✗ {proc} missing")

    except Exception as e:
        print(f"❌ Processor check failed: {e}")

    print("\n" + "=" * 50)

    # Final verdict
    if "result" in locals() and len(result) > 10000 and "placeholder" not in result.lower():
        print("✅ PDF extraction is working correctly!")
        print(f"   Successfully extracted {len(result):,} characters from PDF")
    else:
        print("❌ PDF extraction needs fixing - returning placeholder or error")
        print("   Next step: Implement proper Surya model initialization")

    print("=" * 50)
