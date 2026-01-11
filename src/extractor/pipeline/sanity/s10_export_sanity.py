
import duckdb
import os
from pathlib import Path
from extractor.pipeline.steps.s10_markdown_exporter import run as run_s10

def main():
    # 1. create dummy db
    db_path = Path("s10_sanity.duckdb")
    if db_path.exists():
        db_path.unlink()
        
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE merged_content (id VARCHAR, section_id VARCHAR, page INTEGER, type VARCHAR, content VARCHAR, asset_id VARCHAR, sort_order INTEGER)")
    con.execute("CREATE TABLE sections (id VARCHAR, title VARCHAR, page_start INTEGER, page_end INTEGER, parent_id VARCHAR, display_title VARCHAR, title_display VARCHAR, llm_title VARCHAR, llm_summary VARCHAR, llm_key_concepts VARCHAR, llm_metadata VARCHAR)")
    con.execute("CREATE TABLE tables (id VARCHAR, page INTEGER, x0 DOUBLE, y0 DOUBLE, x1 DOUBLE, y1 DOUBLE, csv_data VARCHAR, html_data VARCHAR, section_id VARCHAR, sort_order INTEGER, llm_title VARCHAR, llm_description VARCHAR, image_path VARCHAR)")
    con.execute("CREATE TABLE figures (id VARCHAR, page INTEGER, x0 DOUBLE, y0 DOUBLE, x1 DOUBLE, y1 DOUBLE, image_path VARCHAR, section_id VARCHAR, sort_order INTEGER, llm_title VARCHAR, llm_description VARCHAR)")
    con.execute("CREATE TABLE requirements (id VARCHAR, req_id VARCHAR, section_id VARCHAR, text VARCHAR, type VARCHAR, confidence DOUBLE, citation_snippet VARCHAR, is_table_row BOOLEAN, is_conditional BOOLEAN, condition_text VARCHAR, sort_order INTEGER, page INTEGER, y0 DOUBLE, proving_status VARCHAR, verification_artifact VARCHAR, proof_file VARCHAR)")
    
    # Insert Dummy Data
    con.execute("INSERT INTO sections (id, title) VALUES ('s1', 'Sanity Section')")
    con.execute("INSERT INTO merged_content VALUES ('mc1', 's1', 1, 'text', 'Hello World', NULL, 100)")
    con.execute("INSERT INTO merged_content VALUES ('mc2', 's1', 1, 'table', 'TABLE_PLACEHOLDER', 't1', 200)")
    
    # Table logic
    con.execute("INSERT INTO tables (id, section_id, csv_data, sort_order) VALUES ('t1', 's1', 'Col1,Col2\nVal1,Val2', 200)")
    
    con.close()
    
    print("Running Export...")
    try:
        out = run_s10(db_path, Path("."))
        print(f"Exported to: {out}")
        print("--- Content ---")
        with open(out, 'r') as f:
            print(f.read())
    except Exception as e:
        print(f"Failed: {e}")
        
    # cleanup
    if db_path.exists():
        db_path.unlink()

if __name__ == "__main__":
    main()
