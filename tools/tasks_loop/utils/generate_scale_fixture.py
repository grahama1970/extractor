#!/usr/bin/env python3
"""
generate_scale_fixture.py

Generates a large-scale synthetic PDF for stress/performance testing.
Also generates "Ground Truth" artifacts (MD/JSON).
Injects "Tricky Elements" from YAML config to test heuristic resilience at scale.

Usage:
    python3 generate_scale_fixture.py output.pdf --pages 50 --config tricky_pdf_elements.yml
"""

import fitz  # PyMuPDF
import random
import json
import yaml
from pathlib import Path

LOREM = (
    """
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. 
Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. 
Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. 
Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
"""
    * 5
)


# Helpers for Chaos
def apply_ligatures(text: str, lig_map: dict) -> str:
    for k, v in lig_map.items():
        text = text.replace(k, v)
    return text


def apply_mojibake(text: str, prob: float) -> str:
    if prob <= 0:
        return text
    chars = list(text)
    for i in range(len(chars)):
        if random.random() < prob and chars[i].isalnum():
            chars[i] = random.choice(["?", "□", "%", "#", ""])
    return "".join(chars)


def insert_chaotic_textbox(page, rect, text, config, fontsize=10, fontname="Helvetica"):
    # Config
    chaos = config.get("chaos", {})
    lig_map = chaos.get("ligature_map", {})
    moji_prob = chaos.get("mojibake_probability", 0.0)
    hyphen_prob = chaos.get("hyphenation_probability", 0.0)

    # 1. Ligatures & Mojibake (Content Level)
    # Applied to the generated text, so PDF contains these chars.
    # Note: Extractor should map ligatures back, but Mojibake is permanent.
    text = apply_ligatures(text, lig_map)
    text = apply_mojibake(text, moji_prob)

    # 2. Layout (Hyphenation)
    # We do manual wrapping to force hyphens
    words = text.split()
    lines = []
    current_line = []
    current_len = 0
    max_len = int(rect.width / (fontsize * 0.5))  # Approximate char width

    for w in words:
        if current_len + len(w) + 1 > max_len:
            # Line full. Check Hyphenation Chaos.
            if random.random() < hyphen_prob and len(w) > 4:
                # Split word
                split_idx = len(w) // 2
                p1 = w[:split_idx] + "-"
                p2 = w[split_idx:]
                current_line.append(p1)
                lines.append(" ".join(current_line))
                current_line = [p2]
                current_len = len(p2)
            else:
                # Normal wrap
                lines.append(" ".join(current_line))
                current_line = [w]
                current_len = len(w)
        else:
            current_line.append(w)
            current_len += len(w) + 1

    if current_line:
        lines.append(" ".join(current_line))

    # Draw Lines
    y = rect.y0 + 10
    line_height = fontsize * 1.2
    for line in lines:
        if y > rect.y1:
            break
        page.insert_text((rect.x0, y), line, fontsize=fontsize, fontname=fontname)
        y += line_height  # Line height


def create_scale_fixture(
    output_path: Path, page_count: int = 50, config_path: Path = None, seed: int = None
):
    # Set Seed
    if seed is not None:
        random.seed(seed)
        print(f"Random Seed: {seed}")

    # Load Config
    config = {}
    if config_path and config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text())
            print(f"Loaded config from {config_path}")
        except Exception as e:
            print(f"Error loading config: {e}")

    doc = fitz.open()

    # Ground Truth Containers
    expected_data = []  # List of dicts (Contracts)
    expected_md_lines = []  # For Markdown comparison

    # Chaos & Style Config
    chaos = config.get("chaos", {})
    style = config.get("style", {})
    print(f"Chaos Config: {chaos}")
    print(f"Style Config: {style}")

    # Style Defaults
    f_body = style.get("body_font_size", 10)
    f_header = style.get("header_font_size", 16)
    f_name = style.get(
        "font_name", "Helvetica"
    )  # PyMuPDF supports limited std fonts unless registered

    for i in range(page_count):
        page = doc.new_page(
            width=style.get("page_width", 595), height=style.get("page_height", 842)
        )
        _width, _height = page.rect.width, page.rect.height

        # Header
        header = f"Page {i+1}: Scale Test Section {i+1}"
        page.insert_text((50, 50), header, fontsize=f_header, fontname=f_name + "-Bold")
        expected_md_lines.append(f"# {header}")

        y = 80

        # Choose Content Mode
        # 0: Text Heavy (Chaos Target)
        # 1: Table Heavy
        # 2: Mixed / Structure
        mode = i % 3

        if mode == 0:  # Text Heavy
            for b in range(3):
                sub_header = f"1.{i}.{b} Text Block"
                page.insert_text(
                    (50, y), sub_header, fontsize=f_body + 2, fontname=f_name + "-Bold"
                )
                y += 20

                expected_md_lines.append(f"## {sub_header}")

                # Use Chaotic Inserter (Needs to support font/size)
                # We need to update insert_chaotic_textbox signature or just pass config
                # Actually insert_chaotic_textbox hardcodes fontsize=10. Fix that too.
                insert_chaotic_textbox(
                    page,
                    fitz.Rect(50, y, 550, y + 100),
                    LOREM,
                    config,
                    fontsize=f_body,
                    fontname=f_name,
                )

                # For Ground Truth:
                # Ideally, we expect the CLEAN text (without hyphens/chaos) if our pipeline is perfect.
                # However, the contract verifier compares extraction to THIS expected string.
                # If we inject chaos, does "Expected" contain chaos?
                # Usually:
                # - Hyphens: Extractor should REMOVE them. So Expected = Clean.
                # - Ligatures: Extractor should NORMALIZE them. So Expected = Clean (or Normalized).
                # - Mojibake: Extractor CANNOT fix. So Expected = Mojibake? Or we accept mismatch?
                # For now, we leave Expected as CLEAN LOREM.
                # This tests if pipeline cleans Hyphens.
                # Mismatch in Mojibake/Ligatures will lower fuzzy score, but pass if threshold is lenient.

                expected_md_lines.append(LOREM.strip() + "\n")

                y += 120
                if y > 700:
                    break

        elif mode == 1:  # Table Heavy
            title = f"Table {i}: Dense Data"
            page.insert_text((50, y), title, fontsize=11, fontname="Helvetica-Oblique")
            y += 20

            expected_md_lines.append(f"### {title}")
            expected_md_lines.append("| ID | Metric A | Metric B | Status |")
            expected_md_lines.append("|---|---|---|---|")

            # Header
            page.draw_rect(fitz.Rect(50, y, 550, y + 20), color=(0, 0, 0), fill=(0.9, 0.9, 0.9))
            page.insert_text((60, y + 14), "ID", fontsize=10)
            page.insert_text((150, y + 14), "Metric A", fontsize=10)
            page.insert_text((300, y + 14), "Metric B", fontsize=10)
            page.insert_text((450, y + 14), "Status", fontsize=10)
            y += 20

            table_rows = []

            # 25 rows
            for r in range(25):
                c1 = f"R{r}"
                c2 = f"{random.random():.4f}"
                c3 = f"{random.randint(100,9999)}"
                c4 = random.choice(["PASS", "FAIL", "WARN"])

                # Injection: Sometimes put "Section-like" text in data
                if r == 12 and i % 5 == 0:
                    c3 = config.get("tables", {}).get("false_header_text", "SECTION TRAP")

                page.insert_text((60, y + 14), c1, fontsize=10)
                page.insert_text((150, y + 14), c2, fontsize=10)
                page.insert_text((300, y + 14), c3, fontsize=10)
                page.insert_text((450, y + 14), c4, fontsize=10)
                page.draw_line((50, y + 20), (550, y + 20))
                y += 20

                row_obj = {"ID": c1, "Metric A": c2, "Metric B": c3, "Status": c4}
                table_rows.append(row_obj)
                expected_md_lines.append(f"| {c1} | {c2} | {c3} | {c4} |")

            # Add Table to Expected Data
            is_strict_table = config.get("tables", {}).get("strict_verification", False)
            expected_data.append(
                {
                    "id": f"TBL-{i}",
                    "type": "Table",
                    "title": title,
                    "content": table_rows,
                    "strict_verification": is_strict_table,
                }
            )

        else:  # Mixed / Structure
            sub_header = f"2.{i} Complex Layout"
            page.insert_text((50, y), sub_header, fontsize=12, fontname="Helvetica-Bold")
            y += 30

            expected_md_lines.append(f"## {sub_header}")

            page.insert_textbox(fitz.Rect(50, y, 300, y + 100), LOREM[:200], fontsize=10)
            expected_md_lines.append(LOREM[:200].strip() + "\n")

            # Side content attempt
            page.draw_rect(fitz.Rect(320, y, 550, y + 100), color=(0, 0, 1))
            page.insert_text((330, y + 20), "Figure/Sidebar", color=(0, 0, 1))
            y += 120

            # Periodically inject False Positive Requirement
            if i % 4 == 0:
                fps = config.get("false_positives", [])
                if fps:
                    fp = random.choice(fps)
                    page.insert_text((50, y), fp["text"], fontsize=11, color=(0.3, 0.3, 0.3))
                    expected_md_lines.append(fp["text"])
                    y += 30

            # Periodically inject Critical Content (Golden Data)
            if i % 10 == 0:
                crit = config.get("critical_content", [])
                if crit:
                    # Pick one deterministicly based on page to avoid randomness if possible, or just cycle
                    item = crit[(i // 10) % len(crit)]
                    rid = item.get("id")
                    rtext = item.get("text")
                    full_text = f"{rid}: {rtext}"

                    page.insert_text((50, y), full_text, fontsize=11, color=(0, 0, 0))
                    y += 30

                    expected_md_lines.append(f"- **{rid}**: {rtext}")
                    expected_data.append(
                        {
                            "id": rid,
                            "type": item.get("type", "Requirement"),
                            "text": full_text,
                            "strict_verification": item.get("strict_verification", True),
                        }
                    )

            # Small inline table
            table_title = f"Table {i}b: Summary"
            page.insert_text((50, y), table_title, fontsize=10)
            expected_md_lines.append(f"### {table_title}")
            y += 15
            page.draw_rect(fitz.Rect(50, y, 300, y + 15), color=(0, 0, 0))
            expected_md_lines.append("| Item |")
            expected_md_lines.append("|---|")
            y += 15

            small_rows = []
            for r in range(3):
                c1 = f"Item {r}"
                page.insert_text((60, y + 10), c1, fontsize=10)
                y += 15
                small_rows.append({"Item": c1})
                expected_md_lines.append(f"| {c1} |")

            expected_data.append(
                {"id": f"TBL-{i}b", "type": "Table", "title": table_title, "content": small_rows}
            )

    # Save PDF
    doc.save(output_path)
    print(f"Generated PDF: {output_path} ({page_count} pages)")

    # Save Markdown
    md_path = output_path.with_name(output_path.stem + "_expected.md")
    md_path.write_text("\n".join(expected_md_lines))
    print(f"Generated MD:  {md_path}")

    # Save JSON with Metrics
    output_obj = {
        "metrics": {
            "requirement_count": len([i for i in expected_data if i["type"] == "Requirement"]),
            "table_count": len([i for i in expected_data if i["type"] == "Table"]),
            "total_items": len(expected_data),
            "total_pages": page_count,
        },
        "content": expected_data,
    }
    json_path = output_path.with_name(output_path.stem + "_expected.json")
    json_path.write_text(json.dumps(output_obj, indent=2))
    print(f"Generated JSON: {json_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, help="Output PDF path")
    parser.add_argument("--pages", type=int, default=50, help="Number of pages")
    parser.add_argument("--config", type=Path, help="Optional tricky_elements.yml config")
    parser.add_argument("--seed", type=int, help="Random seed")
    args = parser.parse_args()

    create_scale_fixture(args.output, args.pages, args.config, args.seed)
