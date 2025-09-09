#!/usr/bin/env python3
"""
Image Document Extractor Worker

Extracts content from image files using OCR and AI description.
Supports various image formats including multi-page TIFF files.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib
import base64
import io

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL not available - Image support disabled")

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available - OCR support disabled")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("easyocr not available - Advanced OCR disabled")

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Extract content from image documents")
console = Console()


class ImageExtractor:
    """Extract content from image documents."""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".cache" / "extractor" / "images"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize EasyOCR if available
        self.ocr_reader = None
        if EASYOCR_AVAILABLE:
            try:
                self.ocr_reader = easyocr.Reader(['en'])
            except Exception as e:
                logger.warning(f"Failed to initialize EasyOCR: {e}")
        
    async def extract_image(self,
                          image_path: Path,
                          ocr_engine: str = "auto",
                          extract_text: bool = True,
                          extract_regions: bool = True,
                          ai_description: bool = False,
                          max_size_mb: int = 50) -> Dict:
        """Extract content from image file.
        
        Args:
            image_path: Path to image file
            ocr_engine: OCR engine to use (auto, tesseract, easyocr, none)
            extract_text: Whether to extract text using OCR
            extract_regions: Whether to extract text regions/bounding boxes
            ai_description: Whether to generate AI description
            max_size_mb: Maximum file size to process
            
        Returns:
            Extracted content with metadata
        """
        # Validate path
        image_path = Path(image_path).resolve()
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # Check file size
        file_size = image_path.stat().st_size
        if file_size > max_size_mb * 1024 * 1024:
            raise ValueError(f"Image file too large: {file_size / 1024 / 1024:.1f}MB > {max_size_mb}MB")
        
        if not PIL_AVAILABLE:
            raise ImportError("PIL is required for image extraction")
        
        # Check cache
        cache_key = self._get_cache_key(image_path, ocr_engine, extract_regions)
        cached = await self._check_cache(cache_key)
        if cached:
            logger.info(f"Using cached extraction for {image_path.name}")
            return cached
        
        # Open image
        image = Image.open(image_path)
        
        # Extract frames/pages
        frames = []
        frame_count = getattr(image, 'n_frames', 1)
        
        for i in range(frame_count):
            if frame_count > 1:
                image.seek(i)
            
            frame_data = await self._extract_frame(
                image.copy(),
                i,
                ocr_engine,
                extract_text,
                extract_regions
            )
            frames.append(frame_data)
        
        # Generate AI description if requested
        description = ""
        if ai_description:
            description = await self._generate_ai_description(image_path, frames)
        
        # Build result
        result = {
            "frames": frames,
            "metadata": self._extract_metadata(image, image_path),
            "ai_description": description,
            "statistics": self._calculate_statistics(frames)
        }
        
        # Cache result
        await self._cache_result(cache_key, result)
        
        return result
    
    async def _extract_frame(self,
                           frame: Image.Image,
                           frame_idx: int,
                           ocr_engine: str,
                           extract_text: bool,
                           extract_regions: bool) -> Dict:
        """Extract content from a single image frame."""
        frame_data = {
            "index": frame_idx,
            "width": frame.width,
            "height": frame.height,
            "mode": frame.mode,
            "format": frame.format or "unknown",
            "text": "",
            "regions": []
        }
        
        # Convert to RGB if needed for OCR
        if extract_text and frame.mode not in ['RGB', 'L']:
            frame = frame.convert('RGB')
        
        # Perform OCR
        if extract_text:
            if ocr_engine == "auto":
                # Choose best available engine
                if EASYOCR_AVAILABLE and self.ocr_reader:
                    ocr_result = await self._ocr_easyocr(frame, extract_regions)
                elif TESSERACT_AVAILABLE:
                    ocr_result = await self._ocr_tesseract(frame, extract_regions)
                else:
                    logger.warning("No OCR engine available")
                    ocr_result = {"text": "", "regions": []}
            elif ocr_engine == "tesseract" and TESSERACT_AVAILABLE:
                ocr_result = await self._ocr_tesseract(frame, extract_regions)
            elif ocr_engine == "easyocr" and EASYOCR_AVAILABLE:
                ocr_result = await self._ocr_easyocr(frame, extract_regions)
            else:
                ocr_result = {"text": "", "regions": []}
            
            frame_data["text"] = ocr_result["text"]
            frame_data["regions"] = ocr_result["regions"]
        
        # Extract visual features
        frame_data["visual_features"] = self._extract_visual_features(frame)
        
        return frame_data
    
    async def _ocr_tesseract(self, image: Image.Image, extract_regions: bool) -> Dict:
        """Perform OCR using Tesseract."""
        try:
            if extract_regions:
                # Get detailed data with bounding boxes
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                
                regions = []
                text_parts = []
                
                n_boxes = len(data['text'])
                for i in range(n_boxes):
                    if int(data['conf'][i]) > 0:  # Confidence > 0
                        text = data['text'][i].strip()
                        if text:
                            text_parts.append(text)
                            regions.append({
                                "text": text,
                                "bbox": [
                                    data['left'][i],
                                    data['top'][i],
                                    data['left'][i] + data['width'][i],
                                    data['top'][i] + data['height'][i]
                                ],
                                "confidence": data['conf'][i] / 100.0
                            })
                
                return {
                    "text": " ".join(text_parts),
                    "regions": regions
                }
            else:
                # Simple text extraction
                text = pytesseract.image_to_string(image).strip()
                return {"text": text, "regions": []}
                
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return {"text": "", "regions": []}
    
    async def _ocr_easyocr(self, image: Image.Image, extract_regions: bool) -> Dict:
        """Perform OCR using EasyOCR."""
        try:
            # Convert PIL image to numpy array
            import numpy as np
            img_array = np.array(image)
            
            # Run OCR
            results = self.ocr_reader.readtext(img_array)
            
            regions = []
            text_parts = []
            
            for (bbox, text, confidence) in results:
                text_parts.append(text)
                
                if extract_regions:
                    # Convert bbox format
                    x_coords = [p[0] for p in bbox]
                    y_coords = [p[1] for p in bbox]
                    regions.append({
                        "text": text,
                        "bbox": [
                            min(x_coords),
                            min(y_coords),
                            max(x_coords),
                            max(y_coords)
                        ],
                        "confidence": confidence
                    })
            
            return {
                "text": " ".join(text_parts),
                "regions": regions
            }
            
        except Exception as e:
            logger.error(f"EasyOCR failed: {e}")
            return {"text": "", "regions": []}
    
    def _extract_visual_features(self, image: Image.Image) -> Dict:
        """Extract visual features from image."""
        features = {
            "dominant_colors": [],
            "histogram": {},
            "has_transparency": image.mode in ['RGBA', 'LA', 'PA'],
            "is_grayscale": image.mode in ['L', 'LA']
        }
        
        try:
            # Get color histogram
            if image.mode in ['RGB', 'RGBA']:
                # Convert to RGB for analysis
                rgb_image = image.convert('RGB')
                
                # Get dominant colors (simplified)
                small_image = rgb_image.resize((50, 50))
                colors = small_image.getcolors(maxcolors=256)
                if colors:
                    # Sort by frequency
                    colors.sort(key=lambda x: x[0], reverse=True)
                    features["dominant_colors"] = [
                        {"count": count, "rgb": color}
                        for count, color in colors[:5]
                    ]
            
            # Basic histogram
            hist = image.histogram()
            if image.mode == 'RGB':
                features["histogram"] = {
                    "red": hist[0:256],
                    "green": hist[256:512],
                    "blue": hist[512:768]
                }
            elif image.mode == 'L':
                features["histogram"] = {"gray": hist}
                
        except Exception as e:
            logger.debug(f"Failed to extract visual features: {e}")
        
        return features
    
    async def _generate_ai_description(self, image_path: Path, frames: List[Dict]) -> str:
        """Generate AI description of image content."""
        # This is a placeholder for AI integration
        # In production, this would call Claude or another AI service
        
        description = f"Image with {len(frames)} frame(s). "
        
        if frames:
            first_frame = frames[0]
            description += f"Dimensions: {first_frame['width']}x{first_frame['height']}. "
            
            if first_frame.get("text"):
                word_count = len(first_frame["text"].split())
                description += f"Contains {word_count} words of text. "
            
            visual = first_frame.get("visual_features", {})
            if visual.get("is_grayscale"):
                description += "Grayscale image. "
            
        return description
    
    def _extract_metadata(self, image: Image.Image, file_path: Path) -> Dict:
        """Extract image metadata."""
        metadata = {
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size,
            "format": image.format or "unknown",
            "mode": image.mode,
            "width": image.width,
            "height": image.height,
            "frames": getattr(image, 'n_frames', 1)
        }
        
        # Extract EXIF data if available
        if hasattr(image, '_getexif') and image._getexif():
            try:
                from PIL.ExifTags import TAGS
                exif_data = {}
                for tag, value in image._getexif().items():
                    tag_name = TAGS.get(tag, tag)
                    exif_data[tag_name] = value
                metadata["exif"] = exif_data
            except Exception as e:
                logger.debug(f"Failed to extract EXIF: {e}")
        
        # Image info
        if hasattr(image, 'info'):
            metadata["info"] = image.info
        
        return metadata
    
    def _calculate_statistics(self, frames: List[Dict]) -> Dict:
        """Calculate extraction statistics."""
        stats = {
            "total_frames": len(frames),
            "total_text_length": 0,
            "total_regions": 0,
            "avg_confidence": 0.0,
            "frame_dimensions": []
        }
        
        confidence_sum = 0.0
        confidence_count = 0
        
        for frame in frames:
            stats["total_text_length"] += len(frame.get("text", ""))
            regions = frame.get("regions", [])
            stats["total_regions"] += len(regions)
            
            stats["frame_dimensions"].append({
                "width": frame.get("width", 0),
                "height": frame.get("height", 0)
            })
            
            # Calculate average confidence
            for region in regions:
                if "confidence" in region:
                    confidence_sum += region["confidence"]
                    confidence_count += 1
        
        if confidence_count > 0:
            stats["avg_confidence"] = confidence_sum / confidence_count
        
        return stats
    
    def _get_cache_key(self, file_path: Path, ocr_engine: str, extract_regions: bool) -> str:
        """Generate cache key."""
        stat = file_path.stat()
        data = f"{file_path.absolute()}:{stat.st_size}:{stat.st_mtime}:{ocr_engine}:{extract_regions}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    async def _check_cache(self, cache_key: str) -> Optional[Dict]:
        """Check cache for existing extraction."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except:
                pass
        return None
    
    async def _cache_result(self, cache_key: str, result: Dict):
        """Cache extraction result."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to cache: {e}")
    
    def display_image_preview(self, image_path: Path, result: Dict):
        """Display image preview with extracted content."""
        metadata = result.get("metadata", {})
        
        # Create panel content
        content = []
        content.append(f"[bold]Format:[/bold] {metadata.get('format', 'unknown').upper()}")
        content.append(f"[bold]Dimensions:[/bold] {metadata.get('width')}x{metadata.get('height')}")
        content.append(f"[bold]Mode:[/bold] {metadata.get('mode', 'unknown')}")
        content.append(f"[bold]Frames:[/bold] {metadata.get('frames', 1)}")
        
        # Add text preview if available
        if result.get("frames"):
            first_frame = result["frames"][0]
            text = first_frame.get("text", "")
            if text:
                preview = text[:200] + "..." if len(text) > 200 else text
                content.append(f"\n[bold]Extracted Text:[/bold]\n{preview}")
        
        # AI description
        if result.get("ai_description"):
            content.append(f"\n[bold]AI Description:[/bold]\n{result['ai_description']}")
        
        console.print(Panel(
            "\n".join(content),
            title=f"[bold cyan]{image_path.name}[/bold cyan]",
            border_style="cyan"
        ))


# Initialize extractor
extractor = ImageExtractor()


@app.command()
def extract(
    image_file: Path = typer.Argument(..., help="Image file to extract"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    ocr: str = typer.Option("auto", "--ocr", help="OCR engine (auto, tesseract, easyocr, none)"),
    no_regions: bool = typer.Option(False, "--no-regions", help="Don't extract text regions"),
    ai_describe: bool = typer.Option(False, "--ai", "-a", help="Generate AI description"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Show preview")
):
    """Extract content from image file."""
    async def run():
        try:
            result = await extractor.extract_image(
                image_file,
                ocr_engine=ocr,
                extract_text=(ocr != "none"),
                extract_regions=not no_regions,
                ai_description=ai_describe
            )
            
            if preview:
                extractor.display_image_preview(image_file, result)
            
            if output:
                with open(output, 'w') as f:
                    json.dump(result, f, indent=2)
                console.print(f"[green] Saved to {output}[/green]")
            else:
                # Display summary
                stats = result["statistics"]
                metadata = result["metadata"]
                
                table = Table(title="Image Extraction Summary")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Format", metadata.get("format", "unknown").upper())
                table.add_row("Dimensions", f"{metadata.get('width')}x{metadata.get('height')}")
                table.add_row("Frames", str(stats["total_frames"]))
                table.add_row("Text Length", f"{stats['total_text_length']} chars")
                table.add_row("Text Regions", str(stats["total_regions"]))
                
                if stats.get("avg_confidence", 0) > 0:
                    table.add_row("Avg OCR Confidence", f"{stats['avg_confidence']:.1%}")
                
                console.print(table)
        
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(run())


@app.command()
def ocr_compare(
    image_file: Path = typer.Argument(..., help="Image file to compare OCR engines"),
    show_regions: bool = typer.Option(False, "--regions", "-r", help="Show text regions")
):
    """Compare OCR results from different engines."""
    async def run():
        results = {}
        
        # Test each available engine
        engines = []
        if TESSERACT_AVAILABLE:
            engines.append("tesseract")
        if EASYOCR_AVAILABLE:
            engines.append("easyocr")
        
        if not engines:
            console.print("[red]No OCR engines available[/red]")
            return
        
        with Progress() as progress:
            task = progress.add_task("Comparing OCR engines...", total=len(engines))
            
            for engine in engines:
                try:
                    result = await extractor.extract_image(
                        image_file,
                        ocr_engine=engine,
                        extract_regions=True
                    )
                    results[engine] = result
                except Exception as e:
                    results[engine] = {"error": str(e)}
                
                progress.advance(task)
        
        # Display comparison
        table = Table(title="OCR Engine Comparison")
        table.add_column("Engine", style="cyan")
        table.add_column("Text Length", style="green")
        table.add_column("Regions", style="yellow")
        table.add_column("Avg Confidence", style="blue")
        
        for engine, result in results.items():
            if "error" in result:
                table.add_row(engine, "Error", "-", "-")
            else:
                stats = result.get("statistics", {})
                table.add_row(
                    engine,
                    f"{stats.get('total_text_length', 0)} chars",
                    str(stats.get("total_regions", 0)),
                    f"{stats.get('avg_confidence', 0):.1%}"
                )
        
        console.print(table)
        
        # Show text samples
        console.print("\n[bold]Text Samples:[/bold]")
        for engine, result in results.items():
            if "error" not in result and result.get("frames"):
                text = result["frames"][0].get("text", "")[:200]
                if text:
                    console.print(f"\n[cyan]{engine}:[/cyan]")
                    console.print(text + ("..." if len(text) == 200 else ""))
    
    asyncio.run(run())


# Worker functions
async def working_usage():
    """Demonstrate image extraction."""
    logger.info("Testing image extraction...")
    
    if not PIL_AVAILABLE:
        logger.warning("PIL not installed - skipping demo")
        return
    
    # Create test image with text
    image = Image.new('RGB', (400, 200), color='white')
    
    # Add text if PIL.ImageDraw available
    try:
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(image)
        
        # Try to use a font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        draw.text((50, 50), "Test Image", fill='black', font=font)
        draw.text((50, 100), "OCR Extraction Demo", fill='blue', font=font)
        
    except ImportError:
        logger.warning("ImageDraw not available - creating blank image")
    
    # Save test image
    test_file = Path("/tmp/test_image.png")
    image.save(test_file)
    
    # Extract
    result = await extractor.extract_image(test_file)
    
    logger.info(f"\nExtraction complete:")
    logger.info(f"  Format: {result['metadata'].get('format', 'unknown')}")
    logger.info(f"  Dimensions: {result['metadata'].get('width')}x{result['metadata'].get('height')}")
    
    if result.get("frames"):
        frame = result["frames"][0]
        if frame.get("text"):
            logger.info(f"  OCR Text: {frame['text']}")
        else:
            logger.info("  No text extracted (OCR may not be available)")


async def debug_function():
    """Test edge cases in image extraction."""
    logger.info("Testing image edge cases...")
    
    if not PIL_AVAILABLE:
        logger.warning("PIL not installed - skipping tests")
        return
    
    # Test multi-frame TIFF
    images = []
    for i in range(3):
        img = Image.new('RGB', (200, 100), color=['red', 'green', 'blue'][i])
        images.append(img)
    
    test_file = Path("/tmp/test_multiframe.tiff")
    images[0].save(test_file, save_all=True, append_images=images[1:])
    
    result = await extractor.extract_image(test_file)
    logger.info(f"\nMulti-frame TIFF extracted:")
    logger.info(f"  Frames: {result['statistics']['total_frames']}")
    
    # Test different image modes
    for mode in ['L', 'RGBA', 'P']:
        try:
            img = Image.new(mode, (100, 100))
            test_file = Path(f"/tmp/test_{mode.lower()}.png")
            img.save(test_file)
            
            result = await extractor.extract_image(test_file, ocr_engine="none")
            logger.info(f"\n{mode} mode image:")
            logger.info(f"  Mode detected: {result['metadata'].get('mode')}")
            
            visual = result["frames"][0].get("visual_features", {})
            logger.info(f"  Has transparency: {visual.get('has_transparency', False)}")
            logger.info(f"  Is grayscale: {visual.get('is_grayscale', False)}")
            
        except Exception as e:
            logger.error(f"Failed to test {mode} mode: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()