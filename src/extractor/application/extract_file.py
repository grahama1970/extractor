"""Canonical one-file extraction facade."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from extractor.core.providers.registry import provider_from_filepath, supports_filepath
from extractor.core.schema.extraction_result import (
    ArtifactRef,
    ExtractionCounts,
    ExtractionDiagnostics,
    ExtractionResult,
    ExtractionStatus,
    NeedsAttention,
)
from extractor.core.schema.unified_document import (
    BaseBlock,
    BlockMetadata,
    BlockType,
    DocumentMetadata,
    SourceType,
    UnifiedDocument,
)
from extractor.application.status import validate_required_artifacts


PDF_OXIDE_PIN = "5b0538cb94f8c27b3f3f33411b4a9267dc98a022"


@dataclass
class ExtractedPayload:
    """Provider output plus normalized facade metadata."""

    unified: UnifiedDocument
    artifacts: list[ArtifactRef] = field(default_factory=list)
    provider: str | None = None
    engine: str | None = None
    diagnostics_extra: dict[str, object] = field(default_factory=dict)


class PdfOxideUnavailable(RuntimeError):
    """Raised when the canonical PDF engine is unavailable or incompatible."""


def extract_file(
    path: str | Path,
    *,
    output_dir: str | Path | None = None,
    offline: bool = False,
) -> ExtractionResult:
    """Extract one supported file and return an `extractor.result.v1` envelope."""

    started = time.monotonic()
    source = Path(path).expanduser()
    if not source.exists() or not source.is_file():
        return _terminal_result(
            source=source,
            source_sha256="",
            detected_format="unknown",
            output_dir=Path(output_dir or Path.cwd()),
            status=ExtractionStatus.BLOCKED,
            route="input_validation",
            needs_attention=[
                NeedsAttention(
                    code="source_missing",
                    message=f"Input file does not exist: {source}",
                    action="Provide an existing readable file path.",
                )
            ],
            started=started,
        )

    source = source.resolve()
    source_sha256 = _sha256(source)
    detected_format = _detect_supported_format(source)
    run_dir = Path(output_dir) if output_dir is not None else Path.cwd() / f"{source.stem}_extract"
    run_dir = run_dir.expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    if detected_format == "unsupported":
        return _terminal_result(
            source=source,
            source_sha256=source_sha256,
            detected_format=detected_format,
            output_dir=run_dir,
            status=ExtractionStatus.BLOCKED,
            route="unsupported_format",
            needs_attention=[
                NeedsAttention(
                    code="unsupported_format",
                    message=f"Unsupported input type for {source.name}",
                    action="Provide a supported document, data, image, or text format.",
                )
            ],
            started=started,
        )

    try:
        payload = _extract_unified(source, detected_format, run_dir=run_dir, offline=offline)
    except Exception as exc:
        return _failure_result(
            source=source,
            source_sha256=source_sha256,
            detected_format=detected_format,
            output_dir=run_dir,
            error=exc,
            started=started,
        )

    artifact = _write_unified_artifact(payload.unified, run_dir)
    counts = _counts_from_unified(payload.unified)
    result = ExtractionResult(
        status=ExtractionStatus.COMPLETE,
        source_path=str(source),
        source_sha256=source_sha256,
        detected_format=detected_format,
        output_dir=str(run_dir),
        counts=counts,
        artifacts=[artifact, *payload.artifacts],
        diagnostics=ExtractionDiagnostics(
            route="provider_registry",
            provider=payload.provider or provider_from_filepath(str(source)).__name__,
            engine=payload.engine or "native_provider",
            timings_ms={"total": int((time.monotonic() - started) * 1000)},
            extra={"offline": offline, **payload.diagnostics_extra},
        ),
    )
    result = validate_required_artifacts(result)
    result.write_json(run_dir / "extractor_result.json")
    return result


def _detect_supported_format(source: Path) -> str:
    ext = source.suffix.lower().lstrip(".")
    if supports_filepath(str(source)):
        return _canonical_format(ext)

    try:
        head = source.read_text(encoding="utf-8", errors="ignore")[:2048].strip()
    except Exception:
        return "unsupported"

    lower = head.lower()
    if lower.startswith("<!doctype html") or "<html" in lower:
        return "html"
    if head.startswith("{") or head.startswith("["):
        return "json"
    if lower.startswith("<?xml") or lower.startswith("<"):
        return "xml"
    return "unsupported"


def _canonical_format(ext: str) -> str:
    if ext in {"htm"}:
        return "html"
    if ext in {"markdown"}:
        return "md"
    if ext in {"text", "log", "c", "h", "cpp", "py", "java"}:
        return "txt"
    if ext in {"xls", "xlsm", "ods", "csv", "tsv"}:
        return "xlsx"
    if ext in {"jpg", "jpeg", "gif", "bmp", "tiff", "svg", "webp"}:
        return "image"
    return ext or "unknown"


def _extract_unified(
    source: Path,
    detected_format: str,
    *,
    run_dir: Path,
    offline: bool,
) -> ExtractedPayload:
    if detected_format == "pdf":
        return _extract_pdf_oxide(source, run_dir=run_dir)

    provider_cls = provider_from_filepath(str(source))
    try:
        provider = provider_cls()
    except TypeError:
        provider = provider_cls(str(source))
    unified = provider.extract_document(str(source))
    if hasattr(unified, "model_dump"):
        return ExtractedPayload(
            unified=unified,
            provider=provider_cls.__name__,
            engine="native_provider",
            diagnostics_extra={"offline": offline},
        )
    return ExtractedPayload(
        unified=UnifiedDocument(
            id=source.stem,
            source_type=_source_type_for(detected_format),
            source_path=str(source),
            blocks=[
                BaseBlock(
                    id="raw-0",
                    type=BlockType.PARAGRAPH,
                    content=json.dumps(unified, default=str) if not isinstance(unified, str) else unified,
                )
            ],
            metadata=DocumentMetadata(file_hash=_sha256(source), page_count=1),
        ),
        provider=provider_cls.__name__,
        engine="native_provider",
        diagnostics_extra={"offline": offline},
    )


def _extract_pdf_oxide(source: Path, *, run_dir: Path) -> ExtractedPayload:
    try:
        import pdf_oxide
        from pdf_oxide import PipelineConfig
    except Exception as exc:  # pragma: no cover - exercised in dependency-boundary tests
        raise PdfOxideUnavailable(
            "pdf_oxide is not importable; install the pinned pdf_oxide dependency."
        ) from exc

    config = PipelineConfig(sync_to_arango=False, features=[])
    result = pdf_oxide.extract_pdf(str(source), config)
    raw_artifact = _write_json_artifact(
        result.to_dict(),
        run_dir / "artifacts" / "pdf_oxide.json",
        kind="pdf_oxide_result",
    )

    blocks: list[BaseBlock] = []
    for index, block in enumerate(result.blocks):
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        blocks.append(
            BaseBlock(
                id=str(block.get("id") or f"pdf-oxide-block-{index + 1}"),
                type=_block_type_from_pdf_oxide(block.get("type")),
                content=text,
                metadata=BlockMetadata(
                    page_number=int(block.get("page", 0)) + 1,
                    bbox=_bbox_from_pdf_oxide(block.get("bbox")),
                    attributes={
                        "font_size": block.get("font_size"),
                        "is_bold": block.get("is_bold"),
                        "header_level": block.get("header_level"),
                        "section_id": block.get("section_id"),
                    },
                ),
            )
        )

    for index, table in enumerate(result.tables):
        blocks.append(
            BaseBlock(
                id=str(table.get("id") or f"pdf-oxide-table-{index + 1}"),
                type=BlockType.TABLE,
                content=table.get("data", []),
                metadata=BlockMetadata(
                    page_number=int(table.get("page", 0)) + 1,
                    bbox=_bbox_from_pdf_oxide(table.get("bbox")),
                    attributes={
                        "rows": table.get("rows"),
                        "cols": table.get("cols"),
                        "accuracy": table.get("accuracy"),
                        "flavor": table.get("flavor"),
                        "section_id": table.get("section_id"),
                        "extraction_method": table.get("extraction_method"),
                    },
                ),
            )
        )

    for index, figure in enumerate(result.figures):
        blocks.append(
            BaseBlock(
                id=str(figure.get("id") or f"pdf-oxide-figure-{index + 1}"),
                type=BlockType.FIGURE,
                content=figure,
                metadata=BlockMetadata(
                    page_number=int(figure.get("page", 0)) + 1,
                    bbox=_bbox_from_pdf_oxide(figure.get("bbox")),
                    attributes={"extraction_method": "pdf_oxide"},
                ),
            )
        )

    metadata = dict(result.metadata)
    metadata["pdf_oxide"] = {
        "version": getattr(pdf_oxide, "__version__", None),
        "dependency_pin": PDF_OXIDE_PIN,
        "raw_artifact": raw_artifact.path,
        "raw_artifact_sha256": raw_artifact.sha256,
    }

    return ExtractedPayload(
        unified=UnifiedDocument(
            id=source.stem,
            source_type=SourceType.PDF,
            source_path=str(source),
            blocks=blocks,
            metadata=DocumentMetadata(
                title=source.stem,
                file_hash=_sha256(source),
                page_count=result.page_count,
                extraction_method="pdf_oxide",
                format_metadata=metadata,
            ),
        ),
        artifacts=[raw_artifact],
        provider="PdfProvider",
        engine="pdf_oxide",
        diagnostics_extra={
            "pdf_oxide_version": getattr(pdf_oxide, "__version__", None),
            "pdf_oxide_dependency_pin": PDF_OXIDE_PIN,
            "pdf_oxide_output_sha256": raw_artifact.sha256,
            "pdf_oxide_timings": dict(result.timings),
        },
    )


def _block_type_from_pdf_oxide(raw_type: object) -> BlockType:
    value = str(raw_type or "").lower()
    if value in {"title", "heading", "header", "sectionheader"}:
        return BlockType.HEADING
    if value == "table":
        return BlockType.TABLE
    if value in {"figure", "image", "picture"}:
        return BlockType.FIGURE
    return BlockType.PARAGRAPH


def _bbox_from_pdf_oxide(raw_bbox: object) -> list[float] | None:
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return None
    return [float(value) for value in raw_bbox]


def _write_json_artifact(payload: object, path: Path, *, kind: str) -> ArtifactRef:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    data = path.read_bytes()
    return ArtifactRef(
        kind=kind,
        path=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def _source_type_for(detected_format: str) -> SourceType:
    mapping = {
        "docx": SourceType.DOCX,
        "html": SourceType.HTML,
        "md": SourceType.MD,
        "json": SourceType.JSON,
        "xml": SourceType.XML,
        "txt": SourceType.TXT,
        "xlsx": SourceType.XLSX,
        "pptx": SourceType.PPTX,
        "epub": SourceType.EPUB,
        "image": SourceType.IMAGE,
        "pdf": SourceType.PDF,
    }
    return mapping.get(detected_format, SourceType.UNKNOWN)


def _write_unified_artifact(unified: UnifiedDocument, run_dir: Path) -> ArtifactRef:
    path = run_dir / "artifacts" / "unified_document.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unified.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
    data = path.read_bytes()
    return ArtifactRef(
        kind="unified_document",
        path=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def _counts_from_unified(unified: UnifiedDocument) -> ExtractionCounts:
    tables = 0
    figures = 0
    for block in unified.blocks:
        block_type = getattr(block, "type", "")
        value = getattr(block_type, "value", block_type)
        if str(value).lower() == "table":
            tables += 1
        if str(value).lower() in {"figure", "image"}:
            figures += 1
    page_count = getattr(unified.metadata, "page_count", None)
    return ExtractionCounts(
        blocks=len(unified.blocks),
        pages=page_count,
        tables=tables,
        figures=figures,
    )


def _failure_result(
    *,
    source: Path,
    source_sha256: str,
    detected_format: str,
    output_dir: Path,
    error: Exception,
    started: float,
) -> ExtractionResult:
    message = str(error)
    lowered = message.lower()
    status = ExtractionStatus.FAILED
    needs_attention: list[NeedsAttention] = []
    if "password" in lowered or "encrypted" in lowered:
        status = ExtractionStatus.BLOCKED
        needs_attention.append(
            NeedsAttention(
                code="password_required",
                message="The input appears to require a password or decryption key.",
                action="Provide an unlocked source file or a supported password workflow.",
            )
        )
    result = _terminal_result(
        source=source,
        source_sha256=source_sha256,
        detected_format=detected_format,
        output_dir=output_dir,
        status=status,
        route="provider_registry",
        needs_attention=needs_attention,
        messages=[f"{type(error).__name__}: {message}"],
        started=started,
    )
    result.write_json(output_dir / "extractor_result.json")
    return result


def _terminal_result(
    *,
    source: Path,
    source_sha256: str,
    detected_format: str,
    output_dir: Path,
    status: ExtractionStatus,
    route: str,
    needs_attention: list[NeedsAttention] | None = None,
    messages: list[str] | None = None,
    started: float,
) -> ExtractionResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    return ExtractionResult(
        status=status,
        source_path=str(source),
        source_sha256=source_sha256,
        detected_format=detected_format,
        output_dir=str(output_dir),
        needs_attention=needs_attention or [],
        diagnostics=ExtractionDiagnostics(
            route=route,
            messages=messages or [],
            timings_ms={"total": int((time.monotonic() - started) * 1000)},
        ),
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
