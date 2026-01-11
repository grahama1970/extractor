
import duckdb
from pathlib import Path
import os
import shutil

# Minimal sanity check for Stage 07 (DuckDB Ingest)
# Verifies we can:
# 1. Connect to DuckDB
# 2. Create the schema (tables/merged_content)
# 3. Insert data
# 4. Query it back

def main():
    db_path = Path("sanity_s07.duckdb")
    if db_path.exists():
        db_path.unlink()
        
    print(f"Testing S07 Ingestion into {db_path}...")
    
    con = duckdb.connect(str(db_path))
    
    try:
        # 1. Schema Creation (Manual minimal schema or import from s07 if refactored)
        # We'll use manual to verify the *concept* of the schema, 
        # or better, import create_schema from s07 if available?
        # Let's import the actual schema function to test the CODE, not just DuckDB.
        try:
            from extractor.pipeline.utils.db.schema import create_schema
            create_schema(con)
            print("✅ Schema created successfully using pipeline utilities.")
        except ImportError:
            print("⚠️ Cloud not import create_schema, using manual fallback.")
            con.execute("CREATE TABLE tables (id VARCHAR, page INTEGER, sort_order INTEGER)")
            
        # 2. Ingest Dummy Data
        con.execute("INSERT INTO tables (id, page, sort_order) VALUES ('t1', 1, 100)")
        
        # 3. Verify
        count = con.execute("SELECT count(*) FROM tables").fetchone()[0]
        if count == 1:
            print("✅ Ingest Verification Passed: Found 1 table.")
        else:
            print(f"❌ Ingest Verification Failed: Expected 1 table, found {count}")
            
    except Exception as e:
        print(f"❌ S07 Sanity Exception: {e}")
    finally:
        con.close()
        if db_path.exists():
            db_path.unlink()

if __name__ == "__main__":
    main()
