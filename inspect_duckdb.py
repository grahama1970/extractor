
import duckdb
from pathlib import Path

def main():
    db_path = Path("data/results/pipeline/pipeline.duckdb")
    con = duckdb.connect(str(db_path))
    
    print("Checking Suppression Candidates:")
    
    # Check Table BBox
    # Note: 'title' column might be 'llm_title' or similar. 
    # Schema says 'llm_title'.
    t_res = con.execute("SELECT id, page, x0, y0, x1, y1 FROM tables WHERE llm_title LIKE '%Signal%' OR id LIKE '%Signal%'").fetchall()
    print("Tables matching 'Signal':")
    for r in t_res:
        print(f"  {r}")
    
    # Check Block BBox
    b_res = con.execute("SELECT id, page, x0, y0, x1, y1, text FROM blocks WHERE text LIKE 'clk_i in Subsyste%'").fetchall()
    print("\nBlocks matching 'clk_i in Subsyste':")
    for r in b_res:
        print(f"  {r}")
        
    con.close()

if __name__ == "__main__":
    main()
