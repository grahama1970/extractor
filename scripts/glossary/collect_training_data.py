#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
# ]
# ///
"""
Collect labeled section titles from the datalake for glossary classifier training.

Harvests section titles from datalake_chunks where metadata indicates glossary
sections, plus negative examples from non-glossary sections.

Output: JSONL file with {"title", "label", "features"} for /classifier-lab.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from arango import ArangoClient  # type: ignore

# Add src/ to path so we can import the shared constants
_SRC_DIR = str(Path(__file__).resolve().parents[2] / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from extractor.pipeline.utils.glossary_extractor import GLOSSARY_KEYWORDS, GLOSSARY_WORDS


def _compute_features(title: str) -> dict:
    """Compute tabular features for a section title."""
    t = title.strip().lower()
    words = t.split()
    return {
        "title_lower": t,
        "has_acronym_word": any(w in t for w in GLOSSARY_WORDS),
        "has_list_prefix": t.startswith("list of"),
        "word_count": len(words),
        "is_all_caps": title.strip().isupper(),
    }


def _is_positive(title: str) -> bool:
    """Check if title matches known glossary patterns."""
    t = title.strip().lower()
    return any(kw in t for kw in GLOSSARY_KEYWORDS)


def collect(output_path: str = "data/glossary_section_titles.jsonl", limit: int = 10000):
    """Harvest section titles from ArangoDB datalake_chunks."""
    url = os.getenv("ARANGO_URL", "http://127.0.0.1:8529")
    db_name = os.getenv("MEMORY_ARANGO_DB", os.getenv("ARANGO_DB", "memory"))
    user = os.getenv("ARANGO_USER", "root")
    password = os.getenv("ARANGO_PASS", os.getenv("ARANGO_PASSWORD", ""))

    client = ArangoClient(hosts=url)
    db = client.db(db_name, username=user, password=password)

    # Query unique section titles from datalake chunks
    aql = """
    FOR c IN datalake_chunks
      FILTER c.source_meta.section_title != null AND c.source_meta.section_title != ""
      COLLECT title = c.source_meta.section_title WITH COUNT INTO cnt
      SORT cnt DESC
      LIMIT @limit
      RETURN {title: title, count: cnt}
    """
    try:
        cur = db.aql.execute(aql, bind_vars={"limit": limit})
        rows = list(cur)
    except Exception as e:
        print(f"ArangoDB query failed: {e}", file=sys.stderr)
        print("Falling back to synthetic training data...", file=sys.stderr)
        rows = _synthetic_data()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    count_pos, count_neg = 0, 0
    with open(out, "w") as f:
        for row in rows:
            title = row["title"] if isinstance(row, dict) else row
            label = _is_positive(title)
            features = _compute_features(title)
            record = {
                "title": title,
                "label": "glossary" if label else "not_glossary",
                "features": features,
            }
            f.write(json.dumps(record) + "\n")
            if label:
                count_pos += 1
            else:
                count_neg += 1

    print(f"Wrote {count_pos + count_neg} rows to {out} (pos={count_pos}, neg={count_neg})")


def _synthetic_data() -> list:
    """Generate synthetic training data when ArangoDB is unavailable."""
    positives = [
        "Acronyms and Definitions", "GLOSSARY", "List of Abbreviations",
        "Nomenclature", "Symbols and Abbreviations", "Terms and Definitions",
        "ABBREVIATIONS, ACRONYMS AND DEFINITIONS", "LIST OF TERMS",
        "Acronyms", "Definitions", "List of Acronyms and Abbreviations",
        "TERMINOLOGY", "Abbreviations", "ACRONYMS AND ABBREVIATIONS",
        "List of Symbols", "NOMENCLATURE — TERMS AND DEFINITIONS",
    ]
    negatives = [
        "Introduction", "Hardware Overview", "Test Results",
        "Table of Contents", "References", "Appendix A",
        "System Requirements", "Performance Analysis", "Conclusion",
        "Background", "Methodology", "Data Collection",
        "Executive Summary", "Scope", "Applicable Documents",
        "Configuration Management", "Quality Assurance", "Risk Assessment",
        "Design Description", "Interface Requirements", "Verification",
    ]
    return [{"title": t} for t in positives + negatives]


if __name__ == "__main__":
    import sys
    output = sys.argv[1] if len(sys.argv) > 1 else "data/glossary_section_titles.jsonl"
    collect(output)
