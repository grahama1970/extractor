"""Contract tests for Tau enrichment receipt validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from extractor.application.extract_file import extract_file
from extractor.integrations.tau import (
    TauReceipt,
    TauReceiptError,
    build_tau_request_payload,
    merge_tau_receipt,
    payload_sha256,
    validate_tau_receipt,
)


PDF_FIXTURE = Path("data/input/twins/preset_twin/preset_twin.pdf")


def test_tau_receipt_validates_and_merges_on_matching_lineage(tmp_path: Path) -> None:
    result = extract_file(PDF_FIXTURE, output_dir=tmp_path, offline=True)
    extraction_sha = next(a.sha256 for a in result.artifacts if a.kind == "unified_document")
    target_id = "pdf-oxide-block-1"
    payload = build_tau_request_payload(
        source_sha256=result.source_sha256,
        extraction_sha256=extraction_sha,
        target_id=target_id,
        output_schema="extractor.summary.v1",
        content={"text": "Preset Twin Baseline"},
    )
    receipt = TauReceipt(
        source_sha256=result.source_sha256,
        extraction_sha256=extraction_sha,
        target_id=target_id,
        output_schema="extractor.summary.v1",
        payload_sha256=payload_sha256(payload),
        evidence={"tau_run_id": "fixture-run"},
        output={"summary": "Fixture summary"},
    )

    accepted = validate_tau_receipt(
        receipt,
        source_sha256=result.source_sha256,
        extraction_sha256=extraction_sha,
        target_id=target_id,
        output_schema="extractor.summary.v1",
        request_payload=payload,
    )
    merged = merge_tau_receipt(result, accepted)

    assert merged.diagnostics.extra["tau_receipts"][0]["target_id"] == target_id


def test_tau_receipt_rejects_stale_or_wrong_lineage(tmp_path: Path) -> None:
    result = extract_file(PDF_FIXTURE, output_dir=tmp_path, offline=True)
    extraction_sha = next(a.sha256 for a in result.artifacts if a.kind == "unified_document")
    payload = build_tau_request_payload(
        source_sha256=result.source_sha256,
        extraction_sha256=extraction_sha,
        target_id="block-a",
        output_schema="extractor.summary.v1",
        content={"text": "x"},
    )
    receipt = TauReceipt(
        source_sha256="wrong",
        extraction_sha256=extraction_sha,
        target_id="block-a",
        output_schema="extractor.summary.v1",
        payload_sha256=payload_sha256(payload),
        evidence={"tau_run_id": "fixture-run"},
    )

    with pytest.raises(TauReceiptError, match="source_sha256"):
        validate_tau_receipt(
            receipt,
            source_sha256=result.source_sha256,
            extraction_sha256=extraction_sha,
            target_id="block-a",
            output_schema="extractor.summary.v1",
            request_payload=payload,
        )
