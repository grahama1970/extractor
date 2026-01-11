
import camelot
import logging
import sys
from pathlib import Path
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("camelot_sanity_v2")

def check_pdf_path():
    # Try expected path first
    candidates = [
        Path("data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf"),
        Path("data/input/pipeline/BHT_CV32A65X_with_requirements_noannots_clean_clean.pdf"),
    ]
    # Also search entire data dir
    candidates.extend(list(Path("data").rglob("*.pdf")))
    
    for p in candidates:
        if p.exists() and "BHT" in p.name:
            return p
    return None

def analyze_tables(pdf_path, flavor="lattice", line_scale=15):
    print(f"\n{'='*60}")
    print(f"Running Camelot Analysis v2")
    print(f"PDF: {pdf_path}")
    print(f"Flavor: {flavor}")
    print(f"Line Scale: {line_scale}")
    print(f"{'='*60}\n")

    try:
        # Extract from all pages
        tables = camelot.read_pdf(
            str(pdf_path),
            pages="1-end",
            flavor=flavor,
            line_scale=line_scale
        )
        
        print(f"Total Tables Found: {len(tables)}\n")
        
        for i, t in enumerate(tables):
            df = t.df
            rows, cols = df.shape
            page = t.page
            bbox = t._bbox
            accuracy = t.parsing_report.get('accuracy', 0)
            whitespace = t.parsing_report.get('whitespace', 0)
            
            print(f"Table {i} (Page {page})")
            print(f"  Shape: {rows} rows x {cols} cols")
            print(f"  BBox: {bbox}")
            print(f"  Accuracy: {accuracy:.2f}% | Whitespace: {whitespace:.2f}%")
            
            # Print content preview (First 3 rows)
            print("  Content Preview:")
            print("-" * 40)
            print(df.head(3).to_string())
            print("-" * 40)
            print("\n")
            
    except Exception as e:
        print(f"Extraction Failed: {e}")

def main():
    pdf_path = check_pdf_path()
    if not pdf_path:
        print("Error: Could not find BHT PDF file.")
        sys.exit(1)
        
    # Analyze with line_scale=15 (User specified)
    analyze_tables(pdf_path, flavor="lattice", line_scale=15)

if __name__ == "__main__":
    main()
