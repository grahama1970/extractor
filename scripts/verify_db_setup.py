import sys
from pathlib import Path
import os
import duckdb

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from extractor.pipeline.utils.db.connection import get_connection
from extractor.pipeline.utils.db.schema import create_schema

def main():
    db_path = Path("data/results/pipeline_test/pipeline.duckdb")
    
    # Clean slate
    if db_path.exists():
        print(f"Removing existing DB at {db_path}")
        os.remove(db_path)
    
    try:
        con = get_connection(db_path)
        create_schema(con)
        
        print("Schema created successfully.")
        
        # Verify Tables
        tables = con.sql("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        required_tables = {"blocks", "figures", "sections", "tables", "requirements"}
        
        print(f"Found tables: {table_names}")
        
        missing = required_tables - set(table_names)
        if missing:
            print(f"ERROR: Missing tables: {missing}")
            sys.exit(1)
            
        # Verify View
        views = con.sql("SELECT table_name FROM information_schema.tables WHERE table_type='VIEW'").fetchall()
        view_names = [v[0] for v in views]
        if "v_clean_blocks" not in view_names:
            print("ERROR: Missing view v_clean_blocks")
            sys.exit(1)
            
        print("Verification PASSED.")
        
    except Exception as e:
        print(f"Verification FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
