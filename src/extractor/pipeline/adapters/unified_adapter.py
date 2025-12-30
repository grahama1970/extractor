"""
Unified Adapter: UnifiedDocument -> Pipeline Artifacts
------------------------------------------------------
Converts UnifiedDocument into the JSON formats expected by Stage 07.

Outputs:
- 04_sections.json (Sections with nested blocks)
- 05_tables.json (Tables)
- 06_figures.json (Figures)
"""

from pathlib import Path
from typing import Dict, Any, List
import json
from collections import defaultdict

from extractor.core.schema.unified_document import (
    UnifiedDocument,
    BaseBlock,
    BlockType,
    TableBlock,
    ImageBlock,
)
from loguru import logger


class UnifiedAdapter:
    """
    Adapter to convert UnifiedDocument to pipeline artifact JSONs.
    """
    
    def __init__(self, unified_doc: UnifiedDocument, output_dir: Path):
        self.doc = unified_doc
        self.output_dir = output_dir
        
    def write_artifacts(self):
        """Main entry point to write all artifacts."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._write_sections()
        self._write_tables()
        self._write_figures()
        
        logger.info(f"UnifiedAdapter: Wrote artifacts to {self.output_dir}")
        
    def _write_sections(self):
        """
        Write 04_sections.json
        
        Format expected by Stage 07:
        {
            "sections": [
                {
                    "id": "section-001",
                    "title": "Introduction",
                    "page_start": 0,
                    "page_end": 0,
                    "parent_id": null,
                    "blocks": [
                        {
                            "id": "block-001",
                            "page": 0,
                            "bbox": [x0, y0, x1, y1],
                            "text": "...",
                            "block_type": "Text"
                        }
                    ]
                }
            ],
            "section_count": 1
        }
        """
        sections_dir = self.output_dir / "04_section_builder" / "json_output"
        sections_dir.mkdir(parents=True, exist_ok=True)
        
        # Group blocks by section (using hierarchy or headings)
        sections = []
        current_section = None
        section_counter = 0
        
        # Simple strategy: Each HEADING starts a new section
        # All subsequent blocks until next HEADING belong to that section
        
        for block in self.doc.blocks:
            if block.type == BlockType.HEADING:
                # Flush previous section
                if current_section:
                    sections.append(current_section)
                
                # Start new section
                section_counter += 1
                section_id = f"section-{section_counter:03d}"
                current_section = {
                    "id": section_id,
                    "title": str(block.content),
                    "page_start": block.metadata.page_number or 0,
                    "page_end": block.metadata.page_number or 0,
                    "parent_id": None,
                    "blocks": []
                }
            elif block.type in [BlockType.PARAGRAPH, BlockType.TEXT, BlockType.LISTITEM]:
                # Add to current section
                if not current_section:
                    # Create default section if none exists
                    section_counter += 1
                    section_id = f"section-{section_counter:03d}"
                    current_section = {
                        "id": section_id,
                        "title": "Untitled Section",
                        "page_start": 0,
                        "page_end": 0,
                        "parent_id": None,
                        "blocks": []
                    }
                
                # Convert block to pipeline format
                pipeline_block = {
                    "id": block.id,
                    "page": block.metadata.page_number or 0,
                    "bbox": block.metadata.bbox or [0, 0, 0, 0],
                    "text": str(block.content),
                    "block_type": "Text"  # Normalize to "Text" for pipeline
                }
                current_section["blocks"].append(pipeline_block)
        
        # Flush last section
        if current_section:
            sections.append(current_section)
        
        # If no sections created, create a default one
        if not sections:
            sections.append({
                "id": "section-001",
                "title": self.doc.metadata.title or "Document",
                "page_start": 0,
                "page_end": 0,
                "parent_id": None,
                "blocks": []
            })
        
        output = {
            "sections": sections,
            "section_count": len(sections)
        }
        
        out_path = sections_dir / "04_sections.json"
        out_path.write_text(json.dumps(output, indent=2))
        logger.info(f"Wrote {len(sections)} sections to {out_path}")
        
    def _write_tables(self):
        """
        Write 05_tables.json
        
        Format:
        {
            "tables": [
                {
                    "id": "table-001",
                    "page_index": 0,
                    "bbox": [x0, y0, x1, y1],
                    "csv": "...",
                    "html": "..."
                }
            ]
        }
        """
        tables_dir = self.output_dir / "05_table_extractor" / "json_output"
        tables_dir.mkdir(parents=True, exist_ok=True)
        
        tables = []
        for block in self.doc.blocks:
            if isinstance(block, TableBlock):
                # Convert cells to CSV
                csv_lines = []
                if block.cells:
                    # Group by row
                    rows_dict = defaultdict(list)
                    for cell in block.cells:
                        rows_dict[cell.row].append((cell.col, cell.content))
                    
                    for row_idx in sorted(rows_dict.keys()):
                        row_cells = sorted(rows_dict[row_idx], key=lambda x: x[0])
                        csv_lines.append(",".join(f'"{cell[1]}"' for cell in row_cells))
                
                csv_data = "\n".join(csv_lines)
                
                table_obj = {
                    "id": block.id,
                    "page_index": block.metadata.page_number or 0,
                    "bbox": block.metadata.bbox or [0, 0, 0, 0],
                    "csv": csv_data,
                    "html": block.content.get("html", "") if isinstance(block.content, dict) else ""
                }
                tables.append(table_obj)
        
        output = {
            "tables": tables,
            "timestamp": int(self.doc.metadata.extraction_date.timestamp()) if self.doc.metadata.extraction_date else 0
        }
        
        out_path = tables_dir / "05_tables.json"
        out_path.write_text(json.dumps(output, indent=2))
        logger.info(f"Wrote {len(tables)} tables to {out_path}")
        
    def _write_figures(self):
        """
        Write 06_figures.json
        
        Format:
        {
            "figures": [
                {
                    "figure_id": "fig-001",
                    "page": 0,
                    "bbox": [x0, y0, x1, y1],
                    "image_path": "..."
                }
            ]
        }
        """
        figures_dir = self.output_dir / "06_figure_extractor" / "json_output"
        figures_dir.mkdir(parents=True, exist_ok=True)
        
        figures = []
        for block in self.doc.blocks:
            if isinstance(block, ImageBlock):
                figure_obj = {
                    "figure_id": block.id,
                    "id": block.id,
                    "page": block.metadata.page_number or 0,
                    "bbox": block.metadata.bbox or [0, 0, 0, 0],
                    "image_path": block.src,
                    "ai_description": block.alt or ""
                }
                figures.append(figure_obj)
        
        output = {
            "figures": figures
        }
        
        out_path = figures_dir / "06_figures.json"
        out_path.write_text(json.dumps(output, indent=2))
        logger.info(f"Wrote {len(figures)} figures to {out_path}")
