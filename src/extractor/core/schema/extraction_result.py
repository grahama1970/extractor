"""Schema-versioned result envelope for canonical extraction calls."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


RESULT_SCHEMA_VERSION: Literal["extractor.result.v1"] = "extractor.result.v1"


class ExtractionStatus(str, Enum):
    """Terminal status for an extraction run."""

    COMPLETE = "complete"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    FAILED = "failed"


class NeedsAttention(BaseModel):
    """Actionable item for a caller or human when extraction cannot complete."""

    code: str
    message: str
    action: str | None = None


class ArtifactRef(BaseModel):
    """Hashed artifact emitted by the canonical extraction facade."""

    kind: str
    path: str
    sha256: str
    size_bytes: int


class ExtractionCounts(BaseModel):
    """Normalized counts across providers."""

    blocks: int = 0
    pages: int | None = None
    tables: int = 0
    figures: int = 0


class ExtractionDiagnostics(BaseModel):
    """Routing and provenance details for maintainers."""

    route: str
    provider: str | None = None
    engine: str | None = None
    messages: list[str] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Canonical result returned by `extract_file` and the `extractor` CLI."""

    schema_version: Literal["extractor.result.v1"] = RESULT_SCHEMA_VERSION
    status: ExtractionStatus
    source_path: str
    source_sha256: str
    detected_format: str
    output_dir: str
    counts: ExtractionCounts = Field(default_factory=ExtractionCounts)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    needs_attention: list[NeedsAttention] = Field(default_factory=list)
    diagnostics: ExtractionDiagnostics
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def ok(self) -> bool:
        """Return whether the status should be a zero-exit terminal status."""

        return self.status in {ExtractionStatus.COMPLETE, ExtractionStatus.DEGRADED}

    def write_json(self, path: Path) -> ArtifactRef:
        """Write this result envelope and return its own hashed artifact ref."""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        data = path.read_bytes()
        import hashlib

        return ArtifactRef(
            kind="extractor_result",
            path=str(path),
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
        )
