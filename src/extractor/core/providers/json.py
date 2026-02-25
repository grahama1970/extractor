"""
JSON Provider for JSON and JSONL Files
---------------------------------------
Extracts content from JSON (.json) and JSON Lines (.jsonl) files into
UnifiedDocument format.  Handles objects, arrays, nested data, and
line-delimited JSON.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Union

from loguru import logger

from extractor.core.schema.unified_document import (
    BaseBlock,
    BlockMetadata,
    BlockType,
    DocumentMetadata,
    SourceType,
    UnifiedDocument,
)


class JSONProvider:
    """Provider for JSON and JSON Lines files.

    Detects YouTube transcript JSON ({meta, transcript[], full_text})
    from /ingest-youtube and extracts clean text instead of walking
    the JSON structure generically.
    """

    def __init__(self):
        self._block_counter = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        """Extract content from a JSON or JSONL file."""
        file_path = Path(filepath)
        logger.info("Extracting JSON: {}", file_path.name)

        self._block_counter = 0

        try:
            raw = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = file_path.read_text(encoding="latin-1")

        if not raw.strip():
            logger.warning("Empty JSON file: {}", file_path.name)
            return self._empty_doc(file_path)

        # Detect JSONL (multiple lines each containing a JSON object)
        is_jsonl = file_path.suffix.lower() == ".jsonl"

        try:
            if is_jsonl:
                blocks = self._parse_jsonl(raw)
            else:
                data = json.loads(raw)
                # Detect YouTube transcript JSON from /ingest-youtube
                if self._is_youtube_transcript(data):
                    logger.info("Detected YouTube transcript: {}", file_path.name)
                    return self._extract_transcript(data, file_path)
                blocks = self._json_to_blocks(data)
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error in {}: {}", file_path.name, exc)
            # Fall back to treating the whole file as text
            blocks = [
                BaseBlock(
                    id=self._next_id(),
                    type=BlockType.PARAGRAPH,
                    content=raw[:10000],
                    metadata=BlockMetadata(
                        page_number=0,
                        attributes={"parse_error": str(exc)},
                    ),
                )
            ]

        return UnifiedDocument(
            id=file_path.stem,
            source_type=SourceType.JSON,
            source_path=str(file_path),
            blocks=blocks,
            metadata=DocumentMetadata(
                title=file_path.stem,
                file_hash=self._compute_file_hash(file_path),
                page_count=1,
            ),
        )

    # ------------------------------------------------------------------
    # YouTube transcript detection & extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _is_youtube_transcript(data: Any) -> bool:
        """Detect /ingest-youtube JSON: {meta, transcript[], full_text}."""
        if not isinstance(data, dict):
            return False
        return ("transcript" in data or "full_text" in data) and "meta" in data

    def _extract_transcript(self, data: Dict, file_path: Path) -> UnifiedDocument:
        """Convert YouTube transcript JSON to clean UnifiedDocument.

        Produces a heading with video metadata followed by a single
        paragraph block containing the full transcript text — ready
        for downstream /doc2qra consumption.
        """
        meta = data.get("meta", {})
        title = meta.get("title", file_path.stem)
        channel = meta.get("channel", "")
        upload_date = meta.get("upload_date", "")
        description = meta.get("description", "")
        duration_sec = meta.get("duration_sec", 0)

        # Get full_text; fall back to concatenating transcript segments
        full_text = data.get("full_text", "")
        if not full_text:
            segments = data.get("transcript", [])
            full_text = " ".join(
                seg.get("text", "") for seg in segments if seg.get("text")
            )

        if not full_text.strip():
            logger.warning("YouTube transcript has no text: {}", file_path.name)
            return self._empty_doc(file_path)

        blocks: List[BaseBlock] = []

        # Title heading
        blocks.append(BaseBlock(
            id=self._next_id(),
            type=BlockType.HEADING,
            content=title,
            metadata=BlockMetadata(page_number=0, attributes={"level": 1}),
        ))

        # Metadata block
        meta_lines = []
        if channel:
            meta_lines.append(f"Channel: {channel}")
        if upload_date and len(upload_date) == 8:
            meta_lines.append(
                f"Date: {upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
            )
        if duration_sec:
            meta_lines.append(f"Duration: {duration_sec // 60} minutes")
        if meta_lines:
            blocks.append(BaseBlock(
                id=self._next_id(),
                type=BlockType.PARAGRAPH,
                content="\n".join(meta_lines),
                metadata=BlockMetadata(
                    page_number=0,
                    attributes={"is_metadata": True},
                ),
            ))

        # Description (first meaningful paragraph, skip URLs/boilerplate)
        if description:
            desc_lines = []
            for line in description.split("\n"):
                stripped = line.strip()
                if stripped.startswith(
                    ("http", "#", "SUBSCRIBE", "RECOMMENDED", "Looking for")
                ):
                    break
                desc_lines.append(line)
            desc_clean = "\n".join(desc_lines).strip()
            if desc_clean:
                blocks.append(BaseBlock(
                    id=self._next_id(),
                    type=BlockType.PARAGRAPH,
                    content=desc_clean,
                    metadata=BlockMetadata(
                        page_number=0,
                        attributes={"is_description": True},
                    ),
                ))

        # Full transcript as single block (for single-LLM-call QRA extraction)
        blocks.append(BaseBlock(
            id=self._next_id(),
            type=BlockType.PARAGRAPH,
            content=full_text,
            metadata=BlockMetadata(
                page_number=0,
                attributes={"is_transcript": True, "char_count": len(full_text)},
            ),
        ))

        logger.info(
            "Extracted transcript: {} ({:,} chars)",
            title,
            len(full_text),
        )

        return UnifiedDocument(
            id=file_path.stem,
            source_type=SourceType.JSON,
            source_path=str(file_path),
            blocks=blocks,
            metadata=DocumentMetadata(
                title=title,
                file_hash=self._compute_file_hash(file_path),
                page_count=1,
                attributes={
                    "content_type": "youtube_transcript",
                    "channel": channel,
                    "duration_sec": duration_sec,
                },
            ),
        )

    # ------------------------------------------------------------------
    # JSONL parsing
    # ------------------------------------------------------------------

    def _parse_jsonl(self, raw: str) -> List[BaseBlock]:
        """Parse JSON Lines (one JSON object per line)."""
        blocks: List[BaseBlock] = []
        for line_no, line in enumerate(raw.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                blocks.append(
                    BaseBlock(
                        id=self._next_id(),
                        type=BlockType.PARAGRAPH,
                        content=line[:2000],
                        metadata=BlockMetadata(
                            page_number=0,
                            attributes={"jsonl_line": line_no, "parse_error": True},
                        ),
                    )
                )
                continue

            # Each line becomes a heading (with line number) + nested blocks
            blocks.append(
                BaseBlock(
                    id=self._next_id(),
                    type=BlockType.HEADING,
                    content=f"Record {line_no}",
                    metadata=BlockMetadata(
                        page_number=0,
                        attributes={"jsonl_line": line_no},
                    ),
                )
            )
            blocks.extend(self._json_to_blocks(obj))

        return blocks

    # ------------------------------------------------------------------
    # JSON → blocks
    # ------------------------------------------------------------------

    def _json_to_blocks(self, data: Any, depth: int = 0) -> List[BaseBlock]:
        """Convert JSON data to blocks recursively."""
        blocks: List[BaseBlock] = []
        MAX_DEPTH = 8  # prevent runaway recursion

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)) and depth < MAX_DEPTH:
                    # Nested structure — heading for the key, then recurse
                    blocks.append(
                        BaseBlock(
                            id=self._next_id(),
                            type=BlockType.HEADING if depth < 3 else BlockType.PARAGRAPH,
                            content=str(key),
                            metadata=BlockMetadata(
                                page_number=0,
                                attributes={"key": key, "depth": depth, "is_nested": True},
                            ),
                        )
                    )
                    blocks.extend(self._json_to_blocks(value, depth + 1))
                else:
                    blocks.append(
                        BaseBlock(
                            id=self._next_id(),
                            type=BlockType.PARAGRAPH,
                            content=f"{key}: {self._format_value(value)}",
                            metadata=BlockMetadata(
                                page_number=0,
                                attributes={"key": key, "value_type": type(value).__name__},
                            ),
                        )
                    )

        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)) and depth < MAX_DEPTH:
                    blocks.extend(self._json_to_blocks(item, depth + 1))
                else:
                    blocks.append(
                        BaseBlock(
                            id=self._next_id(),
                            type=BlockType.PARAGRAPH,
                            content=f"[{i}]: {self._format_value(item)}",
                            metadata=BlockMetadata(
                                page_number=0,
                                attributes={"array_index": i, "item_type": type(item).__name__},
                            ),
                        )
                    )
        else:
            blocks.append(
                BaseBlock(
                    id=self._next_id(),
                    type=BlockType.PARAGRAPH,
                    content=str(data),
                    metadata=BlockMetadata(
                        page_number=0,
                        attributes={"value_type": type(data).__name__, "is_primitive": True},
                    ),
                )
            )

        return blocks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_id(self) -> str:
        self._block_counter += 1
        return f"json-block-{self._block_counter:04d}"

    def _empty_doc(self, file_path: Path) -> UnifiedDocument:
        return UnifiedDocument(
            id=file_path.stem,
            source_type=SourceType.JSON,
            source_path=str(file_path),
            blocks=[],
            metadata=DocumentMetadata(
                title=file_path.stem,
                file_hash=self._compute_file_hash(file_path),
                page_count=0,
            ),
        )

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        if value is None:
            return "null"
        if isinstance(value, (dict, list)):
            dumped = json.dumps(value, indent=2)
            return dumped[:200] + "..." if len(dumped) > 200 else dumped
        return str(value)

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        try:
            return hashlib.md5(file_path.read_bytes()).hexdigest()
        except Exception:
            return ""