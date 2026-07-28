#!/usr/bin/env python3
import json
from pathlib import Path
import sys


def main(sections_path: str, out_dir: str) -> None:
    """Generate section summaries from JSON and save to specified directory."""
    sections = json.loads(Path(sections_path).read_text(encoding="utf-8"))
    out_root = Path(out_dir) / "09_section_summarizer" / "json_output"
    out_root.mkdir(parents=True, exist_ok=True)
    summaries = []
    for s in sections.get("sections", []):
        sid = s.get("id") or s.get("section_id") or "section"
        text = (s.get("merged_text") or s.get("raw_text") or "").strip()
        snippet = text[:400]
        summaries.append(
            {"section_id": str(sid), "success": True, "summary_data": {"summary": snippet}}
        )
    out = {"summaries": summaries, "timestamp": __import__("datetime").datetime.now().isoformat()}
    out_path = out_root / "09_summaries.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: make_min_summaries.py <sections_json> <results_root>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
