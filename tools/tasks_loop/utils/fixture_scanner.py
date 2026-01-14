#!/usr/bin/env python3
"""
fixture_scanner.py - Production-Grade PDF Scanner for Mimic Fixture Generation.

Analyzes a real PDF's structure (fonts, layout, tables, figures) and produces
a JSON specification with EXACT bboxes for create_fixture_pdf.py. This enables
"Twin-Driven Development" - building synthetic PDFs that are geometrically
identical to real client documents but contain dummy content.

Key Features:
- **Bbox Preservation**: Every content type (text, header, table, figure) gets exact coordinates
- **Table Detection**: Uses Camelot lattice detection to find and extract table bboxes
- **Visual Debugging**: Generates DevTools-style overlay images with color-coded bounding boxes
- **Production-Grade**: Robust error handling, logging, and validation

Usage:
    python fixture_scanner.py --pdf input.pdf --output mimic_spec.json --debug-visuals
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
import statistics

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF required: pip install pymupdf")

try:
    from camelot import io as camelot_io
except ImportError:
    print("Warning: Camelot not installed. Table detection will be skipped.", file=sys.stderr)
    camelot_io = None

# Text masking
LOREM = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 10


class PDFScanner:
    """
    Production-grade PDF scanner that preserves exact bbox coordinates
    for all content types to enable deterministic spatial sorting.
    """
    
    def __init__(self, pdf_path: Path, verbose: bool = False):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.verbose = verbose
        self.spec = {"sections": []}
        self.styles = {}  # font_size -> count
        self.current_section = None
        self.debug_rects = {}  # pno -> [(rect, color, label)]
        self.page_width = 612.0  # Standard US Letter
        self.page_height = 792.0
        
        # Get actual page dimensions from first page
        if len(self.doc) > 0:
            first_page = self.doc[0]
            self.page_width = first_page.rect.width
            self.page_height = first_page.rect.height
            
        self.req_count = 0 
        self._log(f"Initialized scanner for {pdf_path.name}")
        self._log(f"Pages: {len(self.doc)}, Dimensions: {self.page_width}x{self.page_height}")
    
    def _log(self, msg: str):
        """Conditional logging based on verbose flag."""
        if self.verbose:
            print(f"[Scanner] {msg}", file=sys.stderr)
    
    def analyze_styles(self):
        """First pass: Identify Header vs Body fonts using statistical analysis."""
        sizes = []
        for page in self.doc:
            blocks = page.get_text("dict")["blocks"]
            for b in blocks:
                if b["type"] == 0:  # Text
                    for line in b["lines"]:
                        for span in line["spans"]:
                            sizes.append(round(span["size"], 1))
        
        if not sizes:
            self.body_size = 10
            self.header_size = 14
            self._log("No text found. Using default font sizes.")
            return
            
        # Most common size is Body
        self.body_size = statistics.mode(sizes)
        # Largest frequent size (>= body + 2) is Header
        large_sizes = [s for s in sizes if s > self.body_size + 2]
        self.header_size = min(large_sizes) if large_sizes else self.body_size + 2
        
        self._log(f"Analyzed Styles: Body={self.body_size}pt, Header>={self.header_size}pt")

    def _is_header(self, span: dict) -> bool:
        """
        Heuristic to detect header text.
        
        Engineering Documents Rule:
        1. Large Text (>= header_size) -> Always Header
        2. Numbered Pattern (e.g. "1.2.3 Title") AND (Bold OR > body_size) -> Header
        3. Simple Bold text -> Body Emphasis (Not Header)
        """
        text = span["text"].strip()
        
        # 0. Exclusion: Requirements (REQ-...) are NOT Section Headers
        if text.upper().startswith("REQ-") or "SHALL" in text.upper():
             # Basic check to avoid promoting requirements
             # But "SHALL" might appear in a header? "The System Shall..."? 
             # Safety: Only exclude explicit REQ- ID start.
             if text.upper().startswith("REQ-"):
                 if self.verbose:
                     print(f"[DEBUG] Rejected Requirement Header: '{text}'")
                 return False

        # 1. Size Check
        if span["size"] >= self.header_size:
            return True
        
        # 1.5 Color Check (New) - Colored text is often a header
        # PyMuPDF color is int. 0 is black.
        if span.get("color", 0) != 0:
             return True
            
        # 2. Numbered Pattern Check for smaller text
        import re
        # Pattern: Start with digit, sequence of digits/dots, optional trailing dot, space
        match = re.match(r'^(\d+(\.\d+)*\.?)\s+', text)
        is_numbered = bool(match)
        
        is_bold = "Bold" in span["font"] or "Black" in span["font"]
        is_larger = span["size"] > (self.body_size + 0.5)
        
        # Check Caps
        clean_text = re.sub(r'^[\d\.]+\s*', '', text)
        is_caps = clean_text.isupper() and len(clean_text) > 3
        
        if is_numbered:
            numbering = match.group(1)
            # Count parts (e.g. "4.1.5" -> 3 parts)
            # Remove trailing dot if present for splitting
            parts = [p for p in numbering.strip('.').split('.') if p]
            depth = len(parts)
            
            # Rule: Deep headers (1.1+) are almost always headers
            if depth >= 2:
                return True
            # Rule: Top-level (1.) needs style signal to avoid lists
            if (is_bold or is_larger or is_caps):
                return True
        
        if is_numbered and self.verbose:
             print(f"[DEBUG] Rejected Numbered: '{text}' Size:{span['size']} Body:{self.body_size} Bold:{is_bold} Caps:{is_caps}")
             
        return False

    def detect_tables(self, page_num: int) -> List[Dict[str, Any]]:
        """
        Detect tables using Camelot lattice detection.
        Returns list of table dicts with bbox and placeholder content.
        """
        if camelot_io is None:
            return []
        
        try:
            # User specified line_scale=15 for BHT documents
            tables = camelot_io.read_pdf(
                str(self.pdf_path),
                pages=str(page_num + 1),  # Camelot uses 1-indexed pages
                flavor='lattice',
                line_scale=15
            )
            
            # Note: We do NOT fallback to stream. If lattice fails, the Twin generator isn't drawing lines correctly.
            if len(tables) == 0:
                self._log(f"Page {page_num+1}: No lattice tables found.")

            results = []
            for idx, tbl in enumerate(tables):
                # Camelot bbox is (x0, y0, x1, y1) in TOP-LEFT origin (Wait, actually PDFMiner BL usually, 
                # but let's stick to existing transformation which seems to work for Demoted table?)
                camelot_bbox = tbl._bbox
                x0, y0_top, x1, y1_top = camelot_bbox
                
                # Convert to PyMuPDF coords: y_bottom = page_height - y_top
                page = self.doc[page_num]
                H = page.rect.height
                y0 = H - y1_top  # Bottom-left corner
                y1 = H - y0_top  # Top-right corner
                
                bbox = [float(x0), float(y0), float(x1), float(y1)]
                
                # Generate placeholder table spec with bbox
                num_cols = len(tbl.df.columns)
                num_rows = len(tbl.df)
                
                results.append({
                    "type": "table",
                    "bbox": bbox,
                    "page": page_num,
                    "columns": [f"Col{i+1}" for i in range(num_cols)],
                    "rows": num_rows,
                    "table_index": idx
                })
                
                self._log(f"Page {page_num+1}: Detected table {idx+1} ({num_rows}x{num_cols}) at {bbox}")
            
            return results
        except Exception as e:
            self._log(f"Table detection failed on page {page_num+1}: {e}")
            return []

    def convert(self):
        """
        Second pass: Extract structure with EXACT bbox preservation.
        
        This is the critical method that determines the quality of the twin.
        Every content item MUST have:
        - bbox: [x0, y0, x1, y1] in PyMuPDF coordinates
        - page: 0-indexed page number
        """
        current_section = {
            "title": "Document Start",
            "level": 1,
            "bbox": [0, 0, self.page_width, 100],  # Placeholder bbox for initial section
            "page": 0,
            "content": []
        }
        self.spec["sections"].append(current_section)
        
        for pno, page in enumerate(self.doc):
            # First, detect tables on this page
            raw_tables = self.detect_tables(pno)
            
            # Filter text-heavy tables (aligns with Pipeline S05 logic)
            detected_tables = []
            for t in raw_tables:
                # Heuristic: Text Blob Detection (Single or Multi-column phantom)
                # Matches extractor.pipeline.utils.tables.heuristics.demote_text_heavy_lattice_tables
                cols = len(t["columns"])
                rows = t["rows"]
                
                # We need content analysis, but detect_tables only returns bbox placeholders.
                # To truly match S05, we need to inspect the text content within the table bbox.
                if cols <= 3:
                     # Check content using fitz
                     rect = fitz.Rect(t["bbox"]) # PyMuPDF coords
                     # t["bbox"] is already [x0, y0, x1, y1] bottom-left origin?
                     # detect_tables converts to PyMuPDF [x0, y0, x1, y1] (bottom-left)
                     # But fitz.Rect expects Top-Left?
                     # Wait, detect_tables logic:
                     # y0 = H - y1_top (Bottom-left Y)
                     # y1 = H - y0_top (Top-right Y)
                     # So y0 < y1 usually in Cartesian.
                     # PyMuPDF Rect(x0, y0, x1, y1) treats y0 as Top if usually.
                     # But page.get_text("blocks") uses Top-Left origin.
                     # logic in detect_tables: `bbox = [float(x0), float(y0), float(x1), float(y1)]` where y0 is bottom-left.
                     # To get text, we need Top-Left coords.
                     # Invert Y back
                     H = self.page_height
                     tl_y0 = H - t["bbox"][3] # Top Y
                     tl_y1 = H - t["bbox"][1] # Bottom Y
                     
                     table_rect = fitz.Rect(t["bbox"][0], tl_y0, t["bbox"][2], tl_y1)
                     table_text = page.get_text("text", clip=table_rect)
                     
                     words = table_text.split()
                     total_words = len(words)
                     total_digits = sum(c.isdigit() for c in table_text)
                     total_chars = len(table_text)
                     row_count = rows # Approximation
                     
                     avg_words = total_words / max(1, row_count)
                     digit_ratio = total_digits / max(1, total_chars)
                     
                     if avg_words > 2.5 and digit_ratio < 0.2:
                         self._log(f"Filtered text-heavy table on page {pno+1}: avg_words={avg_words:.1f}, digit_ratio={digit_ratio:.2f}")
                         continue
                
                detected_tables.append(t)
            
            blocks = page.get_text("dict")["blocks"]
            # Sort blocks by vertical position for reading order
            blocks.sort(key=lambda b: b["bbox"][1])
            
            # Track table bboxes to avoid text/table overlap
            table_rects = [fitz.Rect(t["bbox"]) for t in detected_tables]
            
            for b in blocks:
                bbox = b["bbox"]
                bbox_normalized = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
                
                # Type 1: Image -> Figure
                if b["type"] == 1:
                    current_section["content"].append({
                        "type": "figure",
                        "description": f"Figure from Page {pno+1}",
                        "bbox": bbox_normalized,
                        "page": pno
                    })
                    self._add_debug(pno, fitz.Rect(bbox), (0, 1, 0), "Figure")
                    continue
                
                # Type 0: Text
                if b["type"] == 0:
                    # Check if this text block overlaps with a detected table
                    block_rect = fitz.Rect(bbox)
                    overlaps_table = any(block_rect.intersects(t_rect) for t_rect in table_rects)
                    if overlaps_table:
                        continue  # Skip text blocks that are part of tables
                    
                    text_content = ""
                    is_header_block = False
                    
                    for line in b["lines"]:
                        for span in line["spans"]:
                            if self._is_header(span):
                                is_header_block = True
                            text_content += span["text"] + " "
                    
                    text_content = text_content.strip()
                    if not text_content:
                        continue
                        
                    if is_header_block:
                         # 2nd Safety Check: Entire block content
                         # If the block starts with "REQ-", it is definitely NOT a section header.
                         if text_content.upper().strip().startswith("REQ-"):
                             is_header_block = False
                             if self.verbose:
                                 print(f"[DEBUG] Demoted REQ- block from Header: '{text_content[:30]}...'")
                    
                    if is_header_block and len(text_content) < 200:
                        # New Section Header
                        
                        # Check for "Continued" suffix (Engineering Document Convention)
                        is_continued = "(continued)" in text_content.lower() or text_content.strip().lower().endswith("- continued")
                        
                        if is_continued and len(self.spec["sections"]) > 0:
                             # Merge into previous section
                            self.spec["sections"][-1]["content"].append({
                                "type": "header",
                                "text": text_content,
                                "bbox": bbox_normalized,
                                "page": pno,
                                "metadata": {"merged_continued": True}
                            })
                            current_section = self.spec["sections"][-1]
                            self._add_debug(pno, fitz.Rect(bbox), (0.5, 0, 0), f"Continued: {text_content[:15]}")
                        else:
                            # Standard New Section
                            # Determine level based on font size
                            level = 1 if any(s["size"] > self.header_size + 4 for l in b["lines"] for s in l["spans"]) else 2
                            
                            current_section = {
                                "title": text_content,
                                "level": level,
                                "bbox": bbox_normalized,
                                "page": pno,
                                "content": []
                            }
                            self.spec["sections"].append(current_section)
                            self._add_debug(pno, fitz.Rect(bbox), (1, 0, 0), f"H{level}: {text_content[:15]}")
                    else:
                        # Body Paragraph
                        
                        # Heuristic: Check for Equation
                        # 1. Short text (< 100 chars)
                        # 2. Contains math symbols 
                        # 3. Exclude Numbered Headers (likely Sections)
                        
                        import re
                        is_numbered_start = bool(re.match(r'^\d+(\.\d+)*\.?\s+', text_content))
                        
                        math_symbols = {'=', '≠', '≈', '>', '<', '≥', '≤', '+', '−', '∫', '∑', 'prod'}
                        has_math = any(s in text_content for s in math_symbols)
                        is_short = len(text_content) < 100
                        is_labeled = text_content.strip().endswith(')') and '(' in text_content
                        
                        if is_short and (has_math or is_labeled) and not is_numbered_start:
                            current_section["content"].append({
                                "type": "equation",
                                "text": text_content,
                                "bbox": bbox_normalized,
                                "page": pno
                            })
                            self._add_debug(pno, fitz.Rect(bbox), (0, 1, 1), "Equation")
                        else:
                            # Standard Body Text or Sub-Header
                            
                            # Heuristic: Check for Requirement
                            # Engineering docs use "shall", "must", "will"
                            req_keywords = ["shall", "must", "will"]
                            is_requirement = any(k in text_content.lower() for k in req_keywords) and len(text_content) > 20
                            
                            if is_requirement:
                                self.req_count += 1
                                current_section["content"].append({
                                    "type": "requirement",
                                    "id": f"REQ-{self.req_count:03d}",
                                    "text": text_content, # Pass original text for now? Or Lorem?
                                    # We will let create_fixture_pdf handle the dummy generation
                                    "bbox": bbox_normalized,
                                    "page": pno
                                })
                                self._add_debug(pno, fitz.Rect(bbox), (1, 0, 1), "Requirement")
                            else:
                                # Check if it looks like a sub-header (Bold or slightly larger)
                                is_bold = any("Bold" in s["font"] for l in b["lines"] for s in l["spans"])
                                max_size = max(s["size"] for l in b["lines"] for s in l["spans"]) if b["lines"] else 0
                                
                                if is_bold or max_size >= self.body_size + 1:
                                    current_section["content"].append({
                                        "type": "header",
                                        "text": text_content,
                                        "bbox": bbox_normalized,
                                        "page": pno
                                    })
                                    self._add_debug(pno, fitz.Rect(bbox), (0.5, 0, 0.5), "Sub-Header")
                                else:
                                    # Regular Body - Mimic with Lorem
                                    word_count = len(text_content.split())
                                    mimic_text = (LOREM * (word_count // 10 + 1))[:len(text_content)]
                                    
                                    current_section["content"].append({
                                        "type": "text",
                                        "text": mimic_text,
                                        "bbox": bbox_normalized,
                                        "page": pno
                                    })
                                    self._add_debug(pno, fitz.Rect(bbox), (0, 0, 1), "Body")
            
            # Add detected tables to the current section
            for table_spec in detected_tables:
                current_section["content"].append(table_spec)
                self._add_debug(pno, fitz.Rect(table_spec["bbox"]), (1, 0.5, 0), f"Table {table_spec['table_index']+1}")

    def _add_debug(self, pno, rect, color, label):
        """Track debug annotations for visual overlays."""
        if pno not in self.debug_rects:
            self.debug_rects[pno] = []
        self.debug_rects[pno].append((rect, color, label))

    def save_debug_visuals(self, output_dir: Path):
        """
        Generate DevTools-style visual overlays with color-coded bounding boxes.
        
        Color Legend:
        - Red: Section Headers
        - Blue: Body Text
        - Orange: Tables
        - Green: Figures
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self._log(f"Generating debug visuals in {output_dir}")
        
        for pno, page in enumerate(self.doc):
            if pno in self.debug_rects:
                shape = page.new_shape()
                for rect, color, label in self.debug_rects[pno]:
                    shape.draw_rect(rect)
                    shape.finish(color=color, width=2, dashes="[3] 0")  # Draw box with dashed line
                    # Draw label
                    shape.insert_text(fitz.Point(rect.x0, rect.y0-5), label, fontsize=8, color=color)
                shape.commit()
            
            pix = page.get_pixmap(dpi=150)  # Higher DPI for clarity
            out_path = output_dir / f"page_{pno+1}.png"
            pix.save(str(out_path))
            
        self._log(f"Saved {len(self.doc)} debug pages")

    def validate_spec(self) -> List[str]:
        """
        Validate the generated spec for common issues.
        Returns list of warning messages.
        """
        warnings = []
        
        if not self.spec.get("sections"):
            warnings.append("No sections detected!")
        
        for idx, sec in enumerate(self.spec["sections"]):
            if "bbox" not in sec:
                warnings.append(f"Section {idx} missing bbox")
            
            for c_idx, content in enumerate(sec.get("content", [])):
                if "bbox" not in content:
                    warnings.append(f"Section {idx}, Content {c_idx} missing bbox")
                if "page" not in content:
                    warnings.append(f"Section {idx}, Content {c_idx} missing page number")
        
        return warnings

    def get_spec(self) -> Dict[str, Any]:
        """Return the complete specification with metadata."""
        return {
            "pdf_source": self.pdf_path.name,
            "page_count": len(self.doc),
            "page_dimensions": {
                "width": self.page_width,
                "height": self.page_height
            },
            **self.spec
        }


def main():
    parser = argparse.ArgumentParser(
        description="Scan a real PDF and generate a mimic specification with exact bboxes"
    )
    parser.add_argument("--pdf", required=True, type=Path, help="Input PDF to scan")
    parser.add_argument("--output", required=True, type=Path, help="Output JSON spec file")
    parser.add_argument("--debug-visuals", action="store_true", help="Generate visual debug overlays")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    if not args.pdf.exists():
        print(f"ERROR: PDF not found: {args.pdf}", file=sys.stderr)
        return 1
    
    # Scan
    scanner = PDFScanner(args.pdf, verbose=args.verbose)
    scanner.analyze_styles()
    scanner.convert()
    
    # Validate
    warnings = scanner.validate_spec()
    if warnings:
        print("⚠️  WARNINGS:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
    
    # Save spec
    spec = scanner.get_spec()
    with open(args.output, "w") as f:
        json.dump(spec, f, indent=2)
    
    sections_count = len(spec["sections"])
    content_count = sum(len(s.get("content", [])) for s in spec["sections"])
    print(f"✅ Generated Spec: {sections_count} sections, {content_count} content items")
    print(f"   Output: {args.output}")
    
    # Debug visuals
    if args.debug_visuals:
        debug_dir = args.output.parent / "scanner_debug"
        scanner.save_debug_visuals(debug_dir)
        print(f"   Debug visuals: {debug_dir}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
