#!/usr/bin/env python3
"""
create_fixture.py - Generate test PDF fixtures from content specifications.

This script creates deterministic PDFs with known, extractable content
and auto-generates the corresponding SPEC.md with expected values.

Usage:
    # From JSON spec file
    python create_fixture.py --spec content_spec.json --name my_fixture

    # From inline JSON
    python create_fixture.py --inline '{"sections": [...]}' --name my_fixture

The generated fixture will be in: fixtures/{name}/
    - source.pdf      (the generated PDF)
    - SPEC.md         (auto-generated with expected values)
    - contracts/      (after running compile_contracts.py)
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF required: pip install pymupdf")

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
TASKS_LOOP_DIR = SCRIPT_DIR.parent
FIXTURES_DIR = TASKS_LOOP_DIR / "fixtures"

# Fonts
FONT_TITLE = "hebo"  # Helvetica-Bold
FONT_BODY = "helv"


class PDFBuilder:
    """Build PDF documents from content specifications."""

    def __init__(self, style: str = "standard"):
        self.doc = fitz.open()
        self.style = style
        self.page = None
        self.y = 72  # Current y position
        self.margin = 72
        self.page_width = 612  # Letter width
        self.page_height = 792  # Letter height

        # Track what we create for SPEC generation
        self.created = {
            "sections": [],
            "tables": [],
            "figures": [],
            "requirements": [],
            "equations": [],
            "annotations": [],
        }

    def new_page(self):
        """Add a new page and reset position."""
        self.page = self.doc.new_page(width=self.page_width, height=self.page_height)
        self.y = 72
        return self.page

    def ensure_space(self, needed: float):
        """Ensure there's enough space on page, or create new one."""
        if self.y + needed > self.page_height - 72:
            self.new_page()

    def add_section(self, title: str, level: int = 1) -> dict:
        """Add a section header."""
        if self.page is None:
            self.new_page()

        self.ensure_space(40)

        # Increased sizes for clarity against body text (10pt/11pt)
        fontsize = {1: 24, 2: 20, 3: 16}.get(level, 14)

        # Add section header
        point = fitz.Point(self.margin, self.y)
        self.page.insert_text(point, title, fontname=FONT_TITLE, fontsize=fontsize)

        section_info = {
            "id": len(self.created["sections"]),
            "title": title,
            "page": len(self.doc) - 1,
            "level": level,
            "y": self.y,
        }
        self.created["sections"].append(section_info)

        self.y += fontsize + 12
        return section_info

    def add_text(self, text: str) -> dict:
        """Add body text."""
        if self.page is None:
            self.new_page()

        self.ensure_space(30)

        # Track bbox for this text block
        start_y = self.y
        start_page = len(self.doc) - 1

        # Simple text wrapping
        max_width = self.page_width - 2 * self.margin
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            current_line.append(word)
            test_line = " ".join(current_line)
            # Approximate width (8 chars per inch at 10pt)
            if len(test_line) * 6 > max_width:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        for line in lines:
            self.ensure_space(14)
            point = fitz.Point(self.margin, self.y)
            self.page.insert_text(point, line, fontname=FONT_BODY, fontsize=10)
            self.y += 14

        end_y = self.y
        self.y += 8  # Paragraph spacing

        # Record text block with bbox
        text_info = {
            "type": "text",
            "page": start_page,
            "bbox": [self.margin, start_y, self.page_width - self.margin, end_y],
            "text": text[:100],  # Store snippet for debugging
        }
        return text_info

    def add_sub_header(self, text: str) -> dict:
        """Add a sub-header (emphasized text)."""
        if self.page is None:
            self.new_page()

        self.ensure_space(25)

        point = fitz.Point(self.margin, self.y)
        self.page.insert_text(point, text, fontname=FONT_BODY, fontsize=11)

        self.y += 20

        # Track as text for now, or maybe simplified section?
        # For S04 detection, it just needs to be bold/large.
        return {"type": "header", "text": text, "page": len(self.doc) - 1}

    def add_table(self, columns: List[str], rows: List[List[str]]) -> dict:
        """Add a simple table."""
        if self.page is None:
            self.new_page()

        # Track bbox - start position
        table_start_page = len(self.doc) - 1
        table_start_y = self.y
        table_x0 = self.margin
        table_x1 = self.page_width - self.margin

        row_height = 20
        # Prepare columns
        col_width = (self.page_width - 2 * self.margin) / len(columns)

        def draw_header():
            # Header row
            for i, col in enumerate(columns):
                x = self.margin + i * col_width + 5
                self.page.insert_text(
                    fitz.Point(x, self.y),
                    col,
                    fontname=FONT_TITLE,
                    fontsize=10,
                )
            self.y += row_height

            # Draw header line
            self.page.draw_line(
                fitz.Point(self.margin, self.y - 5),
                fitz.Point(self.page_width - self.margin, self.y - 5),
            )

        # Initial Header
        if self.page is None:
            self.new_page()

        # Check if even the header fits, else new page
        self.ensure_space(row_height * 2)
        draw_header()

        # Data rows
        for row_idx, row in enumerate(rows):
            # Check space for next row
            if self.y + row_height > self.page_height - 72:
                self.new_page()
                draw_header()

            # Draw row separator (top) - already drawn by header or previous row?
            # Actually, let's draw a box around each cell to be safe for Lattice

            for i, cell in enumerate(row):
                x = self.margin + i * col_width + 5

                # Draw cell borders
                cell_rect = fitz.Rect(
                    self.margin + i * col_width,
                    self.y,
                    self.margin + (i + 1) * col_width,
                    self.y + row_height,
                )
                self.page.draw_rect(cell_rect, color=(0, 0, 0), width=0.5)

                self.page.insert_text(
                    fitz.Point(x, self.y + 12),
                    str(cell)[:20],  # Truncate long cells
                    fontname=FONT_BODY,
                    fontsize=9,
                )
            self.y += row_height

        # Final bbox encompasses all drawn rows
        table_end_y = self.y
        table_end_page = len(self.doc) - 1

        table_info = {
            "id": f"tbl_{len(self.created['tables'])}",
            "page": table_start_page,  # Page where table STARTS
            "page_end": table_end_page,  # Page where table ENDS (for multi-page tables)
            "bbox": [table_x0, table_start_y, table_x1, table_end_y],
            "columns": columns,
            "rows": len(rows),
        }
        self.created["tables"].append(table_info)

        self.y += 15
        return table_info

    def add_figure(self, description: str, width: int = 200, height: int = 150) -> dict:
        """Add a figure placeholder with caption."""
        if self.page is None:
            self.new_page()

        self.ensure_space(height + 40)

        # Draw placeholder rectangle
        rect = fitz.Rect(
            self.margin,
            self.y,
            self.margin + width,
            self.y + height,
        )
        self.page.draw_rect(rect, color=(0.8, 0.8, 0.8), fill=(0.95, 0.95, 0.95))

        # Add "Figure" text in center
        center_x = self.margin + width / 2 - 20
        center_y = self.y + height / 2
        self.page.insert_text(
            fitz.Point(center_x, center_y),
            f"[Figure {len(self.created['figures']) + 1}]",
            fontsize=10,
        )

        self.y += height + 5

        # Caption
        caption = f"Figure {len(self.created['figures']) + 1}: {description}"
        self.page.insert_text(
            fitz.Point(self.margin, self.y),
            caption,
            fontname=FONT_BODY,
            fontsize=9,
        )

        figure_info = {
            "id": f"fig_{len(self.created['figures'])}",
            "page": len(self.doc) - 1,
            "description": description,
            "bbox": list(rect),
        }
        self.created["figures"].append(figure_info)

        self.y += 25
        return figure_info

    def add_requirement(self, req_id: str, text: str, req_type: str = "Functional") -> dict:
        """Add a requirement statement."""
        if self.page is None:
            self.new_page()

        self.ensure_space(30)

        full_text = f"{req_id}: {text}"
        self.page.insert_text(
            fitz.Point(self.margin, self.y),
            full_text[:80],  # Truncate for display
            fontname=FONT_BODY,
            fontsize=10,
        )

        req_info = {
            "id": req_id,
            "text": text,
            "type": req_type,
            "page": len(self.doc) - 1,
            "section_id": len(self.created["sections"]) - 1 if self.created["sections"] else 0,
        }
        self.created["requirements"].append(req_info)

        self.y += 18
        return req_info

    def add_equation(self, latex: str, label: str = None) -> dict:
        """Add a LaTeX equation (rendered as text placeholder)."""
        if self.page is None:
            self.new_page()

        self.ensure_space(35)

        # Center the equation
        eq_num = len(self.created["equations"]) + 1
        display = f"  {latex}  "
        if label:
            display += f"({label})"
        else:
            display += f"({eq_num})"

        # Indent for equation block
        self.page.insert_text(
            fitz.Point(self.margin + 50, self.y),
            display,
            fontname=FONT_BODY,
            fontsize=11,
        )

        eq_info = {
            "id": eq_num,
            "latex": latex,
            "label": label or str(eq_num),
            "page": len(self.doc) - 1,
        }
        self.created["equations"].append(eq_info)

        self.y += 25
        return eq_info

    def add_annotation(self, annot_type: str, content: str = None) -> dict:
        """Add a PDF annotation."""
        if self.page is None:
            self.new_page()

        rect = fitz.Rect(self.margin, self.y, self.margin + 100, self.y + 20)

        if annot_type == "highlight":
            # Add some text first, then highlight it
            self.page.insert_text(fitz.Point(self.margin, self.y), "Highlighted text")
            self.page.add_highlight_annot(rect)
        elif annot_type == "note":
            self.page.add_text_annot(fitz.Point(self.margin, self.y), content or "Note")
        elif annot_type == "box":
            self.page.add_rect_annot(rect)

        annot_info = {
            "type": annot_type,
            "page": len(self.doc) - 1,
            "content": content,
        }
        self.created["annotations"].append(annot_info)

        self.y += 30
        return annot_info

    def save(self, path: Path) -> dict:
        """Save the PDF and return creation summary."""
        self.doc.save(str(path))
        self.doc.close()
        return self.created


def build_from_spec(spec: dict) -> tuple[Path, dict]:
    """Build PDF from content specification."""
    builder = PDFBuilder(style=spec.get("style", "standard"))

    for section in spec.get("sections", []):
        builder.add_section(section["title"], level=section.get("level", 1))

        for content in section.get("content", []):
            ctype = content["type"]

            if ctype == "text":
                builder.add_text(content["text"])

            elif ctype == "table":
                columns = content.get("columns", ["A", "B", "C"])
                rows = content.get("rows", [])
                if isinstance(rows, int):
                    # Generate dummy rows
                    rows = [[f"R{i}C{j}" for j in range(len(columns))] for i in range(rows)]
                builder.add_table(columns, rows)

            elif ctype == "figure":
                builder.add_figure(content.get("description", "Figure"))

            elif ctype == "requirement":
                builder.add_requirement(
                    content["id"],
                    content["text"],
                    content.get("type", "Functional"),
                )

            elif ctype == "latex" or ctype == "equation":
                builder.add_equation(
                    content.get("equation", content.get("latex", "x = y")),
                    content.get("label"),
                )

            elif ctype == "header":
                builder.add_sub_header(content["text"])

            elif ctype == "annotation":
                builder.add_annotation(
                    content.get("annot_type", "note"),
                    content.get("content"),
                )

    return builder


def generate_spec_md(fixture_name: str, pdf_path: str, created: dict) -> str:
    """Generate SPEC.md content from creation summary."""

    # Build YAML frontmatter
    yaml_lines = [
        "---",
        f"fixture: {fixture_name}",
        f"pdf: {pdf_path}",
        f"generated: {datetime.now().isoformat()}",
        "",
        "steps:",
    ]

    # S01: Annotations
    if created["annotations"]:
        yaml_lines.extend(
            [
                "  s01:",
                "    name: Annotation Processor",
                "    expected:",
                f"      annotation_count: {len(created['annotations'])}",
            ]
        )

    # S02: Blocks (estimated)
    block_estimate = len(created["sections"]) * 5 + len(created["tables"]) + len(created["figures"])
    yaml_lines.extend(
        [
            "  s02:",
            "    name: Marker Blocks",
            "    expected:",
            f"      block_count_min: {block_estimate}",
        ]
    )

    # S04: Sections
    yaml_lines.extend(
        [
            "  s04:",
            "    name: Section Builder",
            "    expected:",
            f"      section_count: {len(created['sections'])}",
        ]
    )

    # S05: Tables
    if created["tables"]:
        yaml_lines.extend(
            [
                "  s05:",
                "    name: Table Extractor",
                "    expected:",
                f"      table_count: {len(created['tables'])}",
            ]
        )

    # S06: Figures
    if created["figures"]:
        yaml_lines.extend(
            [
                "  s06:",
                "    name: Figure Extractor",
                "    expected:",
                f"      figure_count: {len(created['figures'])}",
            ]
        )

    # S08: Requirements
    if created["requirements"]:
        yaml_lines.extend(
            [
                "  s08:",
                "    name: Requirements (LLM)",
                "    expected:",
                f"      requirement_count: {len(created['requirements'])}",
            ]
        )

    # S10: Markdown Exporter
    yaml_lines.extend(
        [
            "  s10:",
            "    name: Markdown Exporter",
            "    expected:",
            f"      section_headers: {len(created['sections'])}",
        ]
    )

    if created["requirements"]:
        yaml_lines.append(f"      requirements: {len(created['requirements'])}")
    if created["equations"]:
        # We don't have a direct gate check for equations yet but good to have in spec
        yaml_lines.append(f"      equations_min: {len(created['equations'])}")

    yaml_lines.extend(
        [
            "---",
            "",
        ]
    )

    # Markdown notes
    md_lines = [
        f"# {fixture_name} Fixture Notes",
        "",
        "## Generated Content",
        "",
        f"- **Sections**: {len(created['sections'])}",
        f"- **Tables**: {len(created['tables'])}",
        f"- **Figures**: {len(created['figures'])}",
        f"- **Requirements**: {len(created['requirements'])}",
        f"- **Equations**: {len(created['equations'])}",
        f"- **Annotations**: {len(created['annotations'])}",
        "",
    ]

    if created["sections"]:
        md_lines.append("## Sections")
        md_lines.append("")
        for s in created["sections"]:
            md_lines.append(f"- {s['title']} (page {s['page']})")
        md_lines.append("")

    if created["requirements"]:
        md_lines.append("## Requirements")
        md_lines.append("")
        for r in created["requirements"]:
            md_lines.append(f"- **{r['id']}**: {r['text'][:50]}...")
        md_lines.append("")

    return "\n".join(yaml_lines + md_lines)


def create_fixture(spec: dict, fixture_name: str) -> Path:
    """Create a complete fixture from content specification."""

    fixture_dir = FIXTURES_DIR / fixture_name
    fixture_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = fixture_dir / "source.pdf"
    spec_path = fixture_dir / "SPEC.md"

    # Build PDF
    builder = build_from_spec(spec)
    created = builder.save(pdf_path)

    # Generate SPEC.md
    relative_pdf = f"fixtures/{fixture_name}/source.pdf"
    spec_content = generate_spec_md(fixture_name, relative_pdf, created)
    spec_path.write_text(spec_content)

    print(f"\n✅ Fixture created: {fixture_name}")
    print(f"   PDF: {pdf_path}")
    print(f"   SPEC: {spec_path}")
    print("\nContent:")
    print(f"   Sections: {len(created['sections'])}")
    print(f"   Tables: {len(created['tables'])}")
    print(f"   Figures: {len(created['figures'])}")
    print(f"   Requirements: {len(created['requirements'])}")
    print(f"   Equations: {len(created['equations'])}")

    return fixture_dir


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Create test PDF fixtures from specs")
    parser.add_argument("--spec", type=Path, help="JSON spec file")
    parser.add_argument("--inline", type=str, help="Inline JSON spec")
    parser.add_argument("--name", required=True, help="Fixture name")
    parser.add_argument("--example", action="store_true", help="Create example fixture")
    args = parser.parse_args()

    if args.example:
        # Create an example fixture
        spec = {
            "style": "standard",
            "sections": [
                {
                    "title": "1. Introduction",
                    "content": [
                        {
                            "type": "text",
                            "text": "This document describes the system requirements.",
                        },
                        {"type": "table", "columns": ["ID", "Name", "Status"], "rows": 3},
                    ],
                },
                {
                    "title": "2. Requirements",
                    "content": [
                        {
                            "type": "requirement",
                            "id": "REQ-001",
                            "text": "The system shall process input within 1 second.",
                        },
                        {
                            "type": "requirement",
                            "id": "REQ-002",
                            "text": "The system must support UTF-8 encoding.",
                        },
                    ],
                },
                {
                    "title": "3. Analysis",
                    "content": [
                        {"type": "text", "text": "The following equations govern system behavior:"},
                        {"type": "equation", "latex": "E = mc^2"},
                        {"type": "equation", "latex": "F = ma"},
                        {"type": "figure", "description": "System Architecture Diagram"},
                    ],
                },
            ],
        }
    elif args.spec:
        spec = json.loads(args.spec.read_text())
    elif args.inline:
        spec = json.loads(args.inline)
    else:
        print("ERROR: Provide --spec, --inline, or --example")
        return 1

    create_fixture(spec, args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
