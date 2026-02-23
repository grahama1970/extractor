#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "nbconvert>=7.16.0",
#   "nbformat>=5.9.0",
#   "jupyter-client>=8.6.0",
#   "ipykernel>=6.29.0",
# ]
# ///
"""
Execute a Jupyter notebook and export HTML, without adding project deps.
Usage:
  uv run scripts/tools/exec_notebook.py <in.ipynb> <out.html>
"""
from __future__ import annotations
import sys
from pathlib import Path
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert import HTMLExporter


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: exec_notebook.py <in.ipynb> <out.html>")
        return 2
    in_path = Path(argv[1])
    out_path = Path(argv[2])
    nb = nbformat.read(in_path.open(), as_version=4)
    ep = ExecutePreprocessor(timeout=900, kernel_name="python3")
    ep.preprocess(nb, {"metadata": {"path": "."}})
    body, _ = HTMLExporter().from_notebook_node(nb)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
