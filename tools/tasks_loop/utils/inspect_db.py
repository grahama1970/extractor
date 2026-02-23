import duckdb
import sys


def inspect(db_path):
    con = duckdb.connect(str(db_path), read_only=True)
    print("Tables in DB:", con.execute("SHOW TABLES").fetchall())

    try:
        reqs = con.execute("SELECT req_id, text, type FROM requirements").fetchall()
        print(f"\nRequirements ({len(reqs)}):")
        for r in reqs:
            print(r)
    except Exception as e:
        print(f"Error querying requirements: {e}")

    try:
        # Check for extracted_tables or similar
        # S07 usually creates 'tables' or 'extracted_tables' if configured?
        # Actually S07 imports 05_tables.json into a table?
        # Let's check available tables first from output above, but for now try 'tables'
        tables = con.execute("SELECT * FROM tables").fetchall()
        print(f"\nTables ({len(tables)}):")
        for t in tables:
            print(t)
    except Exception as e:
        print(f"Error querying tables: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: inspect_db.py <db_path>")
        sys.exit(1)
    inspect(sys.argv[1])
