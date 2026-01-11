
import camelot
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.ERROR)

def main():
    pdf_path = Path("data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf")
    if not pdf_path.exists():
        found = list(Path("data").rglob("*.pdf"))
        # Prioritize the one with correct name
        for f in found:
            if "BHT" in f.name and "clean" not in f.name:
                pdf_path = f
                break
        else:
             if found: pdf_path = found[0]

    print(f"Analyzing PDF: {pdf_path}")
    
    for scale in [15, 40]:
        print(f"\n>>> Running Lattice with line_scale={scale}...")
        try:
            tables = camelot.read_pdf(
                str(pdf_path), 
                pages="1-end", 
                flavor="lattice", 
                line_scale=scale
            )
            
            # Find Page 2 table
            p2_tables = [t for t in tables if t.page == 2]
            if not p2_tables:
                print("  No tables found on Page 2.")
                continue
                
            t = p2_tables[0]
            rows, cols = t.df.shape
            print(f"  Result (Page 2): Found Table with {rows} Rows and {cols} Columns.")
            
            # Print column boundaries/text to understand the merge
            # First row text
            row0 = [str(x).replace('\n', ' ') for x in t.df.iloc[0].values]
            print(f"  Row 0 Content: {row0}")
            
            if cols < 5:
                print("  [ANALYSIS]: Columns were merged. Likely missed vertical separators.")
            elif cols == 5:
                print("  [ANALYSIS]: Correctly identified 5 columns.")
                
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    main()
