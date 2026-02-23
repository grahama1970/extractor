"""Stage 10 arango exporter runner."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from rich.console import Console

from extractor.pipeline.utils.embeddings import ensure_embedder
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.step_sanity import run_step_sanity

try:  # Optional dependency for live export
    from arango import ArangoClient
    from arango.exceptions import ArangoError
except Exception:  # pragma: no cover - optional dependency
    ArangoClient = None  # type: ignore
    ArangoError = Exception  # type: ignore

try:  # Optional for local invocation
    from dotenv import find_dotenv, load_dotenv
except Exception:  # pragma: no cover - optional dependency
    find_dotenv = None  # type: ignore
    load_dotenv = None  # type: ignore

console = Console(stderr=True)
STEP_NAME = "10_arangodb_exporter"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


def _hash_embedding(text: str, dims: int = 8) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vals = []
    for i in range(0, dims * 4, 4):
        chunk = digest[i : i + 4]
        v = int.from_bytes(chunk, "big", signed=False)
        vals.append((v / (2**32)) * 2.0 - 1.0)
    # Normalize
    norm = sum(v * v for v in vals) ** 0.5
    if norm:
        vals = [v / norm for v in vals]
    return vals


def _embed_text(text: str, *, skip_embeddings: bool, fast_embeddings: bool) -> Optional[List[float]]:
    if skip_embeddings or not text or not text.strip():
        return None
    if fast_embeddings:
        return _hash_embedding(text)
    try:
        embedder = ensure_embedder()
        if embedder is None:
            return None
        vecs = embedder.encode([text], normalize_embeddings=True)
        if hasattr(vecs, "tolist"):
            return vecs[0].tolist()
        return list(vecs[0])
    except Exception as exc:
        log_stage_error("10_arangodb_exporter", exc, {"context": "embedding"})
        return None


def _doc_id_from_source(source_pdf: Optional[str]) -> str:
    basis = source_pdf or "document"
    digest = hashlib.md5(basis.encode("utf-8")).hexdigest()
    return f"doc_{digest}"


def _object_key(doc_id: str, idx: int, object_type: str, section_id: Optional[str]) -> str:
    raw = f"{doc_id}:{idx}:{object_type}:{section_id or ''}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _summary_map(summaries_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    summaries = []
    if isinstance(summaries_data, dict):
        summaries = summaries_data.get("summaries") or []
    elif isinstance(summaries_data, list):
        summaries = summaries_data
    out: Dict[str, Dict[str, Any]] = {}
    for s in summaries:
        if not isinstance(s, dict):
            continue
        sid = s.get("section_id")
        if sid:
            out[str(sid)] = s
    return out


def _section_breadcrumb(section: Dict[str, Any]) -> List[str]:
    for key in ("section_breadcrumbs", "breadcrumbs", "breadcrumb_titles"):
        val = section.get(key)
        if isinstance(val, list) and val:
            return [str(v) for v in val if v]
    meta = section.get("metadata") if isinstance(section.get("metadata"), dict) else {}
    if isinstance(meta, dict):
        bc = meta.get("breadcrumbs") or meta.get("breadcrumb_titles")
        if isinstance(bc, list) and bc:
            return [str(v) for v in bc if v]
    return []


def _flatten_unified_hierarchy(hierarchy: Dict[str, Any]) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []

    def _walk(node: Dict[str, Any], parent_id: Optional[str]) -> None:
        node_id = node.get("id")
        if node_id and node_id != "document-root":
            flat.append(
                {
                    "id": node_id,
                    "title": node.get("title"),
                    "level": node.get("level"),
                    "parent_id": parent_id,
                    "breadcrumb": node.get("breadcrumb") or [],
                }
            )
        for child in node.get("children") or []:
            if isinstance(child, dict):
                _walk(child, node_id)

    if isinstance(hierarchy, dict):
        _walk(hierarchy, None)
    return flat


def flatten_document_to_pdf_objects(
    pipeline_data: Dict[str, Any],
    summaries_data: Dict[str, Any],
    *,
    skip_embeddings: bool = False,
    fast_embeddings: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Flatten reflowed sections or a unified document into pdf_objects entries."""
    sections_flat: List[Dict[str, Any]] = []
    pdf_objects: List[Dict[str, Any]] = []
    summaries_by_id = _summary_map(summaries_data)

    source_files = pipeline_data.get("source_files") if isinstance(pipeline_data, dict) else {}
    fallback_source = None
    if isinstance(source_files, dict):
        fallback_source = source_files.get("sections") or source_files.get("source_pdf")

    reflowed_sections = pipeline_data.get("reflowed_sections") or []
    if isinstance(reflowed_sections, list) and reflowed_sections:
        sources = [
            s.get("source_pdf")
            for s in reflowed_sections
            if isinstance(s, dict) and s.get("source_pdf")
        ]
        source_pdf = None
        if sources:
            source_pdf = Counter(sources).most_common(1)[0][0]
        source_pdf = source_pdf or fallback_source
        doc_id = _doc_id_from_source(source_pdf)

        object_idx = 0
        for section in reflowed_sections:
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id") or f"sec_{object_idx}")
            title = section.get("title") or "Untitled"
            level = section.get("level") or 0
            page_start = section.get("page_start")
            page_end = section.get("page_end")
            breadcrumb = _section_breadcrumb(section)
            sections_flat.append(
                {
                    "id": section_id,
                    "title": title,
                    "level": level,
                    "page_start": page_start,
                    "page_end": page_end,
                    "parent_id": section.get("parent_id"),
                    "breadcrumb": breadcrumb,
                    "section_number": section.get("section_number"),
                }
            )

            summary = summaries_by_id.get(section_id, {})
            summary_data = summary.get("summary_data") if isinstance(summary, dict) else {}
            rtm_base = {
                "section_id": section_id,
                "section_title": title,
                "section_level": level,
                "breadcrumb": breadcrumb,
                "evidence": {"page_start": page_start, "page_end": page_end},
            }
            if isinstance(summary_data, dict):
                if summary_data.get("summary"):
                    rtm_base["summary"] = summary_data.get("summary")
                if summary_data.get("key_concepts"):
                    rtm_base["key_concepts"] = summary_data.get("key_concepts")

            text_content = (
                section.get("reflowed_text")
                or section.get("merged_text")
                or section.get("raw_text")
                or ""
            )
            if isinstance(text_content, str) and text_content.strip():
                embedding = _embed_text(
                    text_content, skip_embeddings=skip_embeddings, fast_embeddings=fast_embeddings
                )
                pdf_objects.append(
                    {
                        "_key": _object_key(doc_id, object_idx, "Text", section_id),
                        "doc_id": doc_id,
                        "source_pdf": source_pdf,
                        "object_index_in_doc": object_idx,
                        "object_type": "Text",
                        "text_content": text_content,
                        "section_id": section_id,
                        "section_title": title,
                        "section_level": level,
                        "page_num": page_start,
                        "data": {"type": "text", "section_id": section_id},
                        "embedding": embedding,
                        "rtm": dict(rtm_base),
                    }
                )
                object_idx += 1

            for table in section.get("tables") or []:
                if not isinstance(table, dict):
                    continue
                caption = (
                    table.get("title")
                    or table.get("llm_title")
                    or table.get("caption")
                    or "Untitled"
                )
                desc = table.get("llm_description") or table.get("description") or ""
                header = table.get("header_norm") or table.get("header") or ""
                parts = [f"Table: {caption}"]
                if desc:
                    parts.append(str(desc))
                if header:
                    parts.append(f"Header: {header}")
                table_text = "\n".join(parts)
                embedding = _embed_text(
                    table_text, skip_embeddings=skip_embeddings, fast_embeddings=fast_embeddings
                )
                page_num = table.get("page") or table.get("page_num") or page_start
                pdf_objects.append(
                    {
                        "_key": _object_key(doc_id, object_idx, "Table", section_id),
                        "doc_id": doc_id,
                        "source_pdf": source_pdf,
                        "object_index_in_doc": object_idx,
                        "object_type": "Table",
                        "text_content": table_text,
                        "section_id": section_id,
                        "section_title": title,
                        "section_level": level,
                        "page_num": page_num,
                        "data": {"type": "table", **table},
                        "embedding": embedding,
                        "rtm": dict(rtm_base),
                    }
                )
                object_idx += 1

            for figure in section.get("figures") or []:
                if not isinstance(figure, dict):
                    continue
                caption = (
                    figure.get("caption")
                    or figure.get("title")
                    or figure.get("llm_title")
                    or "Untitled"
                )
                desc = figure.get("llm_description") or figure.get("description") or ""
                parts = [f"Figure: {caption}"]
                if desc:
                    parts.append(str(desc))
                fig_text = "\n".join(parts)
                embedding = _embed_text(
                    fig_text, skip_embeddings=skip_embeddings, fast_embeddings=fast_embeddings
                )
                page_num = figure.get("page") or figure.get("page_num") or page_start
                pdf_objects.append(
                    {
                        "_key": _object_key(doc_id, object_idx, "Figure", section_id),
                        "doc_id": doc_id,
                        "source_pdf": source_pdf,
                        "object_index_in_doc": object_idx,
                        "object_type": "Figure",
                        "text_content": fig_text,
                        "section_id": section_id,
                        "section_title": title,
                        "section_level": level,
                        "page_num": page_num,
                        "data": {"type": "figure", **figure},
                        "embedding": embedding,
                        "rtm": dict(rtm_base),
                    }
                )
                object_idx += 1

        return pdf_objects, sections_flat

    unified = pipeline_data.get("unified_document") if isinstance(pipeline_data, dict) else None
    if isinstance(unified, dict):
        source_pdf = unified.get("source_path") or fallback_source
        doc_id = unified.get("id") if isinstance(unified.get("id"), str) else _doc_id_from_source(
            source_pdf
        )
        hierarchy = unified.get("hierarchy")
        if isinstance(hierarchy, dict):
            sections_flat = _flatten_unified_hierarchy(hierarchy)

        object_idx = 0
        for block in unified.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            btype = str(block.get("type") or "text").lower()
            object_type = "Text"
            if btype in {"table"}:
                object_type = "Table"
            elif btype in {"figure", "image"}:
                object_type = "Figure"
            content = block.get("content")
            text_content = content if isinstance(content, str) else json.dumps(content)
            metadata = block.get("metadata") if isinstance(block.get("metadata"), dict) else {}
            attrs = metadata.get("attributes") if isinstance(metadata.get("attributes"), dict) else {}
            section_id = attrs.get("section_id") or block.get("parent_id")
            page_num = metadata.get("page_number")
            breadcrumb = []
            if section_id and sections_flat:
                for s in sections_flat:
                    if s.get("id") == section_id:
                        breadcrumb = s.get("breadcrumb") or []
                        break
            embedding = _embed_text(
                text_content, skip_embeddings=skip_embeddings, fast_embeddings=fast_embeddings
            )
            pdf_objects.append(
                {
                    "_key": _object_key(doc_id, object_idx, object_type, section_id),
                    "doc_id": doc_id,
                    "source_pdf": source_pdf,
                    "object_index_in_doc": object_idx,
                    "object_type": object_type,
                    "text_content": text_content,
                    "section_id": section_id,
                    "section_title": attrs.get("section_title"),
                    "section_level": attrs.get("section_level"),
                    "page_num": page_num,
                    "data": {"type": btype, "block_id": block.get("id"), **attrs},
                    "embedding": embedding,
                    "rtm": {
                        "section_id": section_id,
                        "breadcrumb": breadcrumb,
                        "evidence": {"page_start": page_num, "page_end": page_num},
                    },
                }
            )
            object_idx += 1

        return pdf_objects, sections_flat

    return [], []


def setup_arango_collection(db, collection_name: str) -> None:
    """Create collection + indexes if missing (safe to re-run)."""
    if not db.has_collection(collection_name):
        db.create_collection(collection_name)
    collection = db.collection(collection_name)
    try:
        collection.add_persistent_index(
            fields=["doc_id", "section_id", "object_index_in_doc", "object_type"],
            unique=False,
            sparse=True,
        )
    except Exception:
        pass
    try:
        collection.add_fulltext_index(fields=["text_content"], min_length=3)
    except Exception:
        pass


def run(
    reflowed_json: Path,
    summaries_json: Path,
    output_dir: Path = Path("data/results/pipeline"),
    collection_name: str = "pdf_objects",
    skip_export: bool = False,
    skip_embeddings: bool = False,
    fast_embeddings: bool = False,
) -> Optional[Path]:
    """
    Flattens the processed document and loads it into ArangoDB.
    """
    console.print("[bold green]Starting ArangoDB Export (Stage 10)[/bold green]")

    stage_output_dir = Path(output_dir).resolve() / "10_arangodb_exporter"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    with open(reflowed_json, "r") as f:
        reflowed_data = json.load(f)
    with open(summaries_json, "r") as f:
        summaries_data = json.load(f)

    pdf_objects_to_load, sections_flat = flatten_document_to_pdf_objects(
        reflowed_data,
        summaries_data,
        skip_embeddings=skip_embeddings,
        fast_embeddings=fast_embeddings,
    )
    if not pdf_objects_to_load:
        console.print("[yellow]No objects to load. Exiting.[/yellow]")
        return None

    # Enrich RTM with Lean4 status when Stage 08 theorems are present
    try:
        theorems_path = output_dir / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"
        if theorems_path.exists():
            tdata = json.loads(theorems_path.read_text(encoding="utf-8"))
            proofs = tdata.get("proof_results") if isinstance(tdata, dict) else None
            sec_stats = {}
            sec_analysis: Dict[str, Dict[str, Any]] = {}
            if isinstance(proofs, list):
                for pr in proofs:
                    item = pr.get("item") if isinstance(pr, dict) else {}
                    src = item.get("source_details", {}) if isinstance(item, dict) else {}
                    sec_id = src.get("section_id")
                    if not sec_id:
                        continue
                    st = sec_stats.setdefault(sec_id, {"total": 0, "ok": 0})
                    st["total"] += 1
                    # 'status' is preferred; 'success' maintained for backward-compat
                    status = pr.get("status")
                    if (status is None and pr.get("success")) or str(status).lower() in {
                        "ok",
                        "proved",
                        "success",
                        "true",
                    }:
                        st["ok"] += 1
                    # Capture last seen analysis per section (best-effort)
                    ana = pr.get("analysis") if isinstance(pr, dict) else None
                    if isinstance(ana, dict):
                        sec_analysis[sec_id] = {
                            "lean4_norm": ana.get("normalized_prop"),
                            "lean4_polarity": ana.get("polarity"),
                            "lean4_shape": ana.get("shape"),
                        }
            for obj in pdf_objects_to_load:
                if not isinstance(obj, dict):
                    continue
                rtm = obj.get("rtm") if isinstance(obj.get("rtm"), dict) else None
                if not rtm:
                    continue
                sec_id = rtm.get("section_id")
                st = sec_stats.get(sec_id) if sec_id else None
                if not st:
                    continue
                rtm["lean4_status"] = "proved" if st["ok"] > 0 else "unproved"
                # Additive: pass through normalized proposition metadata when available
                ana = sec_analysis.get(sec_id)
                if ana:
                    rtm.update(ana)
    except Exception as exc:
        log_stage_error("10_arangodb_exporter", exc, {"context": "10"})
        raise

    # Always materialize flattened JSON for downstream stages (Stage 11 and tooling)
    try:
        flat_path = json_output_dir / "10_flattened_data.json"
        with open(flat_path, "w") as f:
            json.dump(pdf_objects_to_load, f, indent=2)
        logger.info(f"Wrote flattened data for Stage 11 to: {flat_path}")
    except Exception as exc:
        log_stage_error("10_arangodb_exporter", exc, {"context": "10"})
        raise

    # Sections export (flattened hierarchy)
    try:
        sections_path = json_output_dir / "10_sections.json"
        with open(sections_path, "w") as f:
            json.dump(sections_flat, f, indent=2)
        logger.info(f"Wrote flattened sections to: {sections_path}")
    except Exception as exc:
        log_stage_error("10_arangodb_exporter", exc, {"context": "10_sections"})
        raise

    if skip_export:
        console.print(
            "[yellow]--skip-export flag is set. Skipping ArangoDB export (flattened JSON already saved).[/yellow]"
        )
        return flat_path

    try:
        host = os.getenv("ARANGO_HOST", "localhost")
        port = int(os.getenv("ARANGO_PORT", 8529))
        user = os.getenv("ARANGO_USERNAME") or os.getenv("ARANGO_USER", "root")
        password = os.getenv("ARANGO_PASS") or os.getenv("ARANGO_PASSWORD")
        db_name = os.getenv("ARANGO_DB") or os.getenv("ARANGO_DATABASE", "pdf_knowledge_base")

        if not password or ArangoClient is None:
            console.print(
                "[yellow]Arango not configured/available → export skipped; flattened JSON already saved.[/yellow]"
            )
            return flat_path

        client = ArangoClient(hosts=f"http://{host}:{port}")
        db = client.db(db_name, username=user, password=password)
        db.version()
        logger.success(f"Connected to ArangoDB database '{db_name}'.")
    except (ArangoError, ValueError) as e:
        console.print(
            f"[yellow]Arango connection failed → export skipped ({e}); flattened JSON already saved.[/yellow]"
        )
        return flat_path

    setup_arango_collection(db, collection_name)

    try:
        collection = db.collection(collection_name)
        result = collection.import_bulk(pdf_objects_to_load, on_duplicate="replace")

        confirmation = {
            "timestamp": datetime.now().isoformat(),
            "status": "Completed",
            "documents_created": result["created"],
            "documents_updated": result["updated"],
            "errors": result["errors"],
        }
        output_path = json_output_dir / "10_export_confirmation.json"
        with open(output_path, "w") as f:
            json.dump(confirmation, f, indent=2)

        console.print("\n[bold green]✅ ArangoDB export complete.[/bold green]")
        console.print(f"   - Confirmation saved to: [cyan]{output_path}[/cyan]")
        return output_path

    except ArangoError as e:
        console.print(
            f"[yellow]Bulk import failed → export skipped ({e}); flattened JSON present.[/yellow]"
        )
        return flat_path


def debug_bundle(
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
    skip_export: bool = True,
    collection_name: str = "pdf_objects",
    skip_embeddings: bool = True,
    fast_embeddings: bool = False,
):
    """Run Stage 10 directly from a consolidated JSON bundle.

    The bundle should include either of:
      - unified_document: canonical structure (preferred)
      - reflowed_sections: list of sections (legacy PDF pipeline)

    Summaries are optional (pass under the ``summaries`` key).
    """
    stage_output_dir = output_dir / "10_arangodb_exporter"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    output_path: Path | None = None

    try:
        data = json.loads(bundle.read_text())
        if not isinstance(data, dict):
            raise ValueError("Bundle root must be an object")
        has_unified = isinstance(data.get("unified_document"), dict)
        has_reflow = isinstance(data.get("reflowed_sections"), list) and data.get(
            "reflowed_sections"
        )
        if not (has_unified or has_reflow):
            raise ValueError(
                "Bundle must include 'unified_document' or non-empty 'reflowed_sections'"
            )
    except Exception as exc:
        log_stage_error("10_arangodb_exporter", exc, {"context": "10"})
        raise

    reflowed_data = data  # treat the bundle itself as the reflowed payload
    summaries_data = {"summaries": data.get("summaries") or []}

    pdf_objects_to_load, _sections_flat = flatten_document_to_pdf_objects(
        reflowed_data,
        summaries_data,
        skip_embeddings=skip_embeddings,
        fast_embeddings=fast_embeddings,
    )
    if not pdf_objects_to_load:
        console.print("[yellow]No objects to flatten from bundle. Exiting.[/yellow]")
        return None

    if skip_export:
        output_path = json_output_dir / "10_flattened_data.json"
        output_path.write_text(json.dumps(pdf_objects_to_load, indent=2))
        console.print(
            f"[green]Debug bundle: saved {len(pdf_objects_to_load)} flattened objects to {output_path}"
        )
        return output_path

    # Optional export path (rare for debug-bundle)
    try:
        host = os.getenv("ARANGO_HOST", "localhost")
        port = int(os.getenv("ARANGO_PORT", 8529))
        user = os.getenv("ARANGO_USERNAME") or os.getenv("ARANGO_USER", "root")
        password = os.getenv("ARANGO_PASS") or os.getenv("ARANGO_PASSWORD")
        db_name = os.getenv("ARANGO_DB") or os.getenv("ARANGO_DATABASE", "pdf_knowledge_base")

        if not password or ArangoClient is None:
            console.print(
                "[yellow]Arango not configured/available → export skipped; flattened JSON written.[/yellow]"
            )
            output_path = json_output_dir / "10_flattened_data.json"
            output_path.write_text(json.dumps(pdf_objects_to_load, indent=2))
            return output_path

        client = ArangoClient(hosts=f"http://{host}:{port}")
        db = client.db(db_name, username=user, password=password)
        db.version()
        logger.success(f"Connected to ArangoDB database '{db_name}'.")
    except (ArangoError, ValueError) as e:
        console.print(
            f"[yellow]Arango connection failed → export skipped ({e}); flattened JSON written.[/yellow]"
        )
        output_path = json_output_dir / "10_flattened_data.json"
        output_path.write_text(json.dumps(pdf_objects_to_load, indent=2))
        return output_path

    setup_arango_collection(db, collection_name)
    try:
        collection = db.collection(collection_name)
        result = collection.import_bulk(pdf_objects_to_load, on_duplicate="replace")

        confirmation = {
            "timestamp": datetime.now().isoformat(),
            "status": "Completed",
            "documents_created": result["created"],
            "documents_updated": result["updated"],
            "errors": result["errors"],
        }
        output_path = json_output_dir / "10_export_confirmation.json"
        output_path.write_text(json.dumps(confirmation, indent=2))
        console.print(f"[green]Debug bundle: export complete. Confirmation saved to {output_path}")
        return output_path
    except ArangoError as e:
        console.print(
            f"[yellow]Bulk import failed → export skipped ({e}); flattened JSON available.[/yellow]"
        )
        output_path = json_output_dir / "10_flattened_data.json"
        output_path.write_text(json.dumps(pdf_objects_to_load, indent=2))
        return output_path

    # Fallback: if no explicit return occurred, provide the confirmation path if present.
    if output_path is None:
        confirmation = json_output_dir / "10_export_confirmation.json"
        flattened = json_output_dir / "10_flattened_data.json"
        if confirmation.exists():
            return confirmation
        if flattened.exists():
            return flattened
    return output_path


# Minimal __main__ for convenience: import-safe, tiny, and optional.
if __name__ == "__main__":
    # Load .env only for direct invocation
    try:
        if load_dotenv is not None and find_dotenv is not None:
            load_dotenv(find_dotenv(), override=True)
    except Exception as exc:
        log_stage_error("10_arangodb_exporter", exc, {"context": "10"})
        raise
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        sys.exit(sanity())
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.10_arangodb_exporter REFLOWED_JSON SUMMARIES_JSON [OUT_DIR]\n"
            "       Set SKIP_EXPORT=1 to avoid DB writes.\n",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        reflowed = Path(argv[0])
        summaries = Path(argv[1])
    except IndexError:
        print("Missing arguments. See --help.", file=sys.stderr)
        sys.exit(2)
    out_dir = Path(argv[2]) if len(argv) > 2 else Path("data/results/pipeline")

    skip_export = os.getenv("SKIP_EXPORT", "0").lower() in {"1", "true", "yes"}
    collection = os.getenv("ARANGO_COLLECTION", "pdf_objects")
    try:
        run(
            reflowed_json=reflowed,
            summaries_json=summaries,
            output_dir=out_dir,
            collection_name=collection,
            skip_export=skip_export,
            skip_embeddings=False,
            fast_embeddings=False,
        )
    except Exception as exc:
        log_stage_error("10_arangodb_exporter", exc, {"context": "10"})
        raise
        logger.error(f"Stage 10 failed: {exc}")
        sys.exit(1)
