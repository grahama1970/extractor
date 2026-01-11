
import duckdb
from pathlib import Path

def main():
    db_path = Path("data/results/pipeline/pipeline.duckdb")
    con = duckdb.connect(str(db_path))
    
    print(">>> TABLES in DB:")
    tables = con.execute("SELECT id, page, section_id FROM tables ORDER BY page").fetchall()
    print("Columns in tables:", [c[0] for c in con.execute("DESCRIBE tables").fetchall()])
    for t in tables:
        print(t)
        
    print("\n>>> SECTIONS in DB:")
    sections = con.execute("SELECT id, page_start, page_end, x0, y0, x1, y1 FROM sections ORDER BY page_start").fetchall()
    for s in sections:
        print(s)

    con.close()

if __name__ == "__main__":
    main()
