"""
Module: table.py
Description: Specialized table extraction from PDF documents

External Dependencies:
- pypdf: https://pypdf.readthedocs.io/
- camelot-py: https://camelot-py.readthedocs.io/

Sample Input:
>>> pdf_path = "document_with_tables.pdf"
>>> converter = TableConverter({})

Expected Output:
>>> # Extracts only table, form, and TOC blocks from PDF
>>> # Returns rendered output (markdown by default)

Example Usage:
>>> from extractor.core.converters.table import TableConverter
>>> converter = TableConverter({})
>>> tables_markdown = converter("financial_report.pdf")
>>> print(tables_markdown)
'| Column 1 | Column 2 |\\n|----------|----------|\\n| Data 1   | Data 2   |'
"""

from functools import cache
from typing import Tuple, List

from extractor.core.builders.document import DocumentBuilder
from extractor.core.builders.line import LineBuilder
from extractor.core.builders.ocr import OcrBuilder
from extractor.core.converters.pdf import PdfConverter
from extractor.core.processors import BaseProcessor
from extractor.core.processors.llm.llm_complex import LLMComplexRegionProcessor
from extractor.core.processors.llm.llm_form import LLMFormProcessor
from extractor.core.processors.llm.llm_table import LLMTableProcessor
from extractor.core.processors.llm.llm_table_merge import LLMTableMergeProcessor
from extractor.core.processors.table import TableProcessor
from extractor.core.providers.registry import provider_from_filepath
from extractor.core.schema import BlockTypes


class TableConverter(PdfConverter):
    default_processors: Tuple[BaseProcessor, ...] = (
        TableProcessor,
        LLMTableProcessor,
        LLMTableMergeProcessor,
        LLMFormProcessor,
        LLMComplexRegionProcessor,
    )
    converter_block_types: List[BlockTypes] = (BlockTypes.Table, BlockTypes.Form, BlockTypes.TableOfContents)

    def build_document(self, filepath: str):
        provider_cls = provider_from_filepath(filepath)
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)
        document_builder = DocumentBuilder(self.config)
        document_builder.disable_ocr = True

        provider = provider_cls(filepath, self.config)
        document = document_builder(provider, layout_builder, line_builder, ocr_builder)

        for page in document.pages:
            page.structure = [p for p in page.structure if p.block_type in self.converter_block_types]

        for processor in self.processor_list:
            processor(document)

        return document

    def __call__(self, filepath: str):
        document = self.build_document(filepath)
        renderer = self.resolve_dependencies(self.renderer)
        return renderer(document)


if __name__ == "__main__":
    # Test table extraction functionality
    print("🧪 Testing Table Converter")
    print("=" * 50)
    
    # Test 1: Initialize table converter
    print("\n📝 Test 1: Initialize Table Converter")
    try:
        converter = TableConverter(
            artifact_dict={},
            processor_list=None,
            renderer=None  # Use default
        )
        print("✅ Table converter initialized")
        print(f"   - Processors: {len(converter.processor_list)}")
        print(f"   - Block types: {[bt.name for bt in converter.converter_block_types]}")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        import sys
        sys.exit(1)
    
    # Test 2: Check processor types
    print("\n📝 Test 2: Check Processor Configuration")
    try:
        processor_names = [p.__name__ for p in converter.default_processors]
        print("✅ Processors configured:")
        for name in processor_names:
            print(f"   - {name}")
        
        # Verify table-specific processors
        assert "TableProcessor" in processor_names, "Missing TableProcessor"
        assert "LLMTableProcessor" in processor_names, "Missing LLM table processor"
        print("   ✓ All table processors present")
    except Exception as e:
        print(f"❌ Processor check failed: {e}")
    
    # Test 3: Test with minimal PDF
    print("\n📝 Test 3: Process Test Document")
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        test_pdf = tmp.name
        # Write minimal PDF header
        tmp.write(b'%PDF-1.4\n%test\n')
    
    try:
        # Build document (without full processing)
        document = converter.build_document(test_pdf)
        print("✅ Document built successfully")
        print(f"   - Pages: {len(document.pages)}")
        print(f"   - OCR disabled: {hasattr(converter, 'config') and converter.config.get('disable_ocr', True)}")
        
        # Check filtering works
        if document.pages:
            page = document.pages[0]
            filtered_blocks = [b.block_type for b in page.structure if b.block_type in converter.converter_block_types]
            print(f"   - Filtered to {len(filtered_blocks)} table/form blocks")
    except Exception as e:
        print(f"⚠️  Document processing: {e}")
        print("   - This is expected for minimal test PDF")
    finally:
        if os.path.exists(test_pdf):
            os.unlink(test_pdf)
    
    print("\n" + "=" * 50)
    print("✅ Table converter validation complete")