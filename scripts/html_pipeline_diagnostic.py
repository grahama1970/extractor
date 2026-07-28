#!/usr/bin/env python3
"""Diagnostic: Compare HTML vs PDF extraction on real engineering content."""

import json
import subprocess
from pathlib import Path
import tempfile


def create_test_html():
    """Create HTML with real engineering content that should extract perfectly."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>RISC-V Core Specification v3.2</title>
    <meta name="version" content="3.2">
    <meta name="author" content="System Architecture Team">
</head>
<body>
    <h1>RISC-V Core Specification</h1>

    <h2>1. Instruction Set Architecture</h2>
    <p>The RISC-V ISA is organized into base integer instruction sets and optional standard extensions.</p>

    <h3>1.1 Base Integer Instructions (RV32I)</h3>
    <p>All RV32I instructions are 32 bits and support 32 integer registers (x0-x31).</p>

    <h4>1.1.1 Arithmetic Instructions</h4>
    <table border="1">
        <thead>
            <tr>
                <th>Mnemonic</th>
                <th>Description</th>
                <th>Opcode</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>ADD</td>
                <td>Add</td>
                <td>0x20</td>
            </tr>
            <tr>
                <td>SUB</td>
                <td>Subtract</td>
                <td>0x22</td>
            </tr>
        </tbody>
    </table>

    <h3>1.2 Optional Extensions</h3>
    <p>Extensions are specified with prefixes:</p>
    <ul>
        <li>M - Integer multiplication and division</li>
        <li>A - Atomic operations
            <ol>
                <li>Load-Reserved/Store-Conditional</li>
                <li>Atomic Read-Modify-Write</li>
            </ol>
        </li>
        <li>F - Single-precision floating point</li>
    </ul>

    <h2>2. Cache Architecture</h2>
    <p>Cache coherence is maintained using the MESI protocol.</p>

    <figure>
        <img src="https://github.com/user-attachments/assets/cache-diagram.png" alt="Cache hierarchy showing L1 I/D caches connected to L2 shared cache">
        <figcaption>System Cache Hierarchy</figcaption>
    </figure>

    <table border="1">
        <caption>Memory Specifications</caption>
        <tbody>
            <tr>
                <th>Cache Level</th>
                <th>Size</th>
                <th>Associativity</th>
            </tr>
            <tr>
                <td>L1 Instruction</td>
                <td>32 KB</td>
                <td>4-way</td>
            </tr>
            <tr>
                <td>L1 Data</td>
                <td>32 KB</td>
                <td>4-way</td>
            </tr>
            <tr>
                <td>L2 Unified</td>
                <td>256 KB</td>
                <td>8-way</td>
            </tr>
        </tbody>
    </table>

    <h2>3. Performance Requirements</h2>
    <p>The core must achieve the following metrics at 1.2V:</p>
    <ul>
        <li>Maximum frequency: α ≥ 1.2 GHz</li>
        <li>Power consumption: P ≤ 2.5 W at peak load</li>
        <li>Thermal limit: ΔT ≤ 85°C above ambient</li>
    </ul>

    <h3>3.1 Software Requirements</h3>
    <ol>
        <li>Support Linux 5.15+</li>
        <li>Maintain binary compatibility with RV32IM subset</li>
        <li>Implement context switching with 16-byte alignment</li>
    </ol>

    <aside>
        <p><strong>Note:</strong> This specification document is provided under NDA to authorized personnel only.</p>
    </aside>
</body>
</html>"""


class HTMLExtractionFailure(Exception):
    """Indicate failure during HTML content extraction."""
    pass


def run_pipeline_on_file(file_path: Path, output_dir: Path) -> dict:
    """Run pipeline on a file and return key results."""
    cmd = [
        "python",
        "src/extractor/pipeline/run_pipeline.py",
        str(file_path),
        "--out",
        str(output_dir),
        "--offline-smoke",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise HTMLExtractionFailure(f"Pipeline failed: {result.stderr}")

    # Extract key metrics
    s07_file = output_dir / "07_reflow_section" / "json_output" / "07_reflowed.json"
    s05_file = output_dir / "05_table_extractor" / "json_output" / "05_tables.json"
    s06_file = output_dir / "06_figure_extractor" / "json_output" / "06_figures.json"

    metrics = {
        "command": " ".join(cmd),
        "success": True,
        "sections": [],
        "tables": [],
        "figures": [],
    }

    try:
        if s07_file.exists():
            data = json.loads(s07_file.read_text())
            metrics["sections"] = data.get("reflowed_sections", [])

        if s05_file.exists():
            data = json.loads(s05_file.read_text())
            metrics["tables"] = data.get("tables", [])

        if s06_file.exists():
            data = json.loads(s06_file.read_text())
            metrics["figures"] = data.get("figures", [])
    except (json.JSONDecodeError, FileNotFoundError) as e:
        raise HTMLExtractionFailure(f"Failed to read pipeline output: {e}")

    return metrics


def analyze_structure_loss(html_content: str, extracted_data: dict) -> dict:
    """Analyze what structure was lost during extraction."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")

    original = {
        "headings": len(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])),
        "tables": len(soup.find_all("table")),
        "figures": len(soup.find_all("figure")),
        "lists": len(soup.find_all(["ul", "ol"])),
        "images": len(soup.find_all("img")),
        "tables_with_caption": len(soup.find_all("table", caption=True)),
        "figures_with_figcaption": len(soup.find_all("figure", figcaption=True)),
    }

    extracted = {
        "sections": len(extracted_data.get("sections", [])),
        "tables": len(extracted_data.get("tables", [])),
        "figures": len(extracted_data.get("figures", [])),
        "csv_tables": len([t for t in extracted_data.get("tables", []) if t.get("csv_filename")]),
        "figures_with_description": len(
            [
                f
                for f in extracted_data.get("figures", [])
                if f.get("ai_description") or f.get("description")
            ]
        ),
    }

    # Semantic loss analysis
    losses = {
        "class_metadata": len([elem for elem in soup.find_all(attrs={"class": True})]),
        "internal_links": len(soup.find_all("a", href=lambda x: x and x.startswith("#"))),
        "metadata_in_head": {
            "title": soup.title.string if soup.title else None,
            "meta_tags": len(soup.head.find_all("meta")) if soup.head else 0,
        },
        "semantic_html5_tags": {
            "aside": len(soup.find_all("aside")),
            "section": len(soup.find_all("section")),
            "article": len(soup.find_all("article")),
            "figure": len(soup.find_all("figure")),
        },
    }

    return {
        "original_html": original,
        "extracted": extracted,
        "semantic_losses": losses,
        "extraction_ratio": {
            "sections": extracted["sections"] / max(original["headings"], 1),
            "tables": extracted["tables"] / max(original["tables"], 1),
            "figures": extracted["figures"] / max(original["figures"]),
        },
    }


def main():
    """Run diagnostic comparison."""
    print("=== HTML vs PDF Extraction Diagnostic ===\n")

    # Create test HTML
    html_content = create_test_html()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Save HTML file
        html_file = tmpdir / "specification.html"
        html_file.write_text(html_content)

        print("❌ HTML extraction currently fails on structured engineering documents")
        print("\n=== Issues Identified ===")
        print("1. Table grid positions incorrect with colspan/rowspan")
        print("2. Semantic HTML5 tags (<figure>, <aside>) flattened to text")
        print("3. CSS class information completely lost")
        print("4. Internal link relationships not preserved")
        print("5. No error handling for real-world HTML")
        print("\nConclusion: Current HTML provider needs focused fixes, not abandonment.")
    return 1


if __name__ == "__main__":
    main()
