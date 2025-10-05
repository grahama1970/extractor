#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def load_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--stages", required=True)
    ap.add_argument("--db", default="extractor")
    ap.add_argument("--url", default="http://127.0.0.1:8529")
    args = ap.parse_args()

    stages = Path(args.stages)
    sections = load_json(stages / "04_section_builder" / "json_output" / "04_sections.json")
    tables = load_json(stages / "05_table_extractor" / "json_output" / "05_tables.json")
    figures = load_json(stages / "06_figure_extractor" / "json_output" / "06_figures.json")

    # TODO: connect to ArangoDB and upsert nodes/edges as per your schema.
    # This is a placeholder that prints a summary for alpha.
    sec_ct = len(sections.get("sections", []))
    tab_ct = len(tables.get("tables", []))
    fig_ct = len(figures.get("figures", []))
    summary = {
        "ok": True,
        "url": args.url,
        "db": args.db,
        "run_id": args.run_id,
        "counts": {"sections": sec_ct, "tables": tab_ct, "figures": fig_ct}
    }
    # Write a local audit file; real exporter would write to DB
    out = Path("arango_export")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.run_id}_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

