#!/usr/bin/env python3
"""
SPARTA Ingest (lightweight)

Walks a SPARTA workspace, reads enriched STIX with local bindings
(sparta_stix_enriched_local.json), and emits chunked JSONL suitable
for retrieval/training. Avoids heavyweight deps; extracts text from
HTML and TXT, skips PDFs by default (can be added later).

Usage:
  PYTHONPATH=src python -m extractor.pipeline.sparta_ingest run \
    --sparta-root /home/graham/workspace/experiments/sparta/sparta_complete \
    --outdir data/author/sparta_chunks --chunk-chars 3000 --overlap 300
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator, Dict, Any
import typer

app = typer.Typer(add_completion=False, help="SPARTA ingest: chunk local refs into JSONL")


def _read_text(path: Path) -> str:
    suf = path.suffix.lower()
    try:
        if suf in {".txt", ".md", ".rst", ".log"}:
            return path.read_text(errors="ignore")
        if suf in {".html", ".htm"}:
            raw = path.read_text(errors="ignore")
            # Naive tag strip; avoids external deps
            import re, html
            text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = html.unescape(text)
            text = re.sub(r"[ \t\r\f\v]+", " ", text)
            return text
        # Skip heavy types for now
        return ""
    except Exception:
        return ""


def _chunk(text: str, chunk_chars: int, overlap: int) -> Iterator[str]:
    if not text:
        return
    n = max(1, chunk_chars)
    o = max(0, min(overlap, n // 2))
    i = 0
    L = len(text)
    while i < L:
        yield text[i : i + n]
        if i + n >= L:
            break
        i = i + n - o


def _iter_local_refs(enriched: Dict[str, Any], root: Path) -> Iterator[Dict[str, Any]]:
    objs = enriched.get("objects", []) if isinstance(enriched, dict) else []
    for o in objs:
        oid = o.get("id") or o.get("name")
        if not oid:
            continue
        for ref in o.get("external_references", []) or []:
            lp = ref.get("source_name_local") or ref.get("local_path")
            if not lp:
                continue
            p = (root / lp).resolve()
            if p.exists() and p.is_file():
                yield {"object_id": oid, "ref": ref, "path": p}


@app.command()
def run(
    sparta_root: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, help="SPARTA root (contains sparta_stix_enriched_local.json)"),
    outdir: Path = typer.Option(Path("data/author/sparta_chunks"), help="Output directory for JSONL chunks"),
    chunk_chars: int = typer.Option(3000, min=500, help="Max characters per chunk"),
    overlap: int = typer.Option(300, min=0, help="Character overlap between chunks"),
    limit: int = typer.Option(0, help="Limit refs (0 = all)"),
):
    enriched = sparta_root / "sparta_stix_enriched_local.json"
    if not enriched.exists():
        # allow original enriched
        enriched = sparta_root / "sparta_stix_enriched.json"
        if not enriched.exists():
            raise typer.BadParameter("Missing enriched STIX JSON in sparta_root")
    data = json.loads(enriched.read_text())
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / "sparta_chunks.jsonl"
    n_written = 0
    with out.open("w", encoding="utf-8") as f:
        for i, rec in enumerate(_iter_local_refs(data, sparta_root)):
            if limit and i >= limit:
                break
            p: Path = rec["path"]
            txt = _read_text(p)
            if not txt:
                continue
            for j, chunk in enumerate(_chunk(txt, chunk_chars, overlap)):
                row = {
                    "object_id": rec["object_id"],
                    "source_path": str(p),
                    "chunk_index": j,
                    "text": chunk,
                    "original_url": rec["ref"].get("original_url") or rec["ref"].get("url"),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_written += 1
    typer.echo(json.dumps({"ok": True, "chunks": n_written, "out": str(out)}, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()

