from __future__ import annotations

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Dict


def _sha12(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except Exception:
        return None


def _mini_hash(block: Dict[str, Any]) -> str:
    core = {
        "p": block.get("page") or block.get("page_idx"),
        "t": block.get("block_type"),
        "txt": (block.get("text") or "")[:80],
        "b": block.get("bbox"),
    }
    try:
        payload = json.dumps(core, sort_keys=True, ensure_ascii=False).encode("utf-8")
    except Exception:
        payload = b""
    return hashlib.sha1(payload).hexdigest()[:8]


def build_ui_bundle(results_dir: Path, fail_soft: bool = True) -> None:
    """Aggregate stage artifacts into a single UI-facing JSON bundle.

    Writes: <results_dir>/ui/blocks_full.json
    """
    rd = Path(results_dir)
    try:
        stage02 = rd / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
        stage03 = rd / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
        tables_f = rd / "05_table_extractor" / "json_output" / "05_tables.json"
        figs_f = rd / "06_figure_extractor" / "json_output" / "06_figures.json"
        suspects_f = rd / "suspects.json"
        pdf_guess = list((rd / "01_annotation_processor").glob("*_clean.pdf"))[:1]
        pdf_path = pdf_guess[0] if pdf_guess else None

        s02 = json.loads(stage02.read_text()) if stage02.exists() else {}
        s03 = json.loads(stage03.read_text()) if stage03.exists() else {}
        tjs = json.loads(tables_f.read_text()) if tables_f.exists() else {}
        fjs = json.loads(figs_f.read_text()) if figs_f.exists() else {}
        sus = json.loads(suspects_f.read_text()) if suspects_f.exists() else {}

        # Prefer Stage 03 verified blocks when present
        blocks = (s03.get("blocks") if isinstance(s03, dict) else None) or (s02.get("blocks") if isinstance(s02, dict) else None) or []
        if not isinstance(blocks, list):
            blocks = []
        for b in blocks:
            if isinstance(b, dict):
                b["page"] = b.get("page_idx", b.get("page"))
                b["type"] = b.get("block_type", b.get("type"))
                b["mini_hash"] = _mini_hash(b)

        doc_id = None
        if pdf_path:
            h = _sha12(pdf_path)
            stem = pdf_path.stem.lower().replace(" ", "_")
            doc_id = f"{stem}__{h}" if h else stem

        out_dir = rd / "ui"
        out_dir.mkdir(parents=True, exist_ok=True)
        bundle = {
            "doc_id": doc_id,
            "generated_at": datetime.utcnow().isoformat(),
            "pdf_sha256_12": _sha12(pdf_path),
            "blocks": blocks,
            "tables": tjs.get("tables", []) if isinstance(tjs, dict) else [],
            "figures": fjs.get("figures", []) if isinstance(fjs, dict) else [],
            "suspects": sus if isinstance(sus, dict) else {},
            "source": {
                "stage02": str(stage02) if stage02.exists() else None,
                "stage03": str(stage03) if stage03.exists() else None,
                "tables": str(tables_f) if tables_f.exists() else None,
                "figures": str(figs_f) if figs_f.exists() else None,
                "suspects": str(suspects_f) if suspects_f.exists() else None,
            },
        }
        (out_dir / "blocks_full.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False))
    except Exception:
        if fail_soft:
            return
        raise

