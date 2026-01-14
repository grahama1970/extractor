#!/usr/bin/env python3
"""
Gate Utilities - Shared verification helpers for tasks_loop gates.

Philosophy:
- Gates are EXTERNAL verification—they check that a step produced valid output.
- Steps are PURE execution—they should not verify themselves.
- Sanity checks run BEFORE any project coding to validate dependencies.

Usage in gates:
    from gate_utils import load_json, assert_count, assert_file_exists, GateError
"""

import json
import duckdb
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class GateError(Exception):
    """Raised when a gate assertion fails.
    
    Attributes:
        message: What failed (concise, one line)
        expected: What was expected (optional)
        actual: What was found (optional)
        file: Relevant file path (optional)
        hint: Suggested fix (optional, one line)
    """
    def __init__(
        self, 
        message: str, 
        expected: Any = None, 
        actual: Any = None,
        file: str = None,
        hint: str = None
    ):
        self.message = message
        self.expected = expected
        self.actual = actual
        self.file = file
        self.hint = hint
        super().__init__(message)


# ---------------------------------------------------------------------------
# FILE ASSERTIONS
# ---------------------------------------------------------------------------

def assert_file_exists(path: Path, label: str = None) -> None:
    """Assert that a file exists."""
    if not path.exists():
        raise GateError(f"File not found: {label or path}")


def assert_dir_exists(path: Path, label: str = None) -> None:
    """Assert that a directory exists."""
    if not path.is_dir():
        raise GateError(f"Directory not found: {label or path}")


# ---------------------------------------------------------------------------
# JSON ASSERTIONS
# ---------------------------------------------------------------------------

def load_json(path: Path, required_keys: List[str] = None) -> Dict[str, Any]:
    """Load and validate a JSON file.
    
    Args:
        path: Path to JSON file.
        required_keys: Optional list of keys that MUST exist at top level.
        
    Returns:
        Parsed JSON as dict.
        
    Raises:
        GateError: If file missing, empty, invalid JSON, or missing keys.
    """
    assert_file_exists(path)
    
    if path.stat().st_size == 0:
        raise GateError(f"JSON file is empty: {path}")
    
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise GateError(f"Invalid JSON in {path}: {e}")
    
    for k in (required_keys or []):
        if k not in data:
            raise GateError(f"Missing required key '{k}' in {path}")
    
    return data


# ---------------------------------------------------------------------------
# COUNT ASSERTIONS
# ---------------------------------------------------------------------------

def assert_count(actual: int, expected: int, label: str, op: str = ">=") -> None:
    """Assert a count meets expectations.
    
    Args:
        actual: The actual count.
        expected: The expected threshold.
        label: Human-readable label for error messages.
        op: Comparison operator (">=", "==", ">", etc.)
    """
    ops = {
        ">=": lambda a, e: a >= e,
        "==": lambda a, e: a == e,
        ">": lambda a, e: a > e,
        "<=": lambda a, e: a <= e,
        "<": lambda a, e: a < e,
    }
    
    if op not in ops:
        raise ValueError(f"Unknown operator: {op}")
    
    if not ops[op](actual, expected):
        raise GateError(f"{label}: {actual} {op} {expected} failed")


# ---------------------------------------------------------------------------
# DUCKDB ASSERTIONS
# ---------------------------------------------------------------------------

def assert_table_rows(
    db_path: Union[str, Path],
    table_name: str,
    min_rows: int = 1,
    con: Optional[duckdb.DuckDBPyConnection] = None
) -> int:
    """Assert that a DuckDB table has at least min_rows.
    
    Args:
        db_path: Path to DuckDB file.
        table_name: Name of table to check.
        min_rows: Minimum required row count.
        con: Optional existing connection (avoids lock issues).
        
    Returns:
        Actual row count.
        
    Raises:
        GateError: If table missing or too few rows.
    """
    should_close = False
    
    if con is None:
        db_path = Path(db_path)
        if not db_path.exists():
            raise GateError(f"Database not found: {db_path}")
        con = duckdb.connect(str(db_path), read_only=True)
        should_close = True
    
    try:
        try:
            count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        except Exception:
            raise GateError(f"Table '{table_name}' does not exist or cannot be queried")
        
        if count < min_rows:
            raise GateError(f"Table '{table_name}' has {count} rows, expected >= {min_rows}")
        
        return count
    finally:
        if should_close:
            con.close()


# ---------------------------------------------------------------------------
# GATE RUNNER HELPER
# ---------------------------------------------------------------------------

def format_failure(error: "GateError", gate_name: str) -> str:
    """Format gate failure for headless agent consumption.
    
    Output is CONCISE - one line per key fact. No walls of text.
    """
    lines = [
        f"GATE: {gate_name}",
        f"FAIL: {error.message}",
    ]
    
    if error.expected is not None:
        lines.append(f"EXPECTED: {error.expected}")
    if error.actual is not None:
        lines.append(f"ACTUAL: {error.actual}")
    if error.file:
        lines.append(f"FILE: {error.file}")
    if error.hint:
        lines.append(f"HINT: {error.hint}")
    
    return "\n".join(lines)


def run_gate(name: str, checks: callable) -> int:
    """Standard gate runner with consistent output formatting.
    
    Args:
        name: Gate name (e.g., "S04: Section Builder").
        checks: Callable that performs checks and raises GateError on failure.
        
    Returns:
        Exit code (0 = pass, 1 = fail).
    """
    print(f"== Gate {name} ==")
    try:
        checks()
        print(f"\n✅ Gate {name} PASSED")
        return 0
    except GateError as e:
        print(f"\n{format_failure(e, name)}")
        return 1
    except Exception as e:
        print(f"\nGATE: {name}")
        print(f"FAIL: Unexpected error: {type(e).__name__}")
        print(f"DETAIL: {str(e)[:200]}")
        return 1

