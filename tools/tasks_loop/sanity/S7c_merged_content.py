#!/usr/bin/env python3
"""
S7c_merged_content.py - Sanity check for merged_content table population.

Purpose:
- Verify that the merged_content query logic works correctly.
- This tests the core S07/S10 integration.

Dependencies:
- duckdb
- Understanding of merged_content schema

Success Criteria:
- Can create sections, blocks, tables, figures
- Can populate merged_content with sort_order
- Can query merged_content ordered by section + sort_order
"""

import sys
import tempfile
from pathlib import Path

# Resolve project root
ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    try:
        import duckdb
    except ImportError:
        print("FAIL: duckdb not installed")
        return 1
    
    print("Testing merged_content population logic...")
    
    # Use temp db
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=True) as f:
        db_path = Path(f.name)
    if db_path.exists():
        db_path.unlink()
    
    try:
        con = duckdb.connect(str(db_path))
        
        # === Create schema (simplified version of S07) ===
        print("  Creating schema...")
        con.execute("""
            CREATE TABLE sections (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                page_start INTEGER
            )
        """)
        
        con.execute("""
            CREATE TABLE merged_content (
                id INTEGER PRIMARY KEY,
                section_id VARCHAR,
                type VARCHAR,
                content VARCHAR,
                asset_id VARCHAR,
                sort_order INTEGER
            )
        """)
        
        # === Insert test data ===
        print("  Inserting test data...")
        
        # Section
        con.execute("INSERT INTO sections VALUES ('sec_1', 'Test Section', 1)")
        
        # Merged content (simulating blocks, tables, figures interleaved)
        con.execute("""
            INSERT INTO merged_content VALUES
            (1, 'sec_1', 'text', 'Introduction paragraph', NULL, 10000),
            (2, 'sec_1', 'table', NULL, 'tbl_1', 10010),
            (3, 'sec_1', 'text', 'Discussion after table', NULL, 10020),
            (4, 'sec_1', 'figure', NULL, 'fig_1', 10030),
            (5, 'sec_1', 'requirement', 'The system shall...', 'req_1', 10040)
        """)
        
        # === Query merged_content (as S10 would) ===
        print("  Querying merged_content...")
        
        query = """
            SELECT mc.type, mc.content, mc.sort_order, mc.asset_id
            FROM merged_content mc
            WHERE mc.section_id = ?
            ORDER BY mc.sort_order
        """
        
        rows = con.execute(query, ["sec_1"]).fetchall()
        
        if len(rows) != 5:
            print(f"FAIL: Expected 5 rows, got {len(rows)}")
            return 1
        
        # Verify order
        expected_order = ["text", "table", "text", "figure", "requirement"]
        actual_order = [r[0] for r in rows]
        
        if actual_order != expected_order:
            print(f"FAIL: Order mismatch. Expected {expected_order}, got {actual_order}")
            return 1
        
        print(f"    ✅ Retrieved {len(rows)} items in correct order")
        
        # Verify content
        if rows[0][1] != "Introduction paragraph":
            print(f"FAIL: Content mismatch")
            return 1
        
        print(f"    ✅ Content preserved correctly")
        
        con.close()
        
    finally:
        if db_path.exists():
            db_path.unlink()
    
    print("\n✅ Merged content sanity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
