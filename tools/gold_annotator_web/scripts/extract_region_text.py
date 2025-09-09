#!/usr/bin/env python3
import json
import argparse
import fitz  # PyMuPDF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--page', type=int, default=1)
    ap.add_argument('--rect', required=True, help='normalized x,y,w,h (0..1)')
    args = ap.parse_args()

    x, y, w, h = [float(v) for v in args.rect.split(',')]
    doc = fitz.open(args.pdf)
    p = doc[args.page - 1]
    pw, ph = p.rect.width, p.rect.height
    rect = fitz.Rect(x * pw, y * ph, (x + w) * pw, (y + h) * ph)
    text = p.get_text("text", clip=rect) or ""

    out = {"text": text}
    print(json.dumps(out))


if __name__ == '__main__':
    main()

