from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

from PIL import Image
import numpy as np


@dataclass
class PreflightReport:
    pages: int
    annotations_removed: int
    rotations_applied: int
    image_dupes: int
    notes: List[str]


def _ensure_rgb(pix: "fitz.Pixmap") -> "fitz.Pixmap":  # type: ignore
    if not pix or pix.n >= 4:
        return pix
    return fitz.Pixmap(pix, 0) if pix.n == 1 else fitz.Pixmap(pix)  # type: ignore


def _phash_image(pix: "fitz.Pixmap", size: int = 32, hash_size: int = 8) -> str:  # type: ignore
    """Compute a simple perceptual hash (DCT based) for a pixmap.
    Returns hex string. Fallbacks to md5 of samples if anything fails.
    """
    try:
        pix = _ensure_rgb(pix)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        a = np.asarray(img, dtype=np.float32)
        # Convert to luma
        if a.ndim == 3 and a.shape[2] == 3:
            a = (0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]).astype(np.float32)
        # 2D DCT
        dct = np.fft.fft2(a)
        dct = np.abs(dct)
        dctlow = dct[:hash_size, :hash_size]
        med = np.median(dctlow)
        diff = dctlow > med
        bits = "".join("1" if x else "0" for x in diff.flatten())
        return f"{int(bits, 2):0{hash_size*hash_size//4}x}"
    except Exception:
        # Conservative fallback
        try:
            return hashlib.md5(pix.samples).hexdigest()
        except Exception:
            return ""


def _dominant_text_angle(page: "fitz.Page") -> Optional[int]:  # type: ignore
    """Estimate dominant text angle (0/90/180/270) using text directions if available."""
    try:
        raw = page.get_text("rawdict")
        dirs: List[float] = []
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    ang = float(span.get("angle", 0.0))
                    dirs.append(ang)
        if not dirs:
            return None
        # Map to nearest right angle
        counts: Dict[int, int] = {0: 0, 90: 0, 180: 0, 270: 0}
        for a in dirs:
            aa = int((round(a / 90.0) * 90) % 360)
            counts[aa] = counts.get(aa, 0) + 1
        best = max(counts.items(), key=lambda kv: kv[1])[0]
        return best if best in (0, 90, 180, 270) else None
    except Exception:
        return None


def strip_annotations_and_normalize(
    pdf_in: Path,
    pdf_out: Path,
    *,
    normalize_rotation: bool = True,
    dedupe_images: bool = True,
    dpi: int = 300,
) -> PreflightReport:
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) not available; install pymupdf")
    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    anns_removed = 0
    rotations = 0
    dupes = 0
    notes: List[str] = []

    with fitz.open(str(pdf_in)) as doc:
        pages = len(doc)
        # Remove annotations
        for pno in range(pages):
            page = doc.load_page(pno)
            try:
                annot = page.first_annot
                while annot is not None:
                    anns_removed += 1
                    next_ann = annot.next
                    page.delete_annot(annot)
                    annot = next_ann
            except Exception:
                pass
            # Optional rotation normalization based on text angle
            if normalize_rotation:
                ang = _dominant_text_angle(page)
                if ang is not None and ang != 0:
                    try:
                        page.set_rotation(ang)
                        rotations += 1
                    except Exception:
                        notes.append(f"rotation_set_failed_page_{pno}")

        # Image de-dup: compute simple hashes and count dupes (no PDF rewrite)
        if dedupe_images:
            try:
                seen: Dict[str, int] = {}
                for pno in range(pages):
                    page = doc.load_page(pno)
                    for info in page.get_images(full=True):
                        xref = info[0]
                        try:
                            pix = fitz.Pixmap(doc, xref)
                            # Render at DPI for stability
                            if pix.alpha:
                                pix = fitz.Pixmap(pix, 0)  # drop alpha
                            h = _phash_image(pix)
                            if not h:
                                continue
                            if h in seen:
                                dupes += 1
                            else:
                                seen[h] = 1
                        except Exception:
                            continue
            except Exception:
                notes.append("image_dedupe_failed")

        # Save cleaned copy
        doc.save(str(pdf_out))

    return PreflightReport(
        pages=pages,
        annotations_removed=anns_removed,
        rotations_applied=rotations,
        image_dupes=dupes,
        notes=notes,
    )
