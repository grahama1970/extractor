#!/usr/bin/env python3
import fitz  # PyMuPDF
import argparse
from pathlib import Path
from collections import Counter
import json


def analyze_pdf(pdf_path: Path, max_pages: int = 10, json_output: bool = False):
    doc = fitz.open(pdf_path)
    if not json_output:
        print(f"Analyzing {pdf_path.name} ({len(doc)} pages)...")

    fonts = Counter()
    sizes = Counter()

    # Layout Stats
    page_widths = Counter()
    page_heights = Counter()

    # Text Volume
    chars_per_page = []

    limit = min(len(doc), max_pages)

    for i in range(limit):
        page = doc[i]

        # Dimensions
        w = round(page.rect.width, 1)
        h = round(page.rect.height, 1)
        page_widths[w] += 1
        page_heights[h] += 1

        # Text Analysis
        blocks = page.get_text("dict")["blocks"]
        char_count = 0

        for b in blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        # Font
                        fonts[span["font"]] += len(span["text"])
                        # Size
                        s = round(span["size"], 1)
                        sizes[s] += len(span["text"])
                        # Color

                        char_count += len(span["text"])

        chars_per_page.append(char_count)

    # Analysis Logic
    common_w = page_widths.most_common(1)[0][0] if page_widths else 595.0
    common_h = page_heights.most_common(1)[0][0] if page_heights else 842.0

    sorted_sizes = sizes.most_common()
    body_size = sorted_sizes[0][0] if sorted_sizes else 10.0
    max_size = max(sizes.keys()) if sizes else 10.0

    avg_chars = sum(chars_per_page) / len(chars_per_page) if chars_per_page else 0

    result = {
        "file": str(pdf_path.name),
        "style": {
            "page_width": common_w,
            "page_height": common_h,
            "body_font_size": body_size,
            "header_font_size": max_size,
        },
        "stats": {
            "avg_chars_per_page": int(avg_chars),
            "fonts": list(fonts.keys()),
            "top_fonts": dict(fonts.most_common(5)),
        },
    }

    if json_output:
        print(json.dumps(result, indent=2))
        return

    # Text Report
    print("\n--- PDF Style Analysis ---")
    print(f"Page Size: {common_w} x {common_h}")

    print("\nTop Fonts (Weighted by Char Count):")
    for f, count in fonts.most_common(5):
        print(f"  - {f}: {count}")

    print("\nText Sizes (Heuristic):")
    print(f"  - Body: {body_size} pt")
    print(f"  - Max (Title?): {max_size} pt")

    print(f"\nAvg Chars/Page: {int(avg_chars)}")

    print("\n--- Twin Profile Suggestion ---")
    print("style:")
    print(f"  page_width: {common_w}")
    print(f"  page_height: {common_h}")
    print(f"  body_font_size: {body_size}")
    print(f"  header_font_size: {max_size}")
    print(f"  # Original Fonts: {list(fonts.keys())[:3]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--pages", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    analyze_pdf(args.pdf_path, args.pages, args.json)
