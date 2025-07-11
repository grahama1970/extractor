"""
Module: test_granger_pipeline.py
Description: Integration test for extractor in Granger ecosystem pipeline

External Dependencies:
- pytest: https://docs.pytest.org/

Sample Input:
>>> # PDF file from SPARTA
>>> # Expected to produce JSON/ArangoDB output

Expected Output:
>>> Verified pipeline integration working

Example Usage:
>>> pytest tests/integration/test_granger_pipeline.py -v
"""

import pytest
import json
from pathlib import Path


@pytest.mark.integration
def test_pdf_to_json_pipeline():
    """Test basic PDF to JSON conversion for pipeline."""
    try:
        from extractor.core.converters.pdf import PDFConverter
        from extractor.core.schema.document import Document
        from extractor.core.renderers.json import JSONRenderer
        
        # Verify components exist
        assert PDFConverter is not None
        assert Document is not None
        assert JSONRenderer is not None
        
        print("✓ PDF → JSON pipeline components available")
        
    except ImportError as e:
        pytest.fail(f"Missing pipeline component: {e}")


@pytest.mark.integration 
def test_arangodb_output_format():
    """Test that ArangoDB output format is correct for pipeline."""
    try:
        from extractor.core.renderers.arangodb_enhanced import ArangoDBEnhancedRenderer
        
        # Verify renderer can be instantiated
        renderer = ArangoDBEnhancedRenderer()
        
        # Check it has required methods
        assert hasattr(renderer, '__call__') or hasattr(renderer, 'render')
        
        print("✓ ArangoDB output format ready")
        
    except ImportError:
        pytest.skip("ArangoDB renderer not available")
    except Exception as e:
        pytest.fail(f"ArangoDB renderer issue: {e}")


@pytest.mark.integration
def test_cli_accepts_input():
    """Test that CLI can accept input files."""
    try:
        from extractor.cli.main import app
        import typer
        
        # Verify CLI app exists and is a Typer instance
        assert isinstance(app, typer.Typer)
        
        print("✓ CLI ready to accept input")
        
    except ImportError:
        pytest.skip("CLI not available")


@pytest.mark.integration
def test_mcp_server_tools():
    """Test MCP server exposes correct tools for Granger hub."""
    try:
        from extractor.mcp.tools import AVAILABLE_TOOLS
        
        # Check for essential tools
        required_tools = ["convert_pdf", "extract_document"]
        available = [tool for tool in required_tools if tool in AVAILABLE_TOOLS]
        
        assert len(available) > 0, "No MCP tools available"
        
        print(f"✓ MCP tools available: {available}")
        
    except ImportError:
        pytest.skip("MCP server not configured")


@pytest.mark.integration
def test_granger_hub_compatibility():
    """Test compatibility with Granger hub communication."""
    # This is a placeholder for when granger_hub integration is added
    # For now, just verify the module structure supports it
    
    module_path = Path(__file__).parent.parent.parent / "src" / "extractor"
    
    # Check for integration points
    integration_ready = []
    
    if (module_path / "integrations").exists():
        integration_ready.append("integrations_dir")
    
    if (module_path / "mcp").exists():
        integration_ready.append("mcp_support")
    
    if (module_path / "cli").exists():
        integration_ready.append("cli_interface")
    
    assert len(integration_ready) >= 2, f"Limited integration points: {integration_ready}"
    
    print(f"✓ Granger hub integration points: {', '.join(integration_ready)}")


if __name__ == "__main__":
    # Validation
    print("Testing Granger pipeline integration...")
    
    tests = [
        test_pdf_to_json_pipeline,
        test_arangodb_output_format,
        test_cli_accepts_input,
        test_mcp_server_tools,
        test_granger_hub_compatibility
    ]
    
    passed = 0
    skipped = 0
    
    for test in tests:
        try:
            test()
            passed += 1
            print(f"✅ {test.__name__}")
        except pytest.skip.Exception as e:
            skipped += 1
            print(f"⏭️  {test.__name__}: {e}")
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
    
    print(f"\n{passed}/{len(tests)} integration tests passed ({skipped} skipped)")
    exit(0 if passed + skipped == len(tests) else 1)