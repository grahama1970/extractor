#!/usr/bin/env python3
import argparse
import fitz  # PyMuPDF
from pathlib import Path
from generate_scale_fixture import create_scale_fixture

# P1=tasks_loop, P2=tools, P3=extractor (ROOT)
FILE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = FILE_ROOT.parent.parent.parent
# Artifacts are in ~/.gemini
ARTIFACTS_DIR = Path("/home/graham/.gemini/antigravity/brain/e798a01e-b43d-4bf8-8404-0a8308348507")


def generate_preview(config_path: Path, output_name: str, seed: int = 42):
    # 1. Paths
    out_dir = PROJECT_ROOT / "data/debug/mimic_preview"
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = out_dir / f"{output_name}.pdf"

    # 2. Generate PDF using the Core Generator
    create_scale_fixture(pdf_path, page_count=5, config_path=config_path, seed=seed)

    # 3. Render Images
    doc = fitz.open(pdf_path)
    image_paths = []

    for i in range(len(doc)):
        page = doc[i]
        pix = page.get_pixmap(dpi=150)
        img_path = out_dir / f"{output_name}_p{i+1}.png"
        pix.save(img_path)
        image_paths.append(img_path)

    # 4. Load Expected Text
    md_path = pdf_path.with_suffix(".md")
    if md_path.exists():
        expected_lines = md_path.read_text().splitlines()
    else:
        expected_lines = ["(No markdown generated)"]

    # 5. Build Report (Markdown)
    report_lines = []
    report_lines.append(f"# Mimic Preview: {output_name}")
    report_lines.append(f"- **Seed**: {seed}")
    report_lines.append(f"- **Config**: `{config_path}`")
    report_lines.append(f"- **PDF**: `{pdf_path}`")

    # Config Dump
    if config_path:
        cfg_content = config_path.read_text()
        report_lines.append("## Configuration")
        report_lines.append("```yaml")
        report_lines.append(cfg_content)
        report_lines.append("```")

    report_lines.append("## Pages & Ground Truth")

    # We display Page Image then Expected Text (approximate chunking)
    # The expected MD is flat, so we can't easily split by page unless generator supports it.
    # For now, just dump all text at bottom? Or try to interleave?
    # Generator output `expected_md_lines` isn't accessible here easily without parsing.
    # We'll just show images in a carousel or list, then full text.

    for i, img in enumerate(image_paths):
        # Copy image to Artifacts for embedding
        dest_name = f"mimic_preview_{output_name}_p{i+1}.png"
        dest_path = ARTIFACTS_DIR / dest_name
        if dest_path.exists():
            dest_path.unlink()

        # Manually copy bytes
        dest_path.write_bytes(img.read_bytes())

        report_lines.append(f"### Page {i+1}")
        report_lines.append(f"![Page {i+1} Preview](file://{dest_path})")
        report_lines.append("---")

    report_lines.append("## Expected Markdown (Ground Truth)")
    report_lines.append("```markdown")
    report_lines.append("\n".join(expected_lines))
    report_lines.append("```")

    # Save Report
    report_path = ARTIFACTS_DIR / "MIMIC_PREVIEW_REPORT.md"
    report_path.write_text("\n".join(report_lines))

    print(f"Report generated at: {report_path}")
    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--name", type=str, default="chaos_v1")
    args = parser.parse_args()

    generate_preview(args.config, args.name, args.seed)
