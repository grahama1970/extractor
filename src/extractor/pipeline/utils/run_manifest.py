from __future__ import annotations
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json
import os


def _collect_env(keys: List[str]) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {}
    for k in keys:
        out[k] = os.getenv(k)
    return out


class RunManifest:
    def __init__(self, results_root: Path):
        self.results_root = Path(results_root)
        self.path = self.results_root / "final_report.json"
        self.payload: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "Started",
            "stages": [],
            "env": _collect_env(
                [
                    "STAGE07_USE_LAYOUT_SKETCH",
                    "STAGE07_LAYOUT_CONF_THRESH",
                    "TABLE_SELECT_ONE_PER_PAGE",
                    "STAGE06B_EMIT_MERGE_HINTS",
                ]
            ),
            "diagnostics": [],
        }

    def record_stage(
        self,
        name: str,
        status: str,
        output_paths: Dict[str, str],
        counts: Optional[Dict[str, int]] = None,
        diag_count: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry: Dict[str, Any] = {
            "name": name,
            "status": status,
            "output_paths": output_paths,
            "counts": counts or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        if extra:
            entry["extra"] = extra
        self.payload["stages"].append(entry)
        if diag_count is not None:
            self.payload["diagnostics"].append({"stage": name, "count": int(diag_count)})

    def finalize(self, status: str = "Completed") -> None:
        self.payload["status"] = status
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2))
