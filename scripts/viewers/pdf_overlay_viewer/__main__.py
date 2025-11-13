from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .assets import INDEX_TEMPLATE, ASSETS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy overlay viewer assets into a stage directory.")
    parser.add_argument(
        "--stage-dir",
        required=True,
        help="Path to the stage output directory (e.g. data/results/.../09a_pdf_annotator)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing viewer files if they already exist.",
    )
    args = parser.parse_args(argv)

    stage_dir = Path(args.stage_dir).expanduser().resolve()
    if not stage_dir.exists():
        parser.error(f"Stage directory does not exist: {stage_dir}")

    vis_dir = stage_dir / "visual_output"
    overlay_map_path = vis_dir / "overlay_map.json"
    if not overlay_map_path.exists():
        parser.error(f"overlay_map.json not found at {overlay_map_path}. Run the pipeline first.")

    try:
        overlay_data = json.loads(overlay_map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        parser.error(f"Failed to parse overlay_map.json: {exc}")

    vis_dir.mkdir(parents=True, exist_ok=True)

    index_content = INDEX_TEMPLATE.replace("__OVERLAY_DATA__", json.dumps(overlay_data))
    index_path = vis_dir / "index.html"
    if index_path.exists() and not args.force:
        print(f"[viewer] index.html already exists at {index_path} (use --force to overwrite).")
    else:
        index_path.write_text(index_content, encoding="utf-8")

    for name, content in ASSETS.items():
        target = vis_dir / name
        if target.exists() and not args.force:
            continue
        target.write_text(content, encoding="utf-8")

    print(f"[viewer] Viewer assets available at {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
