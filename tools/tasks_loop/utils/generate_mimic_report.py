#!/usr/bin/env python3
"""
generate_mimic_report.py

Generates an interactive HTML report comparing:
1. The Mimic PDF (source.pdf)
2. The Extracted Markdown (full_document.md)
3. The Expected Markdown (source_expected.md)

Usage:
    python generate_mimic_report.py --fixture synthesis_messy_BHT
"""
import argparse
import html
import subprocess
from pathlib import Path

TASKS_LOOP = Path(__file__).resolve().parents[1]
FIXTURES_DIR = TASKS_LOOP / "fixtures"
RESULTS_DIR = (
    TASKS_LOOP.parent.parent / "data/results/pipeline/10_markdown_exporter/markdown_output"
)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Mimic Report: {fixture}</title>
    <style>
        body {{ font-family: sans-serif; margin: 0; padding: 0; display: flex; height: 100vh; overflow: hidden; }}
        .sidebar {{ width: 250px; background: #f4f4f4; border-right: 1px solid #ddd; padding: 20px; overflow-y: auto; }}
        .main {{ flex: 1; display: flex; flex-direction: column; }}
        .header {{ padding: 10px 20px; background: #333; color: white; display: flex; justify-content: space-between; align-items: center; }}
        .toolbar {{ padding: 10px; background: #eee; border-bottom: 1px solid #ddd; }}
        .content {{ flex: 1; display: flex; overflow: hidden; }}
        .panel {{ flex: 1; padding: 20px; overflow-y: auto; border-right: 1px solid #ddd; }}
        .panel:last-child {{ border-right: none; }}
        h2 {{ margin-top: 0; font-size: 16px; border-bottom: 2px solid #333; padding-bottom: 5px; }}
        pre {{ white-space: pre-wrap; font-family: monospace; background: #f9f9f9; padding: 10px; border: 1px solid #e0e0e0; }}
        .diff-add {{ background-color: #e6ffec; }}
        .diff-del {{ background-color: #ffebe9; }}
        .meta-item {{ margin-bottom: 10px; font-size: 14px; }}
        .meta-label {{ font-weight: bold; color: #555; }}
        iframe {{ width: 100%; height: 100%; border: none; }}
        button {{ padding: 5px 10px; cursor: pointer; }}
        .tab-btn {{ background: #ddd; border: none; padding: 8px 16px; margin-right: 2px; }}
        .tab-btn.active {{ background: white; font-weight: bold; }}
    </style>
    <script>
        function showTab(tabId) {{
            document.querySelectorAll('.tab-view').forEach(el => el.style.display = 'none');
            document.getElementById(tabId).style.display = 'flex';
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('btn-' + tabId).classList.add('active');
        }}
    </script>
</head>
<body>
    <div class="sidebar">
        <h3>Fixture Stats</h3>
        <div class="meta-item"><span class="meta-label">Name:</span> {fixture}</div>
        <div class="meta-item"><span class="meta-label">PDF Size:</span> {pdf_size} bytes</div>
        <div class="meta-item"><span class="meta-label">MD Lines:</span> {md_lines}</div>
        <hr>
        <h4>Actions</h4>
        <p><em>(Mock buttons)</em></p>
        <button onclick="alert('Configuration editing not implemented in prototype')">Edit Config</button>
        <button onclick="alert('Regenerating fixture...')">Regenerate</button>
    </div>
    
    <div class="main">
        <div class="header">
            <span>Collaborative Mimic Review</span>
            <span>{timestamp}</span>
        </div>
        
        <div class="toolbar">
            <button id="btn-view-compare" class="tab-btn active" onclick="showTab('view-compare')">Compare (Side-by-Side)</button>
            <button id="btn-view-diff" class="tab-btn" onclick="showTab('view-diff')">Diff Report</button>
            <button id="btn-view-spec" class="tab-btn" onclick="showTab('view-spec')">Spec & Config</button>
        </div>
        
        <div id="view-compare" class="content tab-view">
            <div class="panel">
                <h2>Extracted Markdown (Actual)</h2>
                <pre>{extracted_md}</pre>
            </div>
            <div class="panel">
                <h2>Expected Markdown (Ground Truth)</h2>
                <pre>{expected_md}</pre>
            </div>
        </div>
        
        <div id="view-diff" class="content tab-view" style="display:none;">
             <div class="panel">
                <h2>Diff Output</h2>
                <pre>{diff_output}</pre>
            </div>
        </div>

        <div id="view-spec" class="content tab-view" style="display:none;">
             <div class="panel">
                <h2>SPEC.md</h2>
                <pre>{spec_content}</pre>
            </div>
        </div>
    </div>
</body>
</html>
"""


def generate_report(fixture_name: str):
    fixture_dir = FIXTURES_DIR / fixture_name

    # 1. Gather Paths
    pdf_path = fixture_dir / "source.pdf"
    spec_path = fixture_dir / "SPEC.md"
    expected_md_path = fixture_dir / "source_expected.md"
    extracted_md_path = RESULTS_DIR / "full_document.md"
    # NOTE: extracted path assumes mostly single-run environment or manually copied.
    # Ideally extracting from '10_markdown_exporter'

    # 2. Read Content
    pdf_size = pdf_path.stat().st_size if pdf_path.exists() else 0
    spec_content = spec_path.read_text() if spec_path.exists() else "MISSING SPEC"
    expected_md = expected_md_path.read_text() if expected_md_path.exists() else "MISSING EXPECTED"

    extracted_md = "MISSING EXTRACTED OUTPUT"
    if extracted_md_path.exists():
        extracted_md = extracted_md_path.read_text()

    # 3. Generate Diff
    diff_output = "No diff available."
    if expected_md_path.exists() and extracted_md_path.exists():
        # Using subprocess diff for simplicity
        cmd = ["diff", "-u", str(expected_md_path), str(extracted_md_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        # diff returns 1 if differences found, 0 if equal.
        diff_output = res.stdout if res.stdout else "Identical Content (Match)"
        if res.stderr:
            diff_output += "\nSTDERR:\n" + res.stderr

    # 4. Render HTML
    html_content = HTML_TEMPLATE.format(
        fixture=fixture_name,
        pdf_size=pdf_size,
        md_lines=len(extracted_md.splitlines()),
        timestamp="Now",
        extracted_md=html.escape(extracted_md),
        expected_md=html.escape(expected_md),
        diff_output=html.escape(diff_output),
        spec_content=html.escape(spec_content),
    )

    out_path = fixture_dir / "MIMIC_REPORT.html"
    out_path.write_text(html_content)
    print(f"Report generated: {out_path}")
    print(f"Open with: firefox {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()

    generate_report(args.fixture)
