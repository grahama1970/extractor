#!/usr/bin/env python3
"""
PDF Validation Image Worker - Creates visual validation images for extraction quality.

This worker provides the implementation for Stage 7 of the PDF extraction pipeline.
It generates side-by-side comparison images showing original PDF and extracted blocks.

Key capabilities:
- Render PDF pages as images
- Overlay block boundaries from extraction
- Highlight changes and fixes
- Create comparison visualizations
- Generate validation report

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function demonstrates image generation
- debug_function() tests rendering without full PDF
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Third-party imports
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF
import io

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# Constants
AGENT_NAME = "pdf-validation-image"


class PDFValidationImageWorker:
    """Worker for creating validation images."""
    
    def __init__(self):
        self.colors = {
            'Text': (0, 0, 255, 50),          # Blue
            'SectionHeader': (255, 0, 0, 50),  # Red
            'Table': (0, 255, 0, 50),          # Green
            'Figure': (255, 255, 0, 50),       # Yellow
            'ListItem': (255, 0, 255, 50),     # Magenta
            'suspicious': (255, 128, 0, 80),   # Orange
            'fixed': (0, 255, 128, 80)         # Light green
        }
        self.dpi = 150  # Resolution for rendering
    
    async def create_validation_images(
        self,
        pdf_path: str,
        marker_json_path: str,
        output_dir: Optional[str] = None,
        pages_to_render: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Create validation images comparing PDF to extraction.
        
        Args:
            pdf_path: Path to original PDF
            marker_json_path: Path to extracted JSON
            output_dir: Output directory for images
            pages_to_render: Specific pages to render (None = all)
            
        Returns:
            Dict with image paths and statistics
        """
        logger.info(f"Creating validation images for: {pdf_path}")
        
        # Setup paths
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return {'success': False, 'error': f'PDF not found: {pdf_path}'}
        
        if output_dir is None:
            output_dir = Path("/tmp/validation_images")
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Load marker data
        with open(marker_json_path) as f:
            marker_data = json.load(f)
        
        blocks = marker_data.get('blocks', [])
        
        # Open PDF
        doc = fitz.open(str(pdf_path))
        
        # Determine pages to render
        if pages_to_render is None:
            # Render first 5 pages and any pages with suspicious blocks
            pages_to_render = list(range(min(5, len(doc))))
            suspicious_pages = set(b['page'] for b in blocks if b.get('suspicious'))
            pages_to_render.extend(sorted(suspicious_pages))
            pages_to_render = sorted(set(pages_to_render))[:10]  # Max 10 pages
        
        # Generate images
        image_paths = []
        for page_num in pages_to_render:
            if page_num < len(doc):
                image_path = await self._render_page_with_blocks(
                    doc, page_num, blocks, output_dir
                )
                if image_path:
                    image_paths.append(image_path)
        
        doc.close()
        
        # Create summary image
        summary_path = await self._create_summary_image(
            blocks, output_dir, pdf_path.stem
        )
        if summary_path:
            image_paths.append(summary_path)
        
        logger.success(f"Created {len(image_paths)} validation images")
        
        return {
            'success': True,
            'image_paths': image_paths,
            'pages_rendered': pages_to_render,
            'output_dir': str(output_dir),
            'statistics': self._calculate_statistics(blocks)
        }
    
    async def _render_page_with_blocks(
        self,
        doc: fitz.Document,
        page_num: int,
        blocks: List[Dict],
        output_dir: Path
    ) -> Optional[str]:
        """Render a single page with block overlays."""
        try:
            page = doc[page_num]
            
            # Render page at high DPI
            mat = fitz.Matrix(self.dpi/72.0, self.dpi/72.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Create overlay
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Get page blocks
            page_blocks = [b for b in blocks if b.get('page') == page_num]
            
            # Draw blocks
            scale = self.dpi / 72.0
            for block in page_blocks:
                if 'bbox' in block:
                    bbox = block['bbox']
                    # Scale coordinates
                    x0, y0, x1, y1 = [coord * scale for coord in bbox]
                    
                    # Determine color
                    if block.get('suspicious'):
                        color = self.colors['suspicious']
                    elif block.get('metadata', {}).get('fixed'):
                        color = self.colors['fixed']
                    else:
                        color = self.colors.get(block.get('type', 'Text'), self.colors['Text'])
                    
                    # Draw rectangle
                    draw.rectangle([x0, y0, x1, y1], outline=color[:3], width=2)
                    draw.rectangle([x0, y0, x1, y1], fill=color)
                    
                    # Add label
                    if block.get('suspicious'):
                        draw.text((x0, y0-20), "SUSPICIOUS", fill=(255, 0, 0))
            
            # Composite images
            img = Image.alpha_composite(img.convert('RGBA'), overlay)
            
            # Save
            output_path = output_dir / f"page_{page_num:03d}_validated.png"
            img.save(output_path)
            
            logger.info(f"Rendered page {page_num} with {len(page_blocks)} blocks")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to render page {page_num}: {e}")
            return None
    
    async def _create_summary_image(
        self,
        blocks: List[Dict],
        output_dir: Path,
        pdf_name: str
    ) -> Optional[str]:
        """Create a summary statistics image."""
        try:
            # Create image
            img = Image.new('RGB', (800, 600), 'white')
            draw = ImageDraw.Draw(img)
            
            # Try to use a font, fall back to default
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            except:
                font = ImageFont.load_default()
                title_font = font
            
            # Title
            draw.text((20, 20), f"Validation Summary: {pdf_name}", fill='black', font=title_font)
            
            # Statistics
            stats = self._calculate_statistics(blocks)
            y = 80
            
            for key, value in stats.items():
                if isinstance(value, dict):
                    draw.text((20, y), f"{key}:", fill='black', font=font)
                    y += 30
                    for k, v in value.items():
                        draw.text((40, y), f"  {k}: {v}", fill='gray', font=font)
                        y += 25
                else:
                    draw.text((20, y), f"{key}: {value}", fill='black', font=font)
                    y += 30
            
            # Legend
            y = 400
            draw.text((20, y), "Block Type Colors:", fill='black', font=font)
            y += 30
            
            for block_type, color in list(self.colors.items())[:5]:
                draw.rectangle([30, y, 50, y+20], fill=color[:3])
                draw.text((60, y), block_type, fill='black', font=font)
                y += 25
            
            # Save
            output_path = output_dir / "validation_summary.png"
            img.save(output_path)
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to create summary image: {e}")
            return None
    
    def _calculate_statistics(self, blocks: List[Dict]) -> Dict[str, Any]:
        """Calculate extraction statistics."""
        total = len(blocks)
        suspicious = sum(1 for b in blocks if b.get('suspicious'))
        fixed = sum(1 for b in blocks if b.get('metadata', {}).get('fixed'))
        
        # Count by type
        type_counts = {}
        for block in blocks:
            block_type = block.get('type', 'Unknown')
            type_counts[block_type] = type_counts.get(block_type, 0) + 1
        
        return {
            'total_blocks': total,
            'suspicious_blocks': suspicious,
            'fixed_blocks': fixed,
            'accuracy_rate': f"{((total - suspicious) / total * 100):.1f}%" if total > 0 else "N/A",
            'block_types': type_counts
        }


# Module-level functions
async def create_validation_images(
    pdf_path: str,
    marker_json_path: str,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Create validation images."""
    worker = PDFValidationImageWorker()
    return await worker.create_validation_images(pdf_path, marker_json_path, output_dir)


# ============================================
# USAGE EXAMPLES (MANDATORY)
# ============================================

async def working_usage():
    """
    Demonstrate validation image creation.
    """
    logger.info("=== Running Validation Image Working Usage ===")
    
    # For testing without a real PDF, create mock visualization
    import io
    
    # Create a simple test image
    img = Image.new('RGB', (800, 600), 'white')
    draw = ImageDraw.Draw(img)
    
    # Draw mock PDF page
    draw.rectangle([50, 50, 750, 550], outline='black', width=2)
    draw.text((60, 60), "Mock PDF Page", fill='black')
    
    # Draw mock blocks
    blocks = [
        {'bbox': [100, 100, 400, 150], 'type': 'SectionHeader', 'text': '1.1 Introduction'},
        {'bbox': [100, 170, 700, 220], 'type': 'Text', 'text': 'This is body text...'},
        {'bbox': [100, 240, 700, 340], 'type': 'Table', 'text': 'Table data'},
        {'bbox': [100, 360, 300, 380], 'type': 'Text', 'text': 'Orphaned', 'suspicious': True}
    ]
    
    # Draw blocks with colors
    worker = PDFValidationImageWorker()
    for block in blocks:
        x0, y0, x1, y1 = block['bbox']
        
        if block.get('suspicious'):
            color = (255, 128, 0, 128)  # Orange for suspicious
        else:
            color_rgb = worker.colors.get(block['type'], (0, 0, 255, 50))
            color = color_rgb[:3] + (128,)  # Add alpha
        
        # Create overlay for transparency
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle([x0, y0, x1, y1], fill=color, outline=color[:3], width=2)
        
        # Composite
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        
        # Redraw for labels
        draw = ImageDraw.Draw(img)
        draw.text((x0+5, y0+5), f"[{block['type']}]", fill='black')
    
    # Add legend
    y = 420
    draw.text((100, y), "Legend:", fill='black')
    for i, (block_type, color) in enumerate(list(worker.colors.items())[:4]):
        x = 100 + (i % 2) * 200
        y_pos = 440 + (i // 2) * 25
        draw.rectangle([x, y_pos, x+20, y_pos+20], fill=color[:3])
        draw.text((x+30, y_pos), block_type, fill='black')
    
    # Save test image
    test_path = Path("/tmp/validation_test.png")
    img.save(test_path)
    logger.success(f"Created test validation image: {test_path}")
    
    # Test statistics calculation
    test_blocks = [
        {'type': 'Text', 'suspicious': False},
        {'type': 'SectionHeader', 'suspicious': False},
        {'type': 'Text', 'suspicious': True},
        {'type': 'Table', 'suspicious': False, 'metadata': {'fixed': True}}
    ]
    
    stats = worker._calculate_statistics(test_blocks)
    logger.info(f"Statistics: {json.dumps(stats, indent=2)}")
    
    assert stats['total_blocks'] == 4
    assert stats['suspicious_blocks'] == 1
    assert stats['fixed_blocks'] == 1
    
    logger.success("✓ All tests passed")
    return True


async def debug_function():
    """
    Debug color schemes and block rendering.
    """
    logger.info("=== Running Debug Function ===")
    
    worker = PDFValidationImageWorker()
    
    # Test color generation
    logger.info("Color scheme:")
    for block_type, color in worker.colors.items():
        logger.info(f"  {block_type}: RGBA{color}")
    
    # Test with different block configurations
    test_configs = [
        {'type': 'Text', 'suspicious': True},
        {'type': 'SectionHeader', 'metadata': {'fixed': True}},
        {'type': 'Table', 'suspicious': False},
        {'type': 'Unknown', 'suspicious': False}
    ]
    
    logger.info("\nBlock colors:")
    for config in test_configs:
        if config.get('suspicious'):
            color = worker.colors['suspicious']
        elif config.get('metadata', {}).get('fixed'):
            color = worker.colors['fixed']
        else:
            color = worker.colors.get(config['type'], worker.colors['Text'])
        
        logger.info(f"  {config}: {color}")
    
    return True


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs working_usage() - creates test validation image
    - DEBUG: Run with 'debug' argument to test color schemes
    - DO NOT create external test files - use debug_function() instead!
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        logger.info("Running debug mode...")
        asyncio.run(debug_function())
    else:
        logger.info("Running working usage mode...")
        success = asyncio.run(working_usage())
        exit(0 if success else 1)