#!/usr/bin/env python3
"""
Stage-10: ArangoDB Exporter — Sync Extracted Knowledge Graph.

Purpose:
- Reads the finalized `pipeline.duckdb` (Documents, Sections, Requirements).
- Upserts nodes and edges into an ArangoDB Graph.
- Enables the "Knowledge Architect" vision by persisting structured data.

Schema:
- Nodes:
    - `documents`
    - `sections`
    - `requirements`
- Edges:
    - `has_section` (Document -> Section)
    - `has_requirement` (Section -> Requirement)

Configuration:
- Env vars: ARANGO_HOST, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD
"""

import os
import sys
import json
import duckdb
import hashlib
from pathlib import Path
from loguru import logger
from rich.console import Console
from arango import ArangoClient
from extractor.pipeline.utils.step_sanity import run_step_sanity

# Initialize
console = Console()
STEP_NAME = "10_arangodb_exporter"

def sanity() -> int:
    return run_step_sanity(STEP_NAME)

def get_arango_client():
    hosts = os.getenv("ARANGO_HOST", "http://localhost:8529")
    db_name = os.getenv("ARANGO_DB", "extractor_graph")
    user = os.getenv("ARANGO_USER", "root")
    password = os.getenv("ARANGO_PASSWORD", "openSesame")
    
    client = ArangoClient(hosts=hosts)
    sys_db = client.db("_system", username=user, password=password)
    
    if not sys_db.has_database(db_name):
        sys_db.create_database(db_name)
    
    return client.db(db_name, username=user, password=password)

def ensure_collections(db):
    # Vertices
    for col in ["documents", "sections", "requirements"]:
        if not db.has_collection(col):
            db.create_collection(col)
            
    # Edges
    for edge in ["has_section", "has_requirement"]:
        if not db.has_collection(edge):
            db.create_collection(edge, edge=True)

def run(input_path: Path, output_dir: Path = None):
    pipeline_dir = input_path.parent.parent if input_path.is_file() else input_path
    db_path = pipeline_dir / "pipeline.duckdb"
    
    if not db_path.exists():
        logger.error(f"DuckDB not found at {db_path}. Cannot export to Graph.")
        return

    # 0. Skip if Arango credentials missing (unless in strict mode?)
    if not os.getenv("ARANGO_HOST") and not os.getenv("ARANGO_PASSWORD"):
        logger.warning("ARANGO_HOST/PASSWORD not set. Skipping Stage 10.")
        return

    try:
        logger.info(f"Connecting to ArangoDB at {os.getenv('ARANGO_HOST', 'localhost')}...")
        adb = get_arango_client()
        ensure_collections(adb)
    except Exception as e:
        logger.error(f"Failed to connect to ArangoDB: {e}")
        return

    con = duckdb.connect(str(db_path), read_only=True)
    
    # 1. Ingest Document (The Root)
    # We infer document metadata from the pipeline run context (or just filename)
    doc_name = pipeline_dir.name
    doc_hash = hashlib.md5(doc_name.encode()).hexdigest()
    doc_key = f"doc_{doc_hash}"
    
    doc_meta = {
        "_key": doc_key,
        "filename": doc_name,
        "path": str(pipeline_dir),
        "ingested_at": "NOW" # placeholder, Arango handles dates
    }
    adb.collection("documents").insert(doc_meta, overwrite=True)
    logger.info(f"Upserted Document: {doc_name}")

    # 2. Ingest Sections
    sections = con.execute("SELECT id, title, page_start, parent_id FROM sections").fetchall()
    logger.info(f"Syncing {len(sections)} sections...")
    
    for s_id, title, p_start, p_id in sections:
        sec_key = hashlib.md5(f"{doc_key}_{s_id}".encode()).hexdigest()
        
        # Vertex
        sec_node = {
            "_key": sec_key,
            "original_id": s_id,
            "title": title,
            "page_start": p_start
        }
        adb.collection("sections").insert(sec_node, overwrite=True)
        
        # Edge: Document -> Section (only for top level? No, map all to Doc for provenance)
        adb.collection("has_section").insert({
            "_from": f"documents/{doc_key}",
            "_to": f"sections/{sec_key}",
            "type": "contains"
        }, overwrite=True)
        
        # Edge: Section -> Parent Section (Hierarchy)
        if p_id:
            parent_key = hashlib.md5(f"{doc_key}_{p_id}".encode()).hexdigest()
            adb.collection("has_section").insert({
                "_from": f"sections/{parent_key}",
                "_to": f"sections/{sec_key}",
                "type": "sub_section"
            }, overwrite=True)

    # 3. Ingest Requirements (The Value)
    # Check if table exists first (S08 might have been skipped)
    tables = con.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    
    if "requirements" in table_names:
        reqs = con.execute("""
            SELECT req_id, text, type, confidence, section_id, citation_snippet, is_table_row 
            FROM requirements
        """).fetchall()
        logger.info(f"Syncing {len(reqs)} requirements...")
        
        for r_id, text, r_type, conf, s_id, citation, is_tbl in reqs:
            # Vertex
            # r_id from DuckDB is already a UUID usually
            req_key = r_id 
            
            req_node = {
                "_key": req_key,
                "text": text,
                "type": r_type,
                "confidence": conf,
                "citation": citation,
                "source_type": "table" if is_tbl else "text"
            }
            adb.collection("requirements").insert(req_node, overwrite=True)
            
            # Edge: Section -> Requirement
            if s_id:
                sec_key = hashlib.md5(f"{doc_key}_{s_id}".encode()).hexdigest()
                adb.collection("has_requirement").insert({
                    "_from": f"sections/{sec_key}",
                    "_to": f"requirements/{req_key}",
                    "confidence": conf
                }, overwrite=True)
    else:
        logger.warning("No 'requirements' table found in DuckDB. S08 was likely skipped.")

    con.close()
    logger.info("Stage 10 Graph Sync Complete.")
    
if __name__ == "__main__":
    import sys
    
    # Keep simple sanity check if needed
    if len(sys.argv) > 1 and sys.argv[1] == "sanity":
        sys.exit(sanity())

    # Deprecation
    print("❌ DIRECT EXECUTION DEPRECATED", file=sys.stderr)
    print("Please use the pipeline orchestrator:", file=sys.stderr)
    print("  python -m extractor.pipeline --pdf <PDF> --out <DIR>", file=sys.stderr)
    sys.exit(1)
