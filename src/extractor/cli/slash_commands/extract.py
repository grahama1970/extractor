"""Extract slash commands for marker.
Module: extract.py

Provides commands for extracting content from PDFs and other documents.
"""

from pathlib import Path
from typing import Optional, List
import typer
from loguru import logger

from .base import SlashCommand, validate_file_path
from extractor.core.converters.pdf import PdfConverter
from extractor.core.config.parser import ConfigParser
from extractor.core.output import output_to_format


class ExtractCommand(SlashCommand):
    """Extract content from documents."""
    
    def __init__(self):
        super().__init__(
            name="marker-extract",
            description="Extract content from PDF documents with various options",
            category="extraction"
        )
    
    def _setup_commands(self):
        """Setup extract command handlers."""
        
        @self.app.command()
        def extract(
            pdf_path: str = typer.Argument(..., help="Path to PDF file"),
            output_format: str = typer.Option("markdown", help="Output format (markdown, json, html)"),
            output_path: Optional[str] = typer.Option(None, help="Output path (default: same as input)"),
            max_pages: Optional[int] = typer.Option(None, help="Maximum pages to process"),
            start_page: int = typer.Option(0, help="Start page (0-indexed)"),
            ocr_all_pages: bool = typer.Option(False, help="Force OCR on all pages"),
            parallel_factor: int = typer.Option(1, help="Parallel processing factor"),
            debug: bool = typer.Option(False, help="Enable debug mode")
        ):
            """Extract content from a PDF document."""
            try:
                # Validate input
                pdf_path = validate_file_path(pdf_path)
                pdf_file = Path(pdf_path)
                
                # Setup output path
                if output_path is None:
                    output_path = pdf_file.parent / f"{pdf_file.stem}.{output_format}"
                else:
                    output_path = Path(output_path)
                
                logger.info(f"Extracting content from {pdf_path}")
                
                # Load configuration
                config_parser = ConfigParser()
                config = config_parser.get_pdf_config()
                
                # Override config with command options
                if max_pages:
                    config.max_pages = max_pages
                config.start_page = start_page
                config.ocr_all_pages = ocr_all_pages
                config.parallel_factor = parallel_factor
                
                # Create converter
                converter = PdfConverter(config=config)
                
                # Convert document
                result = converter.convert(pdf_file)
                
                # Output in requested format
                output_to_format(result, output_path, output_format)
                
                logger.success(f"Extraction complete: {output_path}")
                print(f" Extracted to: {output_path}")
                
                if debug:
                    print(f"\nExtraction stats:")
                    print(f"  Pages: {len(result.pages)}")
                    print(f"  Blocks: {len(result.blocks)}")
                    print(f"  Tables: {sum(1 for b in result.blocks if b.block_type == 'Table')}")
                    print(f"  Code blocks: {sum(1 for b in result.blocks if b.block_type == 'Code')}")
                
            except Exception as e:
                logger.error(f"Extraction failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def batch(
            input_dir: str = typer.Argument(..., help="Directory containing PDFs"),
            output_dir: Optional[str] = typer.Option(None, help="Output directory"),
            output_format: str = typer.Option("markdown", help="Output format"),
            pattern: str = typer.Option("*.pdf", help="File pattern to match"),
            recursive: bool = typer.Option(False, help="Process subdirectories"),
            max_workers: int = typer.Option(4, help="Maximum parallel workers")
        ):
            """Extract content from multiple PDFs in batch."""
            try:
                input_path = Path(input_dir)
                if not input_path.exists():
                    raise typer.BadParameter(f"Directory not found: {input_dir}")
                
                # Find PDFs
                if recursive:
                    pdf_files = list(input_path.rglob(pattern))
                else:
                    pdf_files = list(input_path.glob(pattern))
                
                if not pdf_files:
                    print(f"No files matching '{pattern}' found in {input_dir}")
                    return
                
                print(f"Found {len(pdf_files)} files to process")
                
                # Setup output directory
                if output_dir:
                    output_path = Path(output_dir)
                    output_path.mkdir(parents=True, exist_ok=True)
                else:
                    output_path = input_path
                
                # Process files
                from concurrent.futures import ProcessPoolExecutor, as_completed
                from tqdm import tqdm
                
                config_parser = ConfigParser()
                config = config_parser.get_pdf_config()
                
                def process_file(pdf_file: Path) -> tuple:
                    try:
                        converter = PdfConverter(config=config)
                        result = converter.convert(pdf_file)
                        
                        # Determine output file
                        relative_path = pdf_file.relative_to(input_path)
                        out_file = output_path / relative_path.with_suffix(f".{output_format}")
                        out_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        output_to_format(result, out_file, output_format)
                        return (str(pdf_file), True, None)
                    except Exception as e:
                        return (str(pdf_file), False, str(e))
                
                # Process in parallel
                success_count = 0
                with ProcessPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(process_file, pdf): pdf for pdf in pdf_files}
                    
                    with tqdm(total=len(pdf_files), desc="Processing") as pbar:
                        for future in as_completed(futures):
                            pdf_file, success, error = future.result()
                            if success:
                                success_count += 1
                            else:
                                logger.error(f"Failed to process {pdf_file}: {error}")
                            pbar.update(1)
                
                print(f"\n Processed {success_count}/{len(pdf_files)} files successfully")
                
            except Exception as e:
                logger.error(f"Batch extraction failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def tables(
            pdf_path: str = typer.Argument(..., help="Path to PDF file"),
            output_path: Optional[str] = typer.Option(None, help="Output path for tables"),
            format: str = typer.Option("csv", help="Table format (csv, json, excel)"),
            page: Optional[int] = typer.Option(None, help="Extract from specific page only")
        ):
            """Extract only tables from a PDF."""
            try:
                pdf_path = validate_file_path(pdf_path)
                pdf_file = Path(pdf_path)
                
                logger.info(f"Extracting tables from {pdf_path}")
                
                # Load configuration
                config_parser = ConfigParser()
                config = config_parser.get_pdf_config()
                
                # If specific page requested
                if page is not None:
                    config.start_page = page
                    config.max_pages = 1
                
                # Convert document
                converter = PdfConverter(config=config)
                result = converter.convert(pdf_file)
                
                # Extract tables
                tables = [block for block in result.blocks if block.block_type == 'Table']
                
                if not tables:
                    print("No tables found in the document")
                    return
                
                print(f"Found {len(tables)} tables")
                
                # Setup output
                if output_path:
                    output_base = Path(output_path)
                else:
                    output_base = pdf_file.parent / f"{pdf_file.stem}_tables"
                
                output_base.mkdir(exist_ok=True)
                
                # Export tables
                for i, table in enumerate(tables):
                    if format == "csv":
                        import csv
                        out_file = output_base / f"table_{i+1}.csv"
                        
                        with open(out_file, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            for row in table.rows:
                                writer.writerow([cell.text for cell in row.cells])
                        
                        print(f"  Saved: {out_file}")
                    
                    elif format == "json":
                        import json
                        out_file = output_base / f"table_{i+1}.json"
                        
                        table_data = {
                            "page": table.page_range[0] if table.page_range else None,
                            "bbox": table.polygon.bbox if table.polygon else None,
                            "rows": [
                                [cell.text for cell in row.cells]
                                for row in table.rows
                            ]
                        }
                        
                        with open(out_file, 'w', encoding='utf-8') as f:
                            json.dump(table_data, f, indent=2, ensure_ascii=False)
                        
                        print(f"  Saved: {out_file}")
                    
                    elif format == "excel":
                        try:
                            import pandas as pd
                            out_file = output_base / "tables.xlsx"
                            
                            # Convert all tables to dataframes
                            dfs = []
                            for j, tbl in enumerate(tables):
                                rows = [[cell.text for cell in row.cells] for row in tbl.rows]
                                if rows:
                                    df = pd.DataFrame(rows[1:], columns=rows[0] if len(rows) > 0 else None)
                                    dfs.append((f"Table_{j+1}", df))
                            
                            # Write to Excel
                            with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
                                for sheet_name, df in dfs:
                                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                            
                            print(f"  Saved all tables to: {out_file}")
                            break
                        except ImportError:
                            print("pandas required for Excel export. Install with: pip install pandas openpyxl")
                            raise typer.Exit(1)
                
            except Exception as e:
                logger.error(f"Table extraction failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def code(
            pdf_path: str = typer.Argument(..., help="Path to PDF file"),
            output_dir: Optional[str] = typer.Option(None, help="Output directory for code files"),
            language: Optional[str] = typer.Option(None, help="Filter by language"),
            combine: bool = typer.Option(False, help="Combine all code into one file per language")
        ):
            """Extract code blocks from a PDF."""
            try:
                pdf_path = validate_file_path(pdf_path)
                pdf_file = Path(pdf_path)
                
                logger.info(f"Extracting code blocks from {pdf_path}")
                
                # Convert document
                config_parser = ConfigParser()
                config = config_parser.get_pdf_config()
                converter = PdfConverter(config=config)
                result = converter.convert(pdf_file)
                
                # Extract code blocks
                code_blocks = [block for block in result.blocks if block.block_type == 'Code']
                
                if not code_blocks:
                    print("No code blocks found in the document")
                    return
                
                # Filter by language if specified
                if language:
                    code_blocks = [b for b in code_blocks if b.language and b.language.lower() == language.lower()]
                    if not code_blocks:
                        print(f"No {language} code blocks found")
                        return
                
                print(f"Found {len(code_blocks)} code blocks")
                
                # Setup output directory
                if output_dir:
                    output_path = Path(output_dir)
                else:
                    output_path = pdf_file.parent / f"{pdf_file.stem}_code"
                
                output_path.mkdir(exist_ok=True)
                
                if combine:
                    # Group by language
                    from collections import defaultdict
                    by_language = defaultdict(list)
                    
                    for block in code_blocks:
                        lang = block.language or "unknown"
                        by_language[lang].append(block.text)
                    
                    # Write combined files
                    for lang, codes in by_language.items():
                        ext = {
                            "python": "py",
                            "javascript": "js",
                            "java": "java",
                            "cpp": "cpp",
                            "c": "c",
                            "sql": "sql",
                            "bash": "sh",
                            "shell": "sh"
                        }.get(lang.lower(), "txt")
                        
                        out_file = output_path / f"combined_{lang}.{ext}"
                        with open(out_file, 'w', encoding='utf-8') as f:
                            for i, code in enumerate(codes):
                                if i > 0:
                                    f.write("\n\n" + "="*50 + "\n\n")
                                f.write(code)
                        
                        print(f"  Saved {len(codes)} {lang} blocks to: {out_file}")
                else:
                    # Save individual files
                    for i, block in enumerate(code_blocks):
                        lang = block.language or "unknown"
                        ext = {
                            "python": "py",
                            "javascript": "js",
                            "java": "java",
                            "cpp": "cpp",
                            "c": "c",
                            "sql": "sql",
                            "bash": "sh",
                            "shell": "sh"
                        }.get(lang.lower(), "txt")
                        
                        out_file = output_path / f"code_{i+1}_{lang}.{ext}"
                        with open(out_file, 'w', encoding='utf-8') as f:
                            f.write(block.text)
                        
                        page_info = f" (page {block.page_range[0]})" if block.page_range else ""
                        print(f"  Saved: {out_file}{page_info}")
                
            except Exception as e:
                logger.error(f"Code extraction failed: {e}")
                raise typer.Exit(1)
    
    def get_examples(self) -> List[str]:
        """Get example usage."""
        return [
            "/marker-extract document.pdf",
            "/marker-extract document.pdf --output-format json",
            "/marker-extract document.pdf --max-pages 10 --ocr-all-pages",
            "/marker-extract batch /path/to/pdfs --output-dir /path/to/output",
            "/marker-extract tables report.pdf --format excel",
            "/marker-extract code tutorial.pdf --language python --combine",
        ]