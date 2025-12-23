"""Stage 10 arango exporter runner."""
import json, os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error
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
                    if (status is None and pr.get("success")) or str(status).lower() in {"ok", "proved", "success", "true"}:
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
        log_stage_error('10_arangodb_exporter', exc, {'context': '10'})
        raise
        logger.warning(f"RTM lean4_status enrichment failed: {e}")

    # Always materialize flattened JSON for downstream stages (Stage 11 and tooling)
    try:
        flat_path = json_output_dir / "10_flattened_data.json"
        with open(flat_path, "w") as f:
            json.dump(pdf_objects_to_load, f, indent=2)
        logger.info(f"Wrote flattened data for Stage 11 to: {flat_path}")
    except Exception as exc:
        log_stage_error('10_arangodb_exporter', exc, {'context': '10'})
        raise
        logger.warning(f"Failed to write flattened JSON (continuing): {e}")

    # Sections export (flattened hierarchy)
    try:
        sections_path = json_output_dir / "10_sections.json"
        validated_sections = [SectionRecord.model_validate(s) if not isinstance(s, SectionRecord) else s for s in sections_flat]
        with open(sections_path, "w") as f:
            json.dump([s.model_dump(mode="json") for s in validated_sections], f, indent=2)
        logger.info(f"Wrote flattened sections to: {sections_path}")
    except ValidationError as exc:
        log_stage_error('10_arangodb_exporter', exc, {'context': '10_sections_validation'})
        raise
    except Exception as exc:
        log_stage_error('10_arangodb_exporter', exc, {'context': '10_sections'})
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
            console.print("[yellow]Arango not configured/available → export skipped; flattened JSON already saved.[/yellow]")
            return flat_path

        client = ArangoClient(hosts=f"http://{host}:{port}")
        db = client.db(db_name, username=user, password=password)
        db.version()
        logger.success(f"Connected to ArangoDB database '{db_name}'.")
    except (ArangoError, ValueError) as e:
        console.print(f"[yellow]Arango connection failed → export skipped ({e}); flattened JSON already saved.[/yellow]")
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
        console.print(f"[yellow]Bulk import failed → export skipped ({e}); flattened JSON present.[/yellow]")
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
        log_stage_error('10_arangodb_exporter', exc, {'context': '10'})
        raise
        raise ValueError(f"Failed to load bundle: {e}")

    reflowed_data = data  # treat the bundle itself as the reflowed payload
    summaries_data = {"summaries": data.get("summaries") or []}

    pdf_objects_to_load = flatten_document_to_pdf_objects(
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
            console.print("[yellow]Arango not configured/available → export skipped; flattened JSON written.[/yellow]")
            output_path = json_output_dir / "10_flattened_data.json"
            output_path.write_text(json.dumps(pdf_objects_to_load, indent=2))
            return output_path

        client = ArangoClient(hosts=f"http://{host}:{port}")
        db = client.db(db_name, username=user, password=password)
        db.version()
        logger.success(f"Connected to ArangoDB database '{db_name}'.")
    except (ArangoError, ValueError) as e:
        console.print(f"[yellow]Arango connection failed → export skipped ({e}); flattened JSON written.[/yellow]")
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
        console.print(f"[yellow]Bulk import failed → export skipped ({e}); flattened JSON available.[/yellow]")
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
        load_dotenv(find_dotenv(), override=True)
    except Exception as exc:
        log_stage_error('10_arangodb_exporter', exc, {'context': '10'})
        raise
        pass
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

    skip_export = (os.getenv("SKIP_EXPORT", "0").lower() in {"1", "true", "yes"})
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
        log_stage_error('10_arangodb_exporter', exc, {'context': '10'})
        raise
        logger.error(f"Stage 10 failed: {e}")
        sys.exit(1)
