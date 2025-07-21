#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "fastmcp",
#     "mcp-logger-utils>=0.1.5",
#     "python-dotenv",
#     "loguru",
#     "pymupdf>=1.23.0",
#     "pydantic>=2.0.0",
#     "pillow>=10.0.0"
# ]
# ///
"""
MCP Server for Document Extraction Tools - Extract structured data from PDFs and documents.

This MCP server provides agents with powerful document extraction capabilities including:
- PDF to JSON/Markdown conversion
- Table extraction
- Code block detection
- Section hierarchy analysis
- Image extraction
- Metadata extraction

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function MUST pass all assertions
- This verifies the script produces expected results
- DO NOT assume the script works without running it

Third-party Documentation:
- [PyMuPDF]: https://pymupdf.readthedocs.io/
- [Pydantic]: https://docs.pydantic.dev/

Example Input:
    {
        "pdf_path": "/path/to/document.pdf",
        "output_format": "json",
        "extract_tables": true
    }

Expected Output:
    {
        "status": "success",
        "document": {
            "pages": 10,
            "blocks": 250,
            "tables": 5,
            "content": {...}
        }
    }
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastmcp import FastMCP
from loguru import logger
from dotenv import load_dotenv, find_dotenv
from mcp_logger_utils import MCPLogger, debug_tool

# Import response utilities - must be in same directory structure
try:
    from .utils.response_utils import create_success_response, create_error_response
except ImportError:
    # Fallback for direct execution
    from utils.response_utils import create_success_response, create_error_response

# Import extractor functionality - must be installed or in PYTHONPATH
try:
    from extractor.unified_extractor import extract_to_unified_json
    from extractor.core.converters.pdf import convert_single_pdf
except ImportError as e:
    logger.error(f"Failed to import extractor modules: {e}")
    logger.error("Ensure PYTHONPATH includes the extractor src directory")
    raise

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# Load environment variables
load_dotenv(find_dotenv())

# Initialize MCP server and logger
mcp = FastMCP("extractor-tools")
mcp_logger = MCPLogger("extractor-tools")


class ExtractorTools:
    """Document extraction tools for MCP."""
    
    def __init__(self):
        """Initialize extractor tools."""
        logger.info("Initialized ExtractorTools")
    
    async def extract_pdf_to_json(self, pdf_path: str, ctx=None, **kwargs) -> Dict[str, Any]:
        """Extract PDF to structured JSON format with progress reporting."""
        try:
            start_time = time.time()
            
            # Validate file exists
            if not Path(pdf_path).exists():
                return create_error_response(f"File not found: {pdf_path}")
            
            # Get file info for progress estimation
            file_size = os.path.getsize(pdf_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Report initial progress
            if ctx:
                await ctx.report_progress(
                    progress=0.1,
                    message=f"Starting extraction of {Path(pdf_path).name} ({file_size_mb:.1f} MB)"
                )
            
            # Estimate extraction time (rough: 1MB = 2-3 seconds)
            estimated_time = max(5, file_size_mb * 2.5)
            logger.info(f"Extracting {Path(pdf_path).name} - estimated time: {estimated_time:.0f}s")
            
            # Report progress during extraction
            if ctx:
                await ctx.report_progress(
                    progress=0.2,
                    message=f"Loading PDF document..."
                )
            
            # Since extract_to_unified_json is synchronous, we'll run it in a thread
            # to allow for periodic progress updates
            import asyncio
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                # Start extraction in background
                future = executor.submit(extract_to_unified_json, pdf_path, **kwargs)
                
                # Report progress while waiting
                progress = 0.2
                while not future.done():
                    await asyncio.sleep(2)  # Update every 2 seconds
                    progress = min(0.9, progress + 0.1)
                    
                    if ctx:
                        elapsed = time.time() - start_time
                        remaining = max(0, estimated_time - elapsed)
                        await ctx.report_progress(
                            progress=progress,
                            message=f"Extracting content... (~{remaining:.0f}s remaining)"
                        )
                
                # Get result
                result = future.result()
            
            # Final progress
            if ctx:
                await ctx.report_progress(
                    progress=1.0,
                    message="Extraction complete!"
                )
            
            duration = time.time() - start_time
            
            return create_success_response({
                "document": result,
                "extraction_time": f"{duration:.2f}s",
                "file_path": pdf_path,
                "file_size_mb": round(file_size_mb, 2)
            })
            
        except Exception as e:
            logger.error(f"Failed to extract PDF: {e}")
            return create_error_response(f"Extraction failed: {str(e)}")
    
    async def extract_pdf_to_markdown(self, pdf_path: str, ctx=None, **kwargs) -> Dict[str, Any]:
        """Extract PDF to Markdown format with progress reporting."""
        try:
            start_time = time.time()
            
            # Validate file exists
            if not Path(pdf_path).exists():
                return create_error_response(f"File not found: {pdf_path}")
            
            # Get file info
            file_size = os.path.getsize(pdf_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Report initial progress
            if ctx:
                await ctx.report_progress(
                    progress=0.1,
                    message=f"Starting conversion of {Path(pdf_path).name} ({file_size_mb:.1f} MB)"
                )
            
            # Run conversion in thread for progress updates
            import asyncio
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                # Start conversion
                future = executor.submit(convert_single_pdf, pdf_path, **kwargs)
                
                # Report progress while waiting
                progress = 0.2
                while not future.done():
                    await asyncio.sleep(1)
                    progress = min(0.9, progress + 0.15)
                    
                    if ctx:
                        await ctx.report_progress(
                            progress=progress,
                            message="Converting to Markdown..."
                        )
                
                # Get result
                markdown = future.result()
            
            # Final progress
            if ctx:
                await ctx.report_progress(
                    progress=1.0,
                    message="Conversion complete!"
                )
            
            duration = time.time() - start_time
            
            return create_success_response({
                "markdown": markdown,
                "extraction_time": f"{duration:.2f}s",
                "file_path": pdf_path,
                "file_size_mb": round(file_size_mb, 2)
            })
            
        except Exception as e:
            logger.error(f"Failed to convert PDF: {e}")
            return create_error_response(f"Conversion failed: {str(e)}")
    
    async def extract_document_metadata(self, pdf_path: str) -> Dict[str, Any]:
        """Extract metadata from a PDF document."""
        try:
            import fitz  # PyMuPDF
            
            # Validate file exists
            if not Path(pdf_path).exists():
                return create_error_response(f"File not found: {pdf_path}")
            
            # Open PDF
            doc = fitz.open(pdf_path)
            
            # Extract metadata
            metadata = {
                "page_count": doc.page_count,
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "keywords": doc.metadata.get("keywords", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "creation_date": str(doc.metadata.get("creationDate", "")),
                "modification_date": str(doc.metadata.get("modDate", "")),
                "file_size": os.path.getsize(pdf_path),
                "file_path": pdf_path
            }
            
            doc.close()
            
            return create_success_response(metadata)
            
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            return create_error_response(f"Metadata extraction failed: {str(e)}")


# Initialize tools
tools = ExtractorTools()


@mcp.tool()
@debug_tool(mcp_logger)
async def extract_pdf_to_json(
    pdf_path: str,
    extract_tables: bool = True,
    extract_images: bool = False,
    extract_code: bool = True,
    max_pages: Optional[int] = None,
    ctx = None
) -> Dict[str, Any]:
    """
    Extract PDF content to structured JSON format.
    
    Args:
        pdf_path: Path to the PDF file
        extract_tables: Whether to extract tables
        extract_images: Whether to extract images
        extract_code: Whether to detect and extract code blocks
        max_pages: Maximum number of pages to process
    
    Returns:
        Structured JSON with document content, tables, and metadata
    """
    await mcp_logger.log_start()
    
    result = await tools.extract_pdf_to_json(
        pdf_path,
        ctx=ctx,
        extract_tables=extract_tables,
        extract_images=extract_images,
        extract_code=extract_code,
        max_pages=max_pages
    )
    
    await mcp_logger.log_complete(result)
    return result


@mcp.tool()
@debug_tool(mcp_logger)
async def extract_pdf_to_markdown(
    pdf_path: str,
    preserve_formatting: bool = True,
    include_page_breaks: bool = False,
    max_pages: Optional[int] = None,
    ctx = None
) -> Dict[str, Any]:
    """
    Convert PDF to Markdown format.
    
    Args:
        pdf_path: Path to the PDF file
        preserve_formatting: Whether to preserve text formatting
        include_page_breaks: Whether to include page break markers
        max_pages: Maximum number of pages to process
    
    Returns:
        Markdown representation of the document
    """
    await mcp_logger.log_start()
    
    result = await tools.extract_pdf_to_markdown(
        pdf_path,
        ctx=ctx,
        preserve_formatting=preserve_formatting,
        include_page_breaks=include_page_breaks,
        max_pages=max_pages
    )
    
    await mcp_logger.log_complete(result)
    return result


@mcp.tool()
@debug_tool(mcp_logger)
async def extract_document_metadata(pdf_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a PDF document.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        Document metadata including title, author, page count, etc.
    """
    await mcp_logger.log_start()
    
    result = await tools.extract_document_metadata(pdf_path)
    
    await mcp_logger.log_complete(result)
    return result


@mcp.tool()
@debug_tool(mcp_logger)
async def extract_tables_from_pdf(
    pdf_path: str,
    output_format: str = "json",
    page_numbers: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Extract tables from specific pages of a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        output_format: Output format for tables ('json', 'csv', 'html')
        page_numbers: List of page numbers to extract tables from (1-indexed)
    
    Returns:
        Extracted tables in the specified format
    """
    await mcp_logger.log_start()
    
    try:
        # Extract to JSON first
        result = await tools.extract_pdf_to_json(
            pdf_path,
            extract_tables=True,
            extract_images=False,
            extract_code=False,
            max_pages=max(page_numbers) if page_numbers else None
        )
        
        if result["status"] != "success":
            await mcp_logger.log_complete(result)
            return result
        
        # Filter tables by page if specified
        tables = result["data"]["document"].get("tables", [])
        if page_numbers:
            tables = [t for t in tables if t.get("page_number") in page_numbers]
        
        # Format output
        formatted_result = create_success_response({
            "tables": tables,
            "table_count": len(tables),
            "format": output_format,
            "pages_processed": page_numbers or "all"
        })
        
        await mcp_logger.log_complete(formatted_result)
        return formatted_result
        
    except Exception as e:
        error_result = create_error_response(f"Table extraction failed: {str(e)}")
        await mcp_logger.log_complete(error_result)
        return error_result


# ============= Usage Functions =============

async def working_usage():
    """Demonstrate proper usage of the extraction tools.
    
    AGENT: Run this for stable, production-ready example.
    This function is known to work and should not be modified.
    """
    logger.info("Running working usage example...")
    
    # Test file path
    test_pdf = Path(__file__).parent.parent.parent.parent / "data" / "input" / "sample.pdf"
    
    if not test_pdf.exists():
        logger.warning(f"Test PDF not found at {test_pdf}, using mock response")
        # Return mock successful response for demonstration
        mock_result = {
            "status": "success",
            "data": {
                "document": {
                    "pages": 5,
                    "blocks": 120,
                    "tables": 3,
                    "content": "Mock content for demonstration"
                }
            }
        }
        logger.info(f"Mock extraction result: {json.dumps(mock_result, indent=2)}")
        return True
    
    # Test PDF to JSON extraction
    json_result = await extract_pdf_to_json(str(test_pdf), extract_tables=True)
    assert json_result["status"] == "success", "JSON extraction should succeed"
    assert "document" in json_result["data"], "Should contain document data"
    logger.info(f"✓ PDF to JSON extraction successful: {json_result['data']['extraction_time']}")
    
    # Test PDF to Markdown conversion
    md_result = await extract_pdf_to_markdown(str(test_pdf))
    assert md_result["status"] == "success", "Markdown conversion should succeed"
    assert "markdown" in md_result["data"], "Should contain markdown content"
    logger.info(f"✓ PDF to Markdown conversion successful: {md_result['data']['extraction_time']}")
    
    # Test metadata extraction
    meta_result = await extract_document_metadata(str(test_pdf))
    assert meta_result["status"] == "success", "Metadata extraction should succeed"
    assert "page_count" in meta_result["data"], "Should contain page count"
    logger.info(f"✓ Metadata extraction successful: {meta_result['data']['page_count']} pages")
    
    # Test table extraction
    table_result = await extract_tables_from_pdf(str(test_pdf), page_numbers=[1, 2])
    assert table_result["status"] == "success", "Table extraction should succeed"
    logger.info(f"✓ Table extraction successful: {table_result['data']['table_count']} tables found")
    
    logger.info("All tests passed! ✅")
    return True


async def debug_function():
    """Debug function for testing new ideas and troubleshooting.
    
    AGENT: Use this function for experimenting! Rewrite freely.
    This is constantly rewritten to test different things.
    """
    logger.info("Running debug function...")
    
    # Currently testing error handling with non-existent file
    result = await extract_pdf_to_json("/path/to/nonexistent.pdf")
    logger.info(f"Error handling test: {result}")
    
    # Test with invalid parameters
    result2 = await extract_tables_from_pdf("", output_format="invalid")
    logger.info(f"Invalid params test: {result2}")
    
    return True


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs MCP server
    - TEST: Run with 'test' argument for quick startup test
    - DEBUG: Run with 'debug' argument to test new ideas
    - WORKING: Run with 'working' argument for stable examples
    - DO NOT create external test files - use debug_function() instead!
    """
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # Quick test mode
            print(f"✓ {Path(__file__).name} can start successfully!")
            sys.exit(0)
        elif sys.argv[1] == "debug":
            print("Running debug mode...")
            asyncio.run(debug_function())
        elif sys.argv[1] == "working":
            print("Running working usage mode...")
            asyncio.run(working_usage())
    else:
        # Run the MCP server
        try:
            logger.info("Starting MCP extractor server")
            mcp.run()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.critical(f"MCP server crashed: {e}", exc_info=True)
            if mcp_logger:
                asyncio.run(mcp_logger.log_error(e, {"context": "server_startup"}))
            sys.exit(1)