#!/usr/bin/env python3
"""
gate_s13.py - Gate for Knowledge Graph Validation

NOTE: There is no separate "S13" pipeline step in the numbered sequence.
Graph creation is handled by the arango/graph_runner.py utility which
outputs to "11_arango_create_graph/".

This gate validates:
1. Graph edges JSON exists
2. Edge structure is valid
3. Relationship types are present

Usage: python gate_s13.py --fixture <fixture_name>
       python gate_s13.py --skip  # Documents step as N/A
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from gate_utils import GateError, run_gate

ROOT = Path(__file__).resolve().parents[3]
TASKS_LOOP_DIR = Path(__file__).resolve().parent.parent
GRAPH_DIR = ROOT / "data" / "results" / "pipeline" / "11_arango_create_graph"


def load_contract(fixture_name: str) -> dict:
    """Load s13 contract if exists."""
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s13.json"
    if contract_path.exists():
        return json.loads(contract_path.read_text())
    return {}


def checks(fixture_name: str | None, skip: bool = False):
    """Verify knowledge graph output."""
    if skip:
        print("S13: Knowledge graph step documented as N/A")
        print("Graph creation handled by arango/graph_runner.py -> 11_arango_create_graph/")
        return

    # Check graph output directory
    json_dir = GRAPH_DIR / "json_output"
    if not json_dir.exists():
        # Graph creation is optional - clarify rather than fail
        print("CLARIFY: Graph output directory not found")
        print(f"Expected: {json_dir}")
        print("Graph creation is optional (requires embeddings)")
        sys.exit(42)

    # Check for edges JSON
    edges_path = json_dir / "11_graph_edges.json"
    if not edges_path.exists():
        # Check for confirmation file (skipped case)
        confirm_path = json_dir / "11_graph_confirmation.json"
        if confirm_path.exists():
            data = json.loads(confirm_path.read_text())
            print(f"Graph creation skipped: {data.get('reason', 'unknown')}")
            return
        raise GateError(
            message="Graph edges file not found",
            expected="11_graph_edges.json",
            actual="missing",
            file=str(json_dir),
            hint="Run graph_runner or check GRAPH_RELATIONSHIPS_ENABLED",
        )

    # Validate edges structure
    try:
        edges = json.loads(edges_path.read_text())
    except json.JSONDecodeError as e:
        raise GateError(
            message="Invalid JSON in edges file",
            expected="valid JSON",
            actual=str(e),
            file=str(edges_path),
        )

    if not isinstance(edges, list):
        raise GateError(
            message="Edges should be a list",
            expected="list",
            actual=type(edges).__name__,
            file=str(edges_path),
        )

    print(f"Graph edges: {len(edges)} total")

    # Check relationship types
    rel_types = set()
    for edge in edges:
        if isinstance(edge, dict):
            rel_type = edge.get("relationship_type")
            if rel_type:
                rel_types.add(rel_type)

    if rel_types:
        print(f"Relationship types: {sorted(rel_types)}")

    # Check contract expectations
    if fixture_name:
        contract = load_contract(fixture_name)
        expected = contract.get("expected", {})

        expected_edges = expected.get("min_edges")
        if expected_edges is not None and len(edges) < expected_edges:
            raise GateError(
                message="Insufficient edges",
                expected=f">= {expected_edges}",
                actual=len(edges),
                file=str(edges_path),
            )

        expected_types = expected.get("relationship_types")
        if expected_types:
            missing = set(expected_types) - rel_types
            if missing:
                raise GateError(
                    message=f"Missing relationship types: {missing}",
                    expected=expected_types,
                    actual=list(rel_types),
                    file=str(edges_path),
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gate S13: Knowledge Graph (via 11_arango_create_graph)"
    )
    parser.add_argument("--fixture", help="Fixture name (optional)")
    parser.add_argument("--skip", action="store_true", help="Document step as N/A")
    args = parser.parse_args()

    if args.skip:
        checks(None, skip=True)
        sys.exit(0)

    sys.exit(run_gate("S13: Knowledge Graph", lambda: checks(args.fixture)))
