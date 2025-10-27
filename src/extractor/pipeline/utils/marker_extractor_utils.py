#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List


def fallback_simple_extract(pdf_path: Path, out_json: Path) -> List[Dict[str, Any]]:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        os.environ.get("PYTHON", "python"),
        "-m",
        "extractor.core.scripts.simple_marker_extract",
        str(pdf_path),
        str(out_json),
    ]
    subprocess.run(cmd, check=True)
    data = json.loads(out_json.read_text())
    return data.get("blocks") or []

