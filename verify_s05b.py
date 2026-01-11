import duckdb
import json
from pathlib import Path

db_path = Path("data/results/pipeline/test_run/pipeline.duckdb")
con = duckdb.connect(str(db_path))

print("\n--- TABLES ---")
tables = con.sql("SELECT id, llm_title, llm_description FROM tables LIMIT 5").fetchall()
for t in tables:
    print(f"ID: {t[0]}")
    print(f"Title: {str(t[1])[:50]}...")
    print(f"Desc:  {str(t[2])[:50]}...")
    print("-" * 20)

print("\n--- FIGURES ---")
figures = con.sql("SELECT id, llm_title, llm_description FROM figures LIMIT 5").fetchall()
for f in figures:
    print(f"ID: {f[0]}")
    print(f"Title: {str(f[1])[:50]}...")
    print(f"Desc:  {str(f[2])[:50]}...")
    print("-" * 20)
