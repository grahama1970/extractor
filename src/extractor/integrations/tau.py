"""Tau receipt validation boundary for model-mediated enrichment."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from extractor.core.schema.extraction_result import ExtractionResult


class TauReceiptError(ValueError):
    """Raised when a Tau enrichment receipt cannot be trusted."""


class TauReceipt(BaseModel):
    """Minimal receipt Extractor accepts from Tau before merging enrichment."""

    schema_version: str = "tau.enrichment.receipt.v1"
    source_sha256: str
    extraction_sha256: str
    target_id: str
    output_schema: str
    payload_sha256: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)


def validate_tau_receipt(
    receipt: TauReceipt | dict[str, Any],
    *,
    source_sha256: str,
    extraction_sha256: str,
    target_id: str,
    output_schema: str,
    request_payload: dict[str, Any],
) -> TauReceipt:
    """Validate Tau lineage and payload identity before accepting enrichment."""

    parsed = receipt if isinstance(receipt, TauReceipt) else TauReceipt.model_validate(receipt)
    expected_payload_sha = _payload_sha256(request_payload)
    mismatches: list[str] = []
    if parsed.schema_version != "tau.enrichment.receipt.v1":
        mismatches.append("schema_version")
    if parsed.source_sha256 != source_sha256:
        mismatches.append("source_sha256")
    if parsed.extraction_sha256 != extraction_sha256:
        mismatches.append("extraction_sha256")
    if parsed.target_id != target_id:
        mismatches.append("target_id")
    if parsed.output_schema != output_schema:
        mismatches.append("output_schema")
    if parsed.payload_sha256 != expected_payload_sha:
        mismatches.append("payload_sha256")
    if not parsed.evidence:
        mismatches.append("evidence")
    if mismatches:
        raise TauReceiptError("Invalid Tau receipt fields: " + ", ".join(mismatches))
    return parsed


def merge_tau_receipt(result: ExtractionResult, receipt: TauReceipt) -> ExtractionResult:
    """Return a result envelope with an accepted Tau receipt recorded."""

    extra = dict(result.diagnostics.extra)
    receipts = list(extra.get("tau_receipts", []))
    receipts.append(
        {
            "schema_version": receipt.schema_version,
            "target_id": receipt.target_id,
            "output_schema": receipt.output_schema,
            "payload_sha256": receipt.payload_sha256,
            "evidence": receipt.evidence,
        }
    )
    extra["tau_receipts"] = receipts
    return result.model_copy(
        update={"diagnostics": result.diagnostics.model_copy(update={"extra": extra})}
    )


def build_tau_request_payload(
    *,
    source_sha256: str,
    extraction_sha256: str,
    target_id: str,
    output_schema: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """Build the stable payload Extractor submits to Tau."""

    return {
        "source_sha256": source_sha256,
        "extraction_sha256": extraction_sha256,
        "target_id": target_id,
        "output_schema": output_schema,
        "content": content,
    }


def payload_sha256(payload: dict[str, Any]) -> str:
    """Public helper for tests and Tau clients constructing receipts."""

    return _payload_sha256(payload)


def _payload_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
