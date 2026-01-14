
import camelot
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("camelot_sanity")

def main():
    pdf_path = Path("data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf")
    
    if not pdf_path.exists():
        # Fallback search
        found = list(Path("data").rglob("*.pdf"))
        if found:
            pdf_path = found[0]
            print(f"Using found PDF: {pdf_path}")
        else:
            print("PDF not found!")
            return

    print(f"Analyzing PDF: {pdf_path}")
    
    # We only care about Lattice for the Grid Table on Page 2
    # User suggests line_scale=15 might be relevant (or 40 is default).
    # We will sweep.
    
    scales = [15, 30, 40, 45, 60, 90]
    
    print(f"Sweeping line_scale on Page 2 to find 5 columns...")
    
    for scale in scales:
        print(f"\n--- Testing Lattice | LineScale: {scale} ---")
        try:
            tables = camelot.read_pdf(
                str(pdf_path), 
                pages="2", 
                flavor="lattice", 
                line_scale=scale
            )
            print(f"Found {len(tables)} tables.")
            
            for i, t in enumerate(tables):
                df = t.df
                rows, cols = df.shape
                # First row sample
                first_row = " | ".join([str(v).strip() for v in df.iloc[0].values])
                print(f"  Table {i}: Shape=({rows}, {cols})")
                print(f"    First Row: {first_row[:80]}")
                
                if cols == 5:
                    print("    [SUCCESS] Found 5 Columns! This is the target configuration.")
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
