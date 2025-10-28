from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from extractor.pipeline.utils.debug_utils import ensure_logs_dir, log_timing
from extractor.pipeline.utils.pdf_preflight import strip_annotations_and_normalize


STAGE = "00_preflight"


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _checksum(path: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(pdf_path: str) -> int:
    in_path = Path(pdf_path).expanduser().resolve()
    results_root = Path(os.getenv("RUN_RESULTS_DIR", "data/results/pipeline")).resolve()
    pre_dir = results_root / STAGE / in_path.stem
    ensure_logs_dir(results_root, STAGE)

    pre_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = pre_dir / "clean.pdf"

    # Guard: never write back into data/input
    if str(out_pdf).startswith(str(Path("data/input").resolve())):
        raise RuntimeError(f"Refusing to write under data/input: {out_pdf}")

    # Timed preflight
    meta: Dict[str, Any] = {
        "stage": STAGE,
        "input": str(in_path),
        "output": str(out_pdf),
    }
    try:
        report = strip_annotations_and_normalize(
            in_path,
            out_pdf,
            normalize_rotation=True,
            dedupe_images=True,
            dpi=300,
        )
        log_timing(STAGE, {
            "attempt": "preflight",
            "outcome": "ok",
            "annotations_removed": report.annotations_removed,
            "rotations": report.rotations_applied,
            "image_dupes": report.image_dupes,
        })
    except Exception as e:  # pragma: no cover
        log_timing(STAGE, {"attempt": "preflight", "outcome": "exception", "error": str(e)[:400]})
        raise

    # Manifest
    manifest = {
        "timestamp": _iso(),
        "source": str(in_path),
        "dest": str(out_pdf),
        "sha256": _checksum(out_pdf, "sha256"),
        "md5": _checksum(out_pdf, "md5"),
        "prefilters": {
            "strip_annotations": True,
            "normalize_rotation": True,
            "dpi": 300,
            "image_dedupe": {"metric": "phash", "threshold": 6, "count_dupes": report.image_dupes},
            "colorspace": "RGB (implicit in hash path)",
            "deskew": bool(int(os.getenv("PREFLIGHT_DESKEW", "0") or 0)),
        },
        "report": {
            "pages": report.pages,
            "annotations_removed": report.annotations_removed,
            "rotations_applied": report.rotations_applied,
            "image_dupes": report.image_dupes,
            "notes": report.notes,
        },
    }
    (pre_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (pre_dir / "logs" / "preflight.log").parent.mkdir(parents=True, exist_ok=True)
    (pre_dir / "logs" / "preflight.log").write_text(json.dumps(meta | manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[{STAGE}] clean -> {out_pdf}")
    print(f"[{STAGE}] manifest -> {pre_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m extractor.pipeline.steps.00_preflight <input.pdf>")
        raise SystemExit(2)
    raise SystemExit(run(sys.argv[1]))
