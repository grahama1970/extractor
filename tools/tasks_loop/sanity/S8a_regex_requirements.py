#!/usr/bin/env python3
"""
S8a_regex_requirements.py - Sanity check for deterministic requirement extraction regex.

Purpose:
- Verify that the regex patterns from S08 extract requirements correctly.
- This is the deterministic extraction logic (no LLM needed).

Regex Patterns (from s08_extract_requirements.py):
1. Formal: REQ-XXX: ... (id_prefixes pattern)
2. Modal: Sentences containing shall/must/will/should/required

Dependencies:
- re (standard library)

Success Criteria:
- Formal pattern matches REQ-XXX format
- Modal pattern matches shall/must sentences
"""

import re
import sys


# Test text containing various requirement formats
TEST_TEXT = """
4.1.5.4 BHT (Branch History Table) submodule

REQ-BHT-001: The BHT shall record the last eight branch outcomes in a circular buffer.

The prediction mechanism must update on every taken branch. Each entry will contain
the branch address and the outcome bit.

REQ-BHT-002: The debug CSR shall expose the current BHT state.

Additional context: The system should support flushing the BHT on context switches.
This is required for security isolation between processes.

Note: Performance counters are optional and not covered by this specification.
"""

# Expected extractions
EXPECTED_FORMAL = ["REQ-BHT-001", "REQ-BHT-002"]
EXPECTED_MODAL_KEYWORDS = ["shall", "must", "will", "should", "required"]


def extract_formal(text: str, id_prefixes: list = None) -> list:
    """Extract formal requirements (REQ-XXX: ...) pattern."""
    if id_prefixes is None:
        id_prefixes = ["REQ-BHT-", "REQ-"]
    
    prefix_pattern = '|'.join(re.escape(p) for p in id_prefixes)
    formal_pattern = rf'({prefix_pattern}[\w-]+):\s*(.+?)(?=\.\s+[A-Z]|\n\n|{prefix_pattern}|$)'
    
    results = []
    for match in re.finditer(formal_pattern, text, re.IGNORECASE | re.DOTALL):
        req_id = match.group(1)
        req_text = match.group(2).strip()
        results.append({
            "id": req_id,
            "text": req_text,
            "source": "regex_formal"
        })
    return results


def extract_modal(text: str, modal_verbs: list = None) -> list:
    """Extract sentences with modal verbs (shall/must/will/should/required)."""
    if modal_verbs is None:
        modal_verbs = ["shall", "must", "will", "should", "required"]
    
    modal_pattern = r'([^.]+?(?:' + '|'.join(modal_verbs) + r')[^.]+?\.)'
    
    results = []
    for match in re.finditer(modal_pattern, text, re.IGNORECASE):
        sentence = match.group(1).strip()
        results.append({
            "id": None,
            "text": sentence,
            "source": "regex_modal"
        })
    return results


def main() -> int:
    print("Testing deterministic requirement extraction regex...")
    
    # === Test Formal Pattern ===
    print("\n[1] Testing formal pattern (REQ-XXX: ...)...")
    formal_results = extract_formal(TEST_TEXT)
    
    formal_ids = [r["id"] for r in formal_results]
    print(f"    Found: {formal_ids}")
    
    for expected in EXPECTED_FORMAL:
        if expected not in formal_ids:
            print(f"FAIL: Expected '{expected}' not found")
            return 1
    
    print(f"    ✅ Found all {len(EXPECTED_FORMAL)} formal requirements")
    
    # === Test Modal Pattern ===
    print("\n[2] Testing modal pattern (shall/must/will/...)...")
    modal_results = extract_modal(TEST_TEXT)
    
    print(f"    Found {len(modal_results)} modal sentences")
    
    # Check that we found sentences with each modal verb
    found_keywords = set()
    for r in modal_results:
        text_lower = r["text"].lower()
        for kw in EXPECTED_MODAL_KEYWORDS:
            if kw in text_lower:
                found_keywords.add(kw)
    
    print(f"    Modal verbs found: {found_keywords}")
    
    # We expect at least 3 different modal verbs in test text
    if len(found_keywords) < 3:
        print(f"FAIL: Expected at least 3 modal verbs, found {len(found_keywords)}")
        return 1
    
    print(f"    ✅ Found {len(found_keywords)} different modal verbs")
    
    # === Verify no empty extractions ===
    print("\n[3] Verifying extraction quality...")
    all_results = formal_results + modal_results
    
    for r in all_results:
        if not r["text"] or len(r["text"]) < 10:
            print(f"FAIL: Empty or too short extraction: {r}")
            return 1
    
    print(f"    ✅ All {len(all_results)} extractions have valid text")
    
    print("\n✅ Requirement regex sanity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
