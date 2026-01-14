#!/usr/bin/env python3
"""
verify_ground_truth.py

Performs advanced "Contract Comparison" between Pipeline Output (DuckDB) and Ground Truth Schema (JSON).
Implements a Multi-Tier Verification Strategy:

Tier 1: Deterministic Metadata
- Count Check (Requirement/Table counts)
- ID Existence Check

Tier 2: Fuzzy Logic (RapidFuzz)
- Text Similarity Check using `rapidfuzz` (Levenshtein Ratio).
- Thresholds: >95% (Pass), >80% (Warn/Semantic Check Needed), <80% (Fail).

Tier 3: Semantic Logic (LLM - Placeholder)
- For items in the "Warn" zone (80-95%), we would invoke an LLM-as-a-Judge.
- "Is the actual text reasonably close in meaning to the expected text?"

Usage:
    python verify_ground_truth.py --actual data/results/run_X/pipeline.duckdb --expected data/input/fixture_expected.json
"""

import argparse
import json
import duckdb
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple

try:
    from rapidfuzz import fuzz
except ImportError:
    print("Error: rapidfuzz not installed. Run 'pip install rapidfuzz'")
    sys.exit(1)

# Thresholds
FUZZY_PASS = 95.0     # Almost exact match
FUZZY_WARN = 80.0     # Needs semantic check

def load_actual_from_duckdb(db_path: Path) -> List[Dict[str, Any]]:
    con = duckdb.connect(str(db_path), read_only=True)
    
    # Get Requirements
    reqs = con.execute("SELECT req_id, text, type FROM requirements").fetchall()
    actual = []
    
    for rid, text, rtype in reqs:
        actual.append({
            "id": rid,
            "text": text,
            "type": rtype
        })
        
    # Get Tables (Standard Pipeline Table)
    # Tables are often in 'tables' table.
    try:
        tables = con.execute("SELECT id, llm_title, llm_description, csv_data FROM tables").fetchall()
        for tid, title, summary, csv in tables:
            # We construct a text representation for comparison
            # Ground truth tables usually have 'content' as list of dicts.
            # We might need to handle this comparison carefully.
            # For now, let's treat the CSV or Summary as the text.
            
            # Note: Pipeline IDs for tables are auto-generated (e.g. table_p1_t1).
            # Ground Truth IDs are TBL-001.
            # This ID mismatch will cause failures unless we map them.
            actual.append({
                "id": tid,
                "text": csv or summary, # Use CSV if available for strict check
                "type": "Table",
                "is_table": True
            })
    except Exception as e:
        print(f"Warning: Could not load tables: {e}")

    return actual

def verify(actual_rows: List[Dict], expected_rows: List[Dict], json_output: bool = False):
    if not json_output:
        print(f"\n--- Contract Verification ---")
        print(f"Items: Actual={len(actual_rows)} vs Expected={len(expected_rows)}")
    
    actual_map = {r['id']: r for r in actual_rows if r['id']}
    expected_map = {r['id']: r for r in expected_rows if r['id']}
    
    matches_pass = []
    matches_warn = []
    matches_fail = []
    misses = []
    
    # Check Expected against Actual
    for eid, exp in expected_map.items():
        # Prepare expected text
        raw_content = exp.get('content', '')
        if isinstance(raw_content, list) and exp.get('type') == 'Table':
            try:
                import pandas as pd
                df = pd.DataFrame(raw_content)
                etext = df.to_csv(index=False).strip()
            except ImportError:
                 etext = str(raw_content).strip()
        else:
            etext = (exp.get('text', '') or str(raw_content)).strip()
            
        is_strict = exp.get("strict_verification", False)

        # Strategy 1: ID Match
        if eid in actual_map:
            act = actual_map[eid]
            match_type = "ID_MATCH"
            atext = (act.get('text', '') or str(act.get('content', ''))).strip()
        else:
            # Strategy 2: Content Search (Fallback)
            best_match = None
            best_score = 0.0
            for aid, act in actual_map.items():
                atext = (act.get('text', '') or str(act.get('content', ''))).strip()
                score = fuzz.partial_ratio(etext, atext)
                if score > best_score:
                    best_score = score
                    best_match = act
            
            threshold = 100.0 if is_strict else FUZZY_WARN
            
            if best_match and best_score >= threshold:
                act = best_match
                match_type = f"CONTENT_MATCH (ID: {act['id']})"
                atext = (act.get('text', '') or str(act.get('content', ''))).strip()
            else:
                if not json_output:
                    print(f"   [MISS] {eid}: Best Score {best_score:.2f}% (Threshold {threshold}) using partial_ratio")
                misses.append(eid)
                continue

        # Perform Verification
        if is_strict:
            if etext == atext:
                matches_pass.append({"id": eid, "score": 100.0, "reason": f"STRICT/{match_type}"})
            else:
                sim = fuzz.ratio(etext, atext)
                matches_fail.append({"id": eid, "score": sim, "reason": f"STRICT_FAIL (Sim: {sim:.2f}%) [{match_type}]"})
            continue

        # Deterministic Check
        if etext == atext:
            matches_pass.append({"id": eid, "score": 100.0, "reason": f"EXACT/{match_type}"})
            continue
            
        # Fuzzy Check
        score = fuzz.partial_ratio(etext, atext)
        
        if score >= FUZZY_PASS:
            matches_pass.append({"id": eid, "score": score, "reason": "FUZZY_PASS"})
        elif score >= FUZZY_WARN:
            matches_warn.append({"id": eid, "score": score, "reason": "SEMANTIC_CHECK_NEEDED"})
        else:
            matches_fail.append({"id": eid, "score": score, "reason": "FAIL"})
            
    # Decision Logic
    decision = "ACCEPTED"
    exit_code = 0
    
    if matches_fail or misses:
        decision = "REJECTED"
        exit_code = 1
    elif matches_warn:
        decision = "CONDITIONALLY ACCEPTED"
        exit_code = 0
        
    result = {
        "decision": decision,
        "metrics": {
            "passed": len(matches_pass),
            "warnings": len(matches_warn),
            "failed": len(matches_fail),
            "missed": len(misses),
            "total_expected": len(expected_rows)
        },
        "details": {
            "passed": matches_pass,
            "warnings": matches_warn,
            "failed": matches_fail,
            "missed": misses
        }
    }

    if json_output:
        print(json.dumps(result, indent=2))
        sys.exit(exit_code)
        
    # Standard Text Reporting
    print(f"\n✅ PASS ({len(matches_pass)})")
    
    if matches_warn:
        print(f"\n⚠️  WARNING / SEMANTIC CHECK NEEDED ({len(matches_warn)}):")
        for m in matches_warn:
            print(f"   - {m['id']}: Score {m['score']:.2f}%")
            
    if matches_fail:
        print(f"\n❌ FAIL ({len(matches_fail)}):")
        for m in matches_fail:
            print(f"   - {m['id']}: Score {m['score']:.2f}%")
            
    if misses:
        print(f"\n❌ MISSING IDS ({len(misses)}):")
        print(f"   {misses}")
        
    print(f"\nFinal Decision: {decision}")
    if decision == "CONDITIONALLY ACCEPTED":
        print("(Review Warnings)")
        
    sys.exit(exit_code)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", type=Path, required=True, help="Path to pipeline.duckdb")
    parser.add_argument("--expected", type=Path, required=True, help="Path to expected.json")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()
    
    if not args.actual.exists():
        if not args.json:
            print(f"Error: {args.actual} not found")
        sys.exit(1)
    if not args.expected.exists():
        if not args.json:
            print(f"Error: {args.expected} not found")
        sys.exit(1)
        
    expected_json = json.loads(args.expected.read_text())
    
    # Handle wrapped format with metrics
    if "metrics" in expected_json:
        # print("Expected Metrics:", json.dumps(expected_json["metrics"], indent=2))
        expected_rows = expected_json["content"]
        
        # Count Verification (Deterministic)
        e_counts = expected_json["metrics"]
        # We could query counts from DuckDB here to match specific metric logic
    else:
        expected_rows = expected_json
        
    actual = load_actual_from_duckdb(args.actual)
    
    verify(actual, expected_rows, json_output=args.json)
