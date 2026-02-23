#!/usr/bin/env python3
import json
import argparse
import fitz  # PyMuPDF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--rect", required=True, help="normalized x,y,w,h (0..1)")
    ap.add_argument("--zoom", type=float, default=2.0, help="zoom factor for rasterization")
    args = ap.parse_args()

    x, y, w, h = [float(v) for v in args.rect.split(",")]
    doc = fitz.open(args.pdf)
    p = doc[args.page - 1]
    pw, ph = p.rect.width, p.rect.height
    rect = fitz.Rect(x * pw, y * ph, (x + w) * pw, (y + h) * ph)
    mat = fitz.Matrix(args.zoom, args.zoom)
    pm = p.get_pixmap(clip=rect, matrix=mat, alpha=False)
    b = pm.tobytes(output="png")
    # Return as base64-like string (JSON-compatible) using ISO-8859-1 to avoid additional b64; Next can base64-encode if desired.
    # But better to base64 here for browser consumption.
    import base64

    out = {
        "width": pm.width,
        "height": pm.height,
        "zoom": args.zoom,
        "png_base64": base64.b64encode(b).decode("ascii"),
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
