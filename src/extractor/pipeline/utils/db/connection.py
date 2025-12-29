import duckdb
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def get_connection(db_path: Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """
    Establish a connection to the DuckDB database.
    Ensures the parent directory exists.
    Attempts to load the 'vss' extension for vector similarity search.
    """
    if not db_path.parent.exists():
        logger.info(f"Creating database directory: {db_path.parent}")
        db_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Connecting to DuckDB at {db_path} (read_only={read_only})")
    con = duckdb.connect(str(db_path), read_only=read_only)
    
    # Optional: Install/Load extensions
    # We silently fail if internet is not available or extension fails, 
    # as it's not strictly required for Phase 1.
    try:
        con.execute("INSTALL vss; LOAD vss;")
        logger.debug("DuckDB 'vss' extension loaded.")
    except Exception as e:
        logger.warning(f"Could not load DuckDB 'vss' extension: {e}. Vector search may be unavailable.")
        
    return con
