#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///

from __future__ import annotations
import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


def read_json_report(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


@app.command()
def generate(
    report: str = typer.Option("test-results.json", help="Path to pytest JSON report"),
    out_md: str = typer.Option(
        "scripts/artifacts/lessons_status_report.md", help="Output Markdown path"
    ),
):
    """Generate a Markdown status summary from pytest JSON report without touching curated docs."""
    report_path = Path(report)
    if not report_path.exists():
        typer.echo(f"Report not found: {report}")
        raise typer.Exit(2)
    data = read_json_report(report_path)
    if not data:
        typer.echo("Could not parse report JSON")
        raise typer.Exit(3)

    # Aggregate basic stats
    totals = data.get("summary", {})
    tests = data.get("tests", [])
    failed = [t for t in tests if t.get("outcome") == "failed"]
    skipped = [t for t in tests if t.get("outcome") == "skipped"]
    passed = [t for t in tests if t.get("outcome") == "passed"]

    md_lines = []
    md_lines.append("# Lessons Learned – Test Status Report")
    md_lines.append("")
    md_lines.append(f"Generated from: `{report}`")
    md_lines.append("")
    md_lines.append("## Summary")
    md_lines.append("")
    md_lines.append("- ✅ Passed: {}".format(len(passed)))
    md_lines.append("- ❌ Failed: {}".format(len(failed)))
    md_lines.append("- ⏭️ Skipped: {}".format(len(skipped)))
    if totals:
        md_lines.append("- Total duration: {}s".format(totals.get("duration", "n/a")))
    md_lines.append("")

    if failed:
        md_lines.append("## Failures")
        md_lines.append("")
        for t in failed:
            nodeid = t.get("nodeid")
            md_lines.append(f"- {nodeid}")
        md_lines.append("")

    if skipped:
        md_lines.append("## Skipped")
        md_lines.append("")
        for t in skipped[:50]:
            nodeid = t.get("nodeid")
            reason = t.get("keywords", [])
            md_lines.append(f"- {nodeid}  (keywords: {', '.join(reason)})")
        md_lines.append("")

    out_path = Path(out_md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md_lines), encoding="utf-8")
    typer.echo(f"Wrote {out_md}")


if __name__ == "__main__":
    app()
