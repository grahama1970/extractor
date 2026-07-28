"""System diagnostics including CPU, memory, and GPU resource sampling for pipeline runs."""
from __future__ import annotations

from extractor.pipeline.utils.reliability import log_stage_error
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
import threading
import time as _time

try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # type: ignore
# NVML (GPU) support optional
try:
    # prefer nvidia-ml-py; fall back to pynvml if available
    try:
        import pynvml as _nvml  # type: ignore
    except Exception:
        _nvml = None  # type: ignore
    pynvml = _nvml
    _nvml_ok = False
    if pynvml is not None:
        try:
            pynvml.nvmlInit()
            _nvml_ok = True
        except Exception as exc:
            log_stage_error("diagnostics.py", exc, {"context": "diagnostics.py"})
            _nvml_ok = False
except Exception:
    pynvml = None  # type: ignore
    _nvml_ok = False


def get_run_id() -> str:
    """Generate a unique run identifier."""
    return uuid.uuid4().hex


def iso_now() -> str:
    """Return current datetime in ISO 8601 format."""
    return datetime.now().isoformat()


def make_event(
    stage: str,
    severity: str,
    code: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an event dictionary from given parameters with defaults."""
    return {
        "stage": stage,
        "severity": severity,
        "code": code,
        "message": message,
        "ts": ts or iso_now(),
        "context": context or {},
    }


def snapshot_resources(prefix: str) -> Dict[str, Any]:
    """Capture memory usage metrics for a process prefix."""
    out: Dict[str, Any] = {}
    try:
        if psutil is not None:
            proc = psutil.Process()
            out[f"proc_rss_mb_{prefix}"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            out[f"vmem_used_mb_{prefix}"] = int((getattr(vm, "used", 0)) / (1024 * 1024))
        if _nvml_ok and pynvml is not None:
            try:
                dev_count = pynvml.nvmlDeviceGetCount()
                gpumem = []
                util = []
                for i in range(dev_count):
                    h = pynvml.nvmlDeviceGetHandleByIndex(i)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                    u = pynvml.nvmlDeviceGetUtilizationRates(h)
                    gpumem.append(int(mem.used / (1024 * 1024)))
                    util.append(int(getattr(u, "gpu", 0)))
                out[f"gpu_mem_used_mb_{prefix}"] = gpumem
                out[f"gpu_util_percent_{prefix}"] = util
            except Exception as exc:
                log_stage_error("diagnostics.py", exc, {"context": "diagnostics.py"})
                raise
    except Exception as exc:
        log_stage_error("diagnostics.py", exc, {"context": "diagnostics.py"})
        raise
    return out


def build_stage_timings(
    stage_start_ts: str, t0_monotonic: float, extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build stage timings dictionary with start/end timestamps and duration."""
    import time

    timings = {
        "stage_start_ts": stage_start_ts,
        "stage_end_ts": iso_now(),
        "stage_duration_ms": int((time.monotonic() - t0_monotonic) * 1000),
    }
    if extra:
        timings.update(extra)
    return timings


def start_resource_sampler(interval_sec: float = 2.0):
    """Start a background sampler that periodically records process/system metrics.
    Returns a sampler dict with 'thread' and 'samples'. If psutil not available, returns None.
    """
    if psutil is None or interval_sec <= 0:
        return None
    samples = []
    stop_flag = {"stop": False}

    def _run():
        """Monitor system and GPU metrics until stop flag is set."""
        while not stop_flag["stop"]:
            try:
                proc = psutil.Process()
                vm = psutil.virtual_memory()
                gpu_mem = None
                gpu_util = None
                try:
                    if _nvml_ok and pynvml is not None:
                        h = pynvml.nvmlDeviceGetHandleByIndex(0)
                        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                        u = pynvml.nvmlDeviceGetUtilizationRates(h)
                        gpu_mem = int(mem.used / (1024 * 1024))
                        gpu_util = int(getattr(u, "gpu", 0))
                except Exception as exc:
                    log_stage_error("diagnostics.py", exc, {"context": "diagnostics.py"})
                    raise
                samples.append(
                    {
                        "ts": iso_now(),
                        "proc_rss_mb": int((proc.memory_info().rss or 0) / (1024 * 1024)),
                        "cpu_percent": float(proc.cpu_percent(interval=None)),
                        "vmem_used_mb": int((getattr(vm, "used", 0)) / (1024 * 1024)),
                        "gpu_mem_used_mb": gpu_mem,
                        "gpu_util_percent": gpu_util,
                    }
                )
            except Exception as exc:
                log_stage_error("diagnostics.py", exc, {"context": "diagnostics.py"})
                raise
            _time.sleep(interval_sec)

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    return {"thread": th, "samples": samples, "stop": stop_flag}


def stop_resource_sampler(sampler):
    """Stop the background sampler and return collected samples."""
    try:
        if sampler and isinstance(sampler, dict):
            sampler["stop"]["stop"] = True
            th = sampler.get("thread")
            if th:
                th.join(timeout=1.0)
            return sampler.get("samples", [])
    except Exception as exc:
        log_stage_error("diagnostics.py", exc, {"context": "diagnostics.py"})
        raise
        return []
    return []


def classify_llm_error(exc: Exception) -> dict:
    """Normalize LLM exceptions to a stable code/category/message."""
    msg = str(exc)
    low = msg.lower()
    if any(k in low for k in ("timeout", "readtimeout", "timed out")):
        return {"code": "llm_timeout", "category": "timeout", "message": msg}
    if any(k in low for k in ("network", "connect", "connection", "econn", "dns", "proxy")):
        return {"code": "llm_network_error", "category": "network", "message": msg}
    return {"code": "llm_batch_failed", "category": "general", "message": msg}


def gpu_metrics_available() -> bool:
    """Return True if NVML GPU metrics are available."""
    return bool(globals().get("_nvml_ok", False))


# =============================================================================
# ITAR-Safe Diagnostic Pattern Generation
# =============================================================================
# Generates structural fingerprints (pattern.json) from extraction failures
# WITHOUT capturing any actual document content. Enables zero-knowledge debugging.
# =============================================================================

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Tuple


@dataclass
class TablePattern:
    """Structural pattern of a table (no content)."""
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    rows: int
    cols: int
    has_header: bool = True
    has_borders: bool = True
    merged_cells: List[Dict[str, int]] = field(default_factory=list)
    cell_widths: List[float] = field(default_factory=list)


@dataclass
class ExtractionFailurePattern:
    """
    ITAR-safe structural fingerprint for an extraction failure.

    Contains ONLY structural information - NO actual document content.
    """
    version: str = "1.0"
    failure_type: str = "unknown"
    page: Dict[str, Any] = field(default_factory=lambda: {"width": 612, "height": 792})
    table: Optional[Dict[str, Any]] = None
    extraction_params: Optional[Dict[str, Any]] = None
    failure_details: Optional[Dict[str, Any]] = None
    notes: str = ""
    generated_at: str = field(default_factory=iso_now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "version": self.version,
            "failure_type": self.failure_type,
            "page": self.page,
            "table": self.table,
            "extraction_params": self.extraction_params,
            "failure_details": self.failure_details,
            "notes": self.notes,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Path) -> None:
        """Save to file."""
        path.write_text(self.to_json())


def generate_table_failure_pattern(
    page_width: float,
    page_height: float,
    page_number: int,
    table_bbox: Tuple[float, float, float, float],
    rows: int,
    cols: int,
    fragmentation_count: int,
    strategy: str,
    line_scale: Optional[int] = None,
    edge_tol: Optional[int] = None,
    notes: str = "",
) -> ExtractionFailurePattern:
    """
    Generate a diagnostic pattern from a table extraction failure.

    This captures ONLY structural information - no actual content.
    """
    # Determine failure type
    if fragmentation_count > 0:
        failure_type = "table_fragmentation"
    elif rows == 0 and cols == 0:
        failure_type = "table_missed"
    else:
        failure_type = "table_extraction_error"

    flavor = "lattice" if "lattice" in strategy.lower() else "stream"

    return ExtractionFailurePattern(
        failure_type=failure_type,
        page={"width": page_width, "height": page_height, "page_number": page_number},
        table={
            "bbox": list(table_bbox),
            "rows": rows,
            "cols": cols,
            "has_borders": flavor == "lattice",
        },
        extraction_params={
            "flavor": flavor,
            "line_scale": line_scale,
            "edge_tol": edge_tol,
        },
        failure_details={
            "fragmentation_count": fragmentation_count,
            "cells_detected": rows * cols,
        },
        notes=notes,
    )


def generate_support_bundle(
    pdf_name: str,
    page_number: int,
    page_width: float,
    page_height: float,
    failures: List[Dict[str, Any]],
    output_dir: Optional[Path] = None,
) -> Dict[str, Path]:
    """
    Generate a complete support bundle for a PDF extraction failure.

    Returns paths to generated files (pattern.json, etc.)
    """
    import hashlib

    if output_dir is None:
        output_dir = Path.home() / ".pi" / "debug-table" / "bundles"
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_hash = hashlib.md5(pdf_name.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_id = f"{pdf_hash}_{timestamp}"

    bundle_dir = output_dir / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    for i, failure in enumerate(failures):
        table_bbox = failure.get("bbox", (72, 100, 540, 400))
        rows = failure.get("rows", 0)
        cols = failure.get("cols", 0)
        frag_count = failure.get("fragmentation", 0)
        strategy = failure.get("strategy", "unknown")
        line_scale = failure.get("line_scale")
        edge_tol = failure.get("edge_tol")

        pattern = generate_table_failure_pattern(
            page_width=page_width,
            page_height=page_height,
            page_number=page_number,
            table_bbox=table_bbox,
            rows=rows,
            cols=cols,
            fragmentation_count=frag_count,
            strategy=strategy,
            line_scale=line_scale,
            edge_tol=edge_tol,
            notes=f"Auto-generated from {pdf_name} page {page_number}",
        )

        pattern_path = bundle_dir / f"pattern_{i}.json"
        pattern.save(pattern_path)
        results[f"pattern_{i}"] = pattern_path

    # Create manifest
    manifest = {
        "bundle_id": bundle_id,
        "source_pdf": pdf_name,
        "page_number": page_number,
        "failure_count": len(failures),
        "generated_at": iso_now(),
        "files": {k: str(v.name) for k, v in results.items()},
        "itar_safe": True,
    }

    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    results["manifest"] = manifest_path

    return results


def should_generate_diagnostic(fragmentation: int, threshold: int = 3) -> bool:
    """Check if diagnostic should be generated based on fragmentation level."""
    return fragmentation >= threshold


# =============================================================================
# Indecipherable Table Detection & Logging
# =============================================================================
# For vintage scanned PDFs where tables exist structurally but content is
# unreadable (bad OCR, faded text, microfilm artifacts, format corruption).
# These need special handling and pattern capture for synthetic generation.
# =============================================================================

@dataclass
class IndecipherableTablePattern:
    """
    ITAR-safe pattern for tables that are structurally detected but unreadable.

    This captures:
    - Table geometry (bbox, grid structure)
    - Detection confidence
    - Failure indicators (OCR confidence, text density, etc.)

    Does NOT capture:
    - Actual cell content (may contain controlled info)
    - Raw OCR output
    """
    version: str = "1.0"
    failure_type: str = "table_indecipherable"
    page: Dict[str, Any] = field(default_factory=lambda: {"width": 612, "height": 792})
    table: Optional[Dict[str, Any]] = None
    readability_metrics: Optional[Dict[str, Any]] = None
    source_characteristics: Optional[Dict[str, Any]] = None
    notes: str = ""
    generated_at: str = field(default_factory=iso_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "failure_type": self.failure_type,
            "page": self.page,
            "table": self.table,
            "readability_metrics": self.readability_metrics,
            "source_characteristics": self.source_characteristics,
            "notes": self.notes,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json())


def detect_indecipherable_table(
    cell_texts: List[str],
    ocr_confidences: Optional[List[float]] = None,
    min_readable_ratio: float = 0.3,
    min_avg_confidence: float = 0.5,
) -> Dict[str, Any]:
    """
    Detect if a table is indecipherable (structurally present but unreadable).

    Args:
        cell_texts: List of text content from each cell
        ocr_confidences: Optional OCR confidence scores per cell
        min_readable_ratio: Minimum ratio of cells with readable text
        min_avg_confidence: Minimum average OCR confidence

    Returns:
        Dict with:
        - is_indecipherable: bool
        - readable_ratio: float (0-1)
        - avg_confidence: float (0-1) or None
        - empty_cell_ratio: float
        - garbled_cell_ratio: float (cells with mostly non-alphanumeric)
    """
    if not cell_texts:
        return {
            "is_indecipherable": True,
            "readable_ratio": 0.0,
            "avg_confidence": None,
            "empty_cell_ratio": 1.0,
            "garbled_cell_ratio": 0.0,
            "reason": "no_cells",
        }

    total_cells = len(cell_texts)
    empty_cells = sum(1 for t in cell_texts if not t or not t.strip())

    # Check for garbled text (mostly non-alphanumeric characters)
    def is_garbled(text: str) -> bool:
        """Check if text contains mostly non-alphanumeric characters."""
        if not text:
            return False
        alnum = sum(1 for c in text if c.isalnum() or c.isspace())
        return alnum / len(text) < 0.5 if text else True

    garbled_cells = sum(1 for t in cell_texts if t and is_garbled(t))
    readable_cells = total_cells - empty_cells - garbled_cells

    readable_ratio = readable_cells / total_cells if total_cells else 0
    empty_ratio = empty_cells / total_cells if total_cells else 1
    garbled_ratio = garbled_cells / total_cells if total_cells else 0

    # Calculate average confidence if available
    avg_confidence = None
    if ocr_confidences:
        valid_conf = [c for c in ocr_confidences if c is not None]
        avg_confidence = sum(valid_conf) / len(valid_conf) if valid_conf else None

    # Determine if indecipherable
    is_indecipherable = False
    reason = "readable"

    if readable_ratio < min_readable_ratio:
        is_indecipherable = True
        reason = "low_readable_ratio"
    elif avg_confidence is not None and avg_confidence < min_avg_confidence:
        is_indecipherable = True
        reason = "low_ocr_confidence"
    elif garbled_ratio > 0.5:
        is_indecipherable = True
        reason = "mostly_garbled"
    elif empty_ratio > 0.8:
        is_indecipherable = True
        reason = "mostly_empty"

    return {
        "is_indecipherable": is_indecipherable,
        "readable_ratio": round(readable_ratio, 3),
        "avg_confidence": round(avg_confidence, 3) if avg_confidence else None,
        "empty_cell_ratio": round(empty_ratio, 3),
        "garbled_cell_ratio": round(garbled_ratio, 3),
        "reason": reason,
    }


def generate_indecipherable_pattern(
    page_width: float,
    page_height: float,
    page_number: int,
    table_bbox: Tuple[float, float, float, float],
    rows: int,
    cols: int,
    readability_metrics: Dict[str, Any],
    is_scanned: bool = False,
    estimated_age: Optional[str] = None,
    notes: str = "",
) -> IndecipherableTablePattern:
    """
    Generate ITAR-safe pattern for an indecipherable table.

    This can be used to:
    1. Create synthetic fixtures that reproduce the failure
    2. Track failure patterns across corpora
    3. Share debugging info without exposing content
    """
    return IndecipherableTablePattern(
        page={"width": page_width, "height": page_height, "page_number": page_number},
        table={
            "bbox": list(table_bbox),
            "rows": rows,
            "cols": cols,
            "cell_count": rows * cols,
        },
        readability_metrics=readability_metrics,
        source_characteristics={
            "is_scanned": is_scanned,
            "estimated_age": estimated_age,
            "likely_ocr_source": is_scanned,
        },
        notes=notes,
    )


# Global log for indecipherable tables (for corpus-level analysis)
INDECIPHERABLE_LOG_FILE = Path.home() / ".pi" / "debug-table" / "indecipherable_tables.jsonl"


def log_indecipherable_table(
    pdf_path: str,
    page_number: int,
    table_index: int,
    pattern: IndecipherableTablePattern,
) -> None:
    """
    Log an indecipherable table to the global tracking file.

    This enables corpus-level analysis of unreadable tables.
    """
    INDECIPHERABLE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "pdf_path": pdf_path,
        "page_number": page_number,
        "table_index": table_index,
        "logged_at": iso_now(),
        **pattern.to_dict(),
    }

    with open(INDECIPHERABLE_LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
