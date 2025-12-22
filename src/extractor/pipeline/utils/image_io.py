from __future__ import annotations

import base64
from pathlib import Path
from typing import Dict, Optional
from extractor.pipeline.utils.reliability import log_stage_error


def _safe_read_image_b64(path_str: str, base_dir: Path) -> Optional[str]:
    try:

        def _candidates() -> list[Path]:
            raw = Path(path_str)
            c: list[Path] = [raw]
            if not raw.is_absolute():
                c.append(base_dir / raw)
            parts = (base_dir / raw).parts if not raw.is_absolute() else raw.parts
            if parts.count("src") > 1:
                src_idx = parts.index("src")
                trimmed = Path(*parts[src_idx:])
                c.append(trimmed)
                c.append(Path.cwd() / trimmed)
            if "results" in parts:
                idxs = [i for i, p in enumerate(parts) if p == "results"]
                if idxs:
                    last_idx = idxs[-1]
                    rel_after = Path(*parts[last_idx + 1 :])
                    if str(rel_after):
                        c.append(base_dir / rel_after)
            # Dedup
            out, seen = [], set()
            for x in c:
                key = str(x)
                if key not in seen:
                    seen.add(key)
                    out.append(x)
            return out

        from io import BytesIO

        try:
            from PIL import Image  # type: ignore
        except Exception as exc:
            log_stage_error("image_io", exc, {"context": "import_PIL"})
            Image = None  # type: ignore

        for cand in _candidates():
            if cand.exists():
                raw = cand.read_bytes()
                # Try to validate and normalize encoding via PIL
                if Image is not None:
                    try:
                        img = Image.open(BytesIO(raw))
                        buf = BytesIO()
                        # Prefer PNG to preserve diagrams; provider will accept PNG
                        img.save(buf, format="PNG")
                        norm = buf.getvalue()
                        return base64.b64encode(norm).decode("utf-8")
                    except Exception as exc:
                        log_stage_error("image_io", exc, {"context": "PIL_normalize", "candidate": str(cand)})
                # Fallback: return original bytes (may still work if valid)
                return base64.b64encode(raw).decode("utf-8")
        return None
    except Exception as exc:
        log_stage_error("image_io", exc, {"context": "safe_read_image_b64", "path": path_str})
        return None


def get_section_image_b64(section_data: Dict[str, object], base_dir: Path) -> Optional[str]:
    image_path_str = section_data.get("visual_path") or section_data.get("image_path")
    if not image_path_str:
        return None
    return _safe_read_image_b64(str(image_path_str), base_dir)


def get_table_image_b64(table: Dict[str, object], base_dir: Path) -> Optional[str]:
    path = table.get("table_image_path") or table.get("image_path")
    if not path:
        return None
    return _safe_read_image_b64(str(path), base_dir)


def get_figure_image_b64(figure: Dict[str, object], base_dir: Path) -> Optional[str]:
    path = figure.get("image_path")
    if not path:
        return None
    return _safe_read_image_b64(str(path), base_dir)


def get_annotation_image_b64(annot: Dict[str, object], base_dir: Path) -> Optional[str]:
    path = annot.get("image_path")
    if not path:
        return None
    return _safe_read_image_b64(str(path), base_dir)
