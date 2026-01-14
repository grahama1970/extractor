#!/usr/bin/env python3
import sys
import duckdb

def main():
    try:
        con = duckdb.connect(":memory:")
        con.execute("CREATE TABLE san (val INTEGER)")
        con.execute("INSERT INTO san VALUES (123)")
        res = con.execute("SELECT val FROM san").fetchone()[0]
        if res == 123:
            print("OK: DuckDB functional")
        else:
            print(f"FAIL: DuckDB returned {res}")
            sys.exit(1)
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
