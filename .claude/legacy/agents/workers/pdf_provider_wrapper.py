#!/usr/bin/env python3
"""
PDF Provider Wrapper

This wraps the existing PDF provider implementation to work with the sub-agent pattern.
It acts as a bridge between the sub-agent architecture and the existing provider code.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio

import typer
from loguru import logger

# Import the existing provider
from extractor.core.providers.pdf import PDFProvider
from extractor.core.providers.registry import ProviderRegistry

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="PDF Provider Wrapper - Bridge to existing implementation")


class PDFProviderWrapper:
    """Wraps existing PDF provider for sub-agent use."""
    
    def __init__(self):
        # Register the provider
        ProviderRegistry.register()
        self.provider = PDFProvider()
    
    async def extract(self, pdf_path: Path, output_path: Optional[Path] = None) -> Dict:
        """Extract PDF using existing provider.
        
        Args:
            pdf_path: Path to PDF file
            output_path: Optional output path
            
        Returns:
            Extraction results
        """
        try:
            # Use the existing provider
            result = await self.provider.extract(str(pdf_path))
            
            # Save if output path provided
            if output_path:
                with open(output_path, 'w') as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Saved extraction to {output_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise
    
    def get_capabilities(self) -> Dict:
        """Get provider capabilities."""
        return {
            "formats": ["pdf"],
            "features": [
                "text_extraction",
                "table_detection", 
                "image_extraction",
                "metadata_extraction",
                "ocr_support"
            ],
            "max_file_size_mb": 100,
            "batch_support": True
        }


# Initialize wrapper
wrapper = PDFProviderWrapper()


@app.command()
def extract(
    pdf_path: Path = typer.Argument(..., help="Path to PDF file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path")
):
    """Extract PDF using existing provider."""
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        raise typer.Exit(1)
    
    async def run():
        result = await wrapper.extract(pdf_path, output)
        logger.info(f"Extraction complete: {len(result.get('blocks', []))} blocks")
    
    asyncio.run(run())


@app.command()
def capabilities():
    """Show provider capabilities."""
    caps = wrapper.get_capabilities()
    
    print("PDF Provider Capabilities:")
    print(f"  Formats: {', '.join(caps['formats'])}")
    print(f"  Features: {', '.join(caps['features'])}")
    print(f"  Max file size: {caps['max_file_size_mb']} MB")
    print(f"  Batch support: {caps['batch_support']}")


# Worker functions
async def working_usage():
    """Demonstrate provider wrapper."""
    test_pdf = Path("test_data/sample.pdf")
    
    if test_pdf.exists():
        result = await wrapper.extract(test_pdf)
        logger.info(f"Extracted {len(result.get('blocks', []))} blocks")
    else:
        logger.info("Test PDF not found, showing capabilities instead")
        caps = wrapper.get_capabilities()
        logger.info(f"Provider supports: {caps['features']}")


async def debug_function():
    """Debug provider functionality."""
    # Test with non-existent file
    try:
        await wrapper.extract(Path("nonexistent.pdf"))
    except Exception as e:
        logger.info(f"Expected error: {e}")
    
    # Show capabilities
    caps = wrapper.get_capabilities()
    logger.info(f"Debug: Provider capabilities: {caps}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()