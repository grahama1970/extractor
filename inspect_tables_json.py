
import json
from pathlib import Path

# Path to S05 output
JSON_PATH = Path("data/results/pipeline/05_table_extractor/json_output/05_tables.json")

def inspect_json():
    print(f"Loading {JSON_PATH}")
    if not JSON_PATH.exists():
        print("File not found.")
        return
        
    data = json.load(open(JSON_PATH))
    tables = data.get("tables", [])
    print(f"Found {len(tables)} tables in JSON.")
    
    for i, t in enumerate(tables):
        print(f"\n--- Table {i} (Index: {t.get('table_index')}) ---")
        print(f"Page: {t.get('page_number')}")
        print(f"Strategy: {t.get('strategy')}")
        print(f"Rows: {t.get('pandas_metrics', {}).get('shape', [0,0])[0]}")
        print(f"Cols: {t.get('pandas_metrics', {}).get('shape', [0,0])[1]}")
        
        # Print content
        df = t.get("pandas_df", [])
        if not df:
            print("(Empty DF)")
            continue
            
        # Print first few rows
        print("Content Preview:")
        for r in df[:3]: # first 3 rows
            print(r)
            
        # Check for BHT text
        txt = str(df)
        if "BHT is implemented" in txt:
            print(">>> FOUND TARGET TEXT <<<")

if __name__ == "__main__":
    inspect_json()
