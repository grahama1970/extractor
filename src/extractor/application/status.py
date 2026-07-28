"""Fail-closed status validation for extractor.result.v1 envelopes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from extractor.core.schema.extraction_result import (
    ExtractionResult,
    ExtractionStatus,
    NeedsAttention,
)


def validate_required_artifacts(result: ExtractionResult) -> ExtractionResult:
    """Replay required artifact checks and downgrade terminal status on failure."""

    failures: list[str] = []
    for artifact in result.artifacts:
        path = Path(artifact.path)
        if not path.exists():
            failures.append(f"required_artifact_missing:{artifact.kind}")
            continue
        data = path.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != artifact.sha256:
            failures.append(f"required_artifact_hash_mismatch:{artifact.kind}")
        if path.stat().st_size != artifact.size_bytes:
            failures.append(f"required_artifact_size_mismatch:{artifact.kind}")
        if artifact.kind in {"unified_document", "extractor_result", "pdf_oxide_result"}:
            failures.extend(_json_artifact_failures(artifact.kind, data))

    if not failures:
        return result

    messages = [*result.diagnostics.messages, *failures]
    diagnostics = result.diagnostics.model_copy(
        update={
            "messages": messages,
            "extra": {
                **result.diagnostics.extra,
                "artifact_validation": "failed",
                "artifact_failures": failures,
            },
        }
    )
    needs_attention = [
        *result.needs_attention,
        NeedsAttention(
            code="artifact_validation_failed",
            message="One or more required extraction artifacts failed validation.",
            action="Re-run extraction and inspect diagnostics.artifact_failures.",
        ),
    ]
    return result.model_copy(
        update={
            "status": ExtractionStatus.FAILED,
            "diagnostics": diagnostics,
            "needs_attention": needs_attention,
        }
    )


def result_exit_code(result: ExtractionResult) -> int:
    """Return the process exit code implied by terminal status."""

    return 0 if result.status in {ExtractionStatus.COMPLETE, ExtractionStatus.DEGRADED} else 1


def _json_artifact_failures(kind: str, data: bytes) -> list[str]:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return [f"required_artifact_invalid_json:{kind}"]

    if _is_stub(payload):
        return [f"required_artifact_stub:{kind}"]
    if kind == "unified_document" and not isinstance(payload.get("blocks"), list):
        return [f"required_artifact_missing_blocks:{kind}"]
    if kind == "extractor_result" and payload.get("schema_version") != "extractor.result.v1":
        return [f"required_artifact_wrong_schema:{kind}"]
    return []


def _is_stub(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("stub") is True:
        return True
    meta = payload.get("meta")
    if isinstance(meta, dict) and meta.get("stub") is True:
        return True
    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("stub") is True:
        return True
    return False
