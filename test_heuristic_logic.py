
import camelot
import pandas as pd
from pathlib import Path

# Path to the clean PDF used by the pipeline
PDF_PATH = Path("data/results/pipeline/01_annotation_processor/BHT_CV32A65X_with_requirements_noannots_clean_clean.pdf")
if not PDF_PATH.exists():
    # Fallback to source
    PDF_PATH = Path("data/source.pdf") 

def analyze_heuristic():
    print(f"Analyzing PDF: {PDF_PATH}")
    # Extract only page 1 where the BHT table is
    tables = camelot.read_pdf(str(PDF_PATH), pages="all", flavor="lattice")
    print(f"Found {len(tables)} tables on ALL pages using LATTICE.")
    
    for i, t in enumerate(tables):
        df = t.df
        content = df.to_string()
        if True: # Print all tables
            pass
            
        print(f"\n--- Table {i} Analysis (Potential BHT Intro) ---")
        print(df)
        
        # Calculate Heuristic Metrics
        rows, cols = df.shape
        print(f"Shape: {rows} rows, {cols} cols")
        
        # Flatten text
        all_text = []
        total_words = 0
        total_digits = 0
        total_chars = 0
        row_count = 0
        
        # Simulate the logic in heuristics.py
        # src = t.get("pandas_df_raw") ... checks raw logic
        # Here we just iterate the DF
        for idx, row in df.iterrows():
            # Join all cols
            vals = [str(v).strip() for v in row.values]
            line = " ".join(vals)
            if line.strip():
                all_text.append(line)
                words = line.split()
                total_words += len(words)
                total_digits += sum(c.isdigit() for c in line)
                total_chars += len(line)
                row_count += 1
                
        avg_words = total_words / max(1, row_count)
        digit_ratio = total_digits / max(1, total_chars)
        
        print(f"METRICS:")
        print(f"  Avg Words/Row: {avg_words:.2f} (Threshold > 2.5)")
        print(f"  Digit Ratio:   {digit_ratio:.2f} (Threshold < 0.2)")
        print(f"  Cols:          {cols} (Threshold == 1)")
        
        if cols == 1:
            if avg_words > 2.5 and digit_ratio < 0.2:
                print("  Result: WOULD DEMOTE ✅")
            else:
                print("  Result: WOULD KEEP ❌ (Metrics mismatch)")
        else:
            print("  Result: WOULD KEEP ❌ (Cols != 1)")

if __name__ == "__main__":
    analyze_heuristic()
