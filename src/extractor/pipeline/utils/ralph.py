"""
Ralph Wiggum Pipeline Assistant Utilities
"I'm helping!" -- Active verification for pipeline steps.

This module provides helper functions to assert that pipeline steps
are producing MEANINGFUL output (non-zero rows, valid content)
rather than just exiting with code 0.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import duckdb
from loguru import logger

class RalphError(Exception):
    """Raised when Ralph determines a step is NOT helping."""
    pass

def check_table_has_rows(
    db_path: Union[str, Path, Any], 
    table_name: str, 
    min_rows: int = 1,
    col_check: Optional[Dict[str, Any]] = None,
    con: Optional[duckdb.DuckDBPyConnection] = None
) -> int:
    """Asserts that a DuckDB table exists and has at least min_rows.
    
    Args:
        db_path: Path to DuckDB database OR existing connection
        table_name: Name of table to check
        min_rows: Minimum valid row count (default 1)
        col_check: Optional dict of {col_name: expected_value} to check in first row
        con: Optional existing connection to use (prevents lock errors)
        
    Returns:
        int: Actual row count found
        
    Raises:
        RalphError: If table missing or empty
    """
    should_close = False
    
    if con:
        # Use provided connection
        pass
    else:
        # Open new connection
        if not os.path.exists(str(db_path)):
            raise RalphError(f"Database not found: {db_path}")
        try:
            con = duckdb.connect(str(db_path), read_only=True)
            should_close = True
        except Exception as e:
            raise RalphError(f"Failed to connect to DB: {e}")
        
    try:
        # Check existence first
        # Note: information_schema might differ if con is attached to other dbs
        # safer to just try querying the table directly
        try:
            count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        except Exception:
             raise RalphError(f"Table '{table_name}' does not exist or cannot be queried")

        logger.info(f"Ralph: Table '{table_name}' has {count} rows (required: {min_rows})")
        
        if count < min_rows:
            raise RalphError(f"Table '{table_name}' has {count} rows, expected at least {min_rows}. NOT HELPING!")
            
        return count
        
    except Exception as e:
        if isinstance(e, RalphError):
            raise
        raise RalphError(f"Database check failed for '{table_name}': {str(e)}")
    finally:
        if should_close and con:
            try:
                con.close()
            except: pass

def check_json_file_valid(
    path: Union[str, Path], 
    key_check: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Asserts that a JSON file exists, is valid JSON, and optionally contains keys.
    
    Args:
        path: Path to JSON file
        key_check: Optional list of top-level keys that MUST exist
        
    Returns:
        Dict: Parsed JSON content
        
    Raises:
        RalphError: If file missing, empty, invalid, or missing keys
    """
    p = Path(path)
    if not p.exists():
        raise RalphError(f"File not found: {path}")
        
    if p.stat().st_size == 0:
        raise RalphError(f"File is empty: {path}")
        
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise RalphError(f"File contains invalid JSON: {path} ({str(e)})")
        
    if key_check:
        for k in key_check:
            if k not in data:
                raise RalphError(f"JSON missing required key '{k}': {path}")
                
    logger.info(f"Ralph: Validated {p.name} ({len(data)} items/keys)")
    return data

def assert_helping(condition: bool, message: str):
    """Simple assertion wrapper."""
    if not condition:
        raise RalphError(f"NOT HELPING: {message}")
    logger.info(f"Ralph: check passed - {message}")
