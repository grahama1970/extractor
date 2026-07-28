import argparse
import sys
from pathlib import Path


def main() -> int:
    """Prepare pipeline step output directory, verifying marker on request."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-dir", required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.pipeline_dir) / "sample_step"
    out_dir.mkdir(parents=True, exist_ok=True)
    marker = out_dir / "data.txt"

    if args.verify_only:
        return 0 if marker.exists() else 1

    print("sample step running")
    print("sample stderr line", file=sys.stderr)
    marker.write_text("ok", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
