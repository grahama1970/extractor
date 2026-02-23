#!/usr/bin/env python3
"""
S7b_duckdb_crud.py - Sanity check for DuckDB full CRUD operations.

Purpose:
- Verify that we can Create, Read, Update, and Delete in DuckDB.
- This is the core functionality for S07 (DuckDB Ingest).

Dependencies:
- duckdb

Success Criteria:
- Create: Table created successfully
- Insert: Rows inserted
- Read: Rows can be queried
- Update: Rows can be modified
- Delete: Rows can be removed
- Cleanup: Table can be dropped
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

    print("Testing DuckDB CRUD operations...")

    # Use temp file to avoid conflicts
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=True) as f:
        db_path = Path(f.name)

    # Ensure file doesn't exist (duckdb will create it)
    if db_path.exists():
        db_path.unlink()

    try:
        con = duckdb.connect(str(db_path))

        # === CREATE ===
        print("  [C] Creating table...")
        con.execute(
            """
            CREATE TABLE test_sanity (
                id INTEGER PRIMARY KEY,
                name VARCHAR,
                value DOUBLE
            )
        """
        )

        # Verify table exists
        tables = con.execute("SHOW TABLES").fetchall()
        if not any("test_sanity" in str(t) for t in tables):
            print("FAIL: Table not created")
            return 1
        print("    ✅ Table created")

        # === INSERT (CREATE rows) ===
        print("  [C] Inserting rows...")
        con.execute("INSERT INTO test_sanity VALUES (1, 'alpha', 1.1)")
        con.execute("INSERT INTO test_sanity VALUES (2, 'beta', 2.2)")
        con.execute("INSERT INTO test_sanity VALUES (3, 'gamma', 3.3)")

        count = con.execute("SELECT COUNT(*) FROM test_sanity").fetchone()[0]
        if count != 3:
            print(f"FAIL: Expected 3 rows, got {count}")
            return 1
        print(f"    ✅ Inserted {count} rows")

        # === READ ===
        print("  [R] Reading rows...")
        rows = con.execute("SELECT * FROM test_sanity ORDER BY id").fetchall()
        if len(rows) != 3:
            print(f"FAIL: Expected 3 rows, got {len(rows)}")
            return 1
        if rows[0][1] != "alpha":
            print(f"FAIL: Expected 'alpha', got {rows[0][1]}")
            return 1
        print(f"    ✅ Read {len(rows)} rows correctly")

        # === UPDATE ===
        print("  [U] Updating row...")
        con.execute("UPDATE test_sanity SET value = 9.9 WHERE id = 2")

        updated = con.execute("SELECT value FROM test_sanity WHERE id = 2").fetchone()[0]
        if abs(updated - 9.9) > 0.01:
            print(f"FAIL: Expected 9.9, got {updated}")
            return 1
        print(f"    ✅ Updated row: value = {updated}")

        # === DELETE ===
        print("  [D] Deleting row...")
        con.execute("DELETE FROM test_sanity WHERE id = 3")

        count = con.execute("SELECT COUNT(*) FROM test_sanity").fetchone()[0]
        if count != 2:
            print(f"FAIL: Expected 2 rows after delete, got {count}")
            return 1
        print(f"    ✅ Deleted row: {count} remaining")

        # === CLEANUP ===
        print("  [X] Dropping table...")
        con.execute("DROP TABLE test_sanity")

        tables = con.execute("SHOW TABLES").fetchall()
        if any("test_sanity" in str(t) for t in tables):
            print("FAIL: Table not dropped")
            return 1
        print("    ✅ Table dropped")

        con.close()

    finally:
        # Remove temp db file
        if db_path.exists():
            db_path.unlink()

    print("\n✅ DuckDB CRUD sanity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
