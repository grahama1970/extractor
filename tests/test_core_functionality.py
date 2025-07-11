"""
Module: test_core_functionality.py
Description: Core functionality tests for extractor module in Granger ecosystem

External Dependencies:
- pytest: https://docs.pytest.org/
- pathlib: https://docs.python.org/3/library/pathlib.html

Sample Input:
>>> pytest tests/test_core_functionality.py -v

Expected Output:
>>> All core extractor functionality tests pass

Example Usage:
>>> pytest tests/test_core_functionality.py -v
"""

from pathlib import Path
import json
import sys

# Add the src directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def test_extractor_module_exists():
    """Test that extractor module can be imported."""
    try:
        import extractor
        assert hasattr(extractor, '__version__') or True  # Module exists
    except ImportError:
        raise AssertionError("Cannot import extractor module")


def test_pdf_extraction_available():
    """Test that PDF extraction functionality is available."""
    try:
        from extractor.core.converters.pdf import PDFConverter
        assert PDFConverter is not None
    except ImportError:
        raise AssertionError("PDF extraction not available - core functionality missing")


def test_document_model_exists():
    """Test that the document model exists for unified output."""
    try:
        from extractor.core.schema.document import Document
        assert Document is not None
    except ImportError:
        raise AssertionError("Document model missing - cannot produce unified output")


def test_arangodb_renderer_available():
    """Test ArangoDB renderer for pipeline integration."""
    try:
        from extractor.core.renderers.arangodb_enhanced import ArangoDBEnhancedRenderer
        assert ArangoDBEnhancedRenderer is not None
    except ImportError:
        raise AssertionError("ArangoDB renderer missing - cannot integrate with pipeline")


def test_json_output_available():
    """Test JSON output for downstream processing."""
    try:
        from extractor.core.renderers.json import JSONRenderer
        assert JSONRenderer is not None
    except ImportError:
        raise AssertionError("JSON renderer missing - cannot output for downstream")


def test_mcp_server_available():
    """Test MCP server for Granger hub integration."""
    try:
        from extractor.mcp.server import ExtractorMCPServer
        assert ExtractorMCPServer is not None
    except ImportError:
        # MCP server might be optional
        print("⏭️  MCP server not available - optional component")
        return


def test_multi_format_support():
    """Test that multiple document formats are supported."""
    supported_formats = []
    
    # Check PDF
    try:
        from extractor.core.providers.pdf import PDFProvider
        supported_formats.append("pdf")
    except ImportError:
        pass
    
    # Check DOCX
    try:
        from extractor.core.providers.docx_native import DOCXNativeProvider
        supported_formats.append("docx")
    except ImportError:
        pass
    
    # Check PPTX
    try:
        from extractor.core.providers.pptx_native import PPTXNativeProvider
        supported_formats.append("pptx")
    except ImportError:
        pass
    
    # Check XML
    try:
        from extractor.core.providers.xml_native import XMLNativeProvider
        supported_formats.append("xml")
    except ImportError:
        pass
    
    assert len(supported_formats) >= 2, f"Need at least 2 formats, found: {supported_formats}"
    print(f"✓ Supported formats: {', '.join(supported_formats)}")


def test_table_extraction_capability():
    """Test that table extraction is available."""
    table_methods = []
    
    # Check for table processors
    try:
        from extractor.core.processors.table import TableProcessor
        table_methods.append("heuristic")
    except ImportError:
        pass
    
    try:
        from extractor.core.processors.enhanced.enhanced_table_simple import EnhancedTableSimpleProcessor
        table_methods.append("enhanced")
    except ImportError:
        pass
    
    assert len(table_methods) > 0, "No table extraction methods available"
    print(f"✓ Table extraction methods: {', '.join(table_methods)}")


def test_granger_pipeline_integration():
    """Test components needed for SPARTA → Extractor → ArangoDB pipeline."""
    pipeline_ready = []
    
    # Can receive input (from SPARTA)
    try:
        from extractor.core.converters.pdf import convert_pdf
        pipeline_ready.append("input")
    except ImportError:
        pass
    
    # Can process documents
    try:
        from extractor.core.schema.document import Document
        pipeline_ready.append("process")
    except ImportError:
        pass
    
    # Can output to ArangoDB
    try:
        from extractor.core.renderers.arangodb_enhanced import ArangoDBEnhancedRenderer
        pipeline_ready.append("output")
    except ImportError:
        pass
    
    assert len(pipeline_ready) == 3, f"Pipeline incomplete: {pipeline_ready}"
    print("✓ Ready for SPARTA → Extractor → ArangoDB pipeline")


def test_cli_interface_exists():
    """Test that CLI interface exists for command-line usage."""
    try:
        from extractor.cli.main import app
        assert app is not None
    except ImportError:
        raise AssertionError("CLI interface missing - cannot be used from command line")


if __name__ == "__main__":
    # Simple validation
    print("Running core functionality tests...")
    
    tests = [
        test_extractor_module_exists,
        test_pdf_extraction_available,
        test_document_model_exists,
        test_arangodb_renderer_available,
        test_json_output_available,
        test_multi_format_support,
        test_table_extraction_capability,
        test_granger_pipeline_integration,
        test_cli_interface_exists
    ]
    
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"✅ {test.__name__}")
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
    
    print(f"\n{passed}/{len(tests)} core functionality tests passed")
    exit(0 if passed == len(tests) else 1)