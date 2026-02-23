"""
Module: image.py

Image provider with consistent API pattern and optional VLM text extraction.
Supports both initialization patterns for backwards compatibility:
  - Standard: ImageProvider().extract_document(filepath)
  - Legacy: ImageProvider(filepath).extract_document()

External Dependencies:
- PIL: https://pillow.readthedocs.io/
- scillm (optional): For VLM text extraction via CHUTES_VLM_MODEL
"""

import asyncio
import base64
import os
import re
from pathlib import Path
from typing import List, Optional, Any, Dict, Union

from loguru import logger
from PIL import Image

from extractor.core.providers import ProviderPageLines, BaseProvider, ProviderOutput
from extractor.core.providers.fetcher_bridge import ensure_local_source
from extractor.core.schema.polygon import PolygonBox

try:
    from pdftext.schema import Reference  # type: ignore
except Exception:  # pragma: no cover - optional dependency in minimal/offline mode

    class Reference:  # type: ignore
        ...


from extractor.core.schema.unified_document import (
    UnifiedDocument,
    BlockType,
    SourceType,
    BaseBlock,
    ImageBlock,
    BlockMetadata,
    DocumentMetadata,
)


def _encode_image_base64(path: Path) -> str:
    """Read image file and return base64-encoded data URI for VLM."""
    suffix = path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
        ".bmp": "image/bmp",
    }
    mime = mime_types.get(suffix, "image/png")
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def _ocr_extract_text(image_path: Path) -> Dict[str, Any]:
    """Extract text from image using OCR (PaddleOCR or Surya fallback).

    Returns dict with 'ok', 'content', 'engine', and optionally 'error'.
    Lazy-loads OCR libraries to avoid mandatory dependencies.
    """
    # Try PaddleOCR first (best accuracy)
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = ocr.ocr(str(image_path), cls=True)

        lines = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                    lines.append(text)

        content = "\n".join(lines)
        return {"ok": True, "content": content, "engine": "paddleocr"}
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"PaddleOCR failed: {e}")

    # Try Surya (structured document OCR)
    try:
        from surya.ocr import run_ocr
        from surya.model.detection.model import load_model as load_det_model
        from surya.model.recognition.model import load_model as load_rec_model
        from PIL import Image as PILImage

        det_model = load_det_model()
        rec_model = load_rec_model()
        img = PILImage.open(image_path)
        results = run_ocr([img], [["en"]], det_model, rec_model)

        lines = []
        if results:
            for page in results:
                for line in page.text_lines:
                    lines.append(line.text)

        content = "\n".join(lines)
        return {"ok": True, "content": content, "engine": "surya"}
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Surya OCR failed: {e}")

    # Try EasyOCR (easiest setup, good for text-heavy documents)
    try:
        import easyocr

        reader = easyocr.Reader(["en"], gpu=False)
        result = reader.readtext(str(image_path))

        lines = [item[1] for item in result if item and len(item) >= 2]
        content = "\n".join(lines)
        return {"ok": True, "content": content, "engine": "easyocr"}
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"EasyOCR failed: {e}")

    # Try pytesseract (most widely available)
    try:
        import pytesseract
        from PIL import Image as PILImage

        img = PILImage.open(image_path)
        content = pytesseract.image_to_string(img)
        return {"ok": True, "content": content.strip(), "engine": "tesseract"}
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Tesseract failed: {e}")

    return {
        "ok": False,
        "error": "No OCR engine available. Install paddleocr, surya-ocr, easyocr, or pytesseract.",
    }


async def _vlm_describe_image(
    image_path: Path,
    prompt: str,
    model: Optional[str] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Call VLM to describe/extract text from an image.

    Returns dict with 'ok', 'content', and optionally 'error'.
    """
    try:
        from scillm import acompletion
    except ImportError:
        return {"ok": False, "error": "scillm not installed"}

    api_base = os.getenv("CHUTES_API_BASE")
    api_key = os.getenv("CHUTES_API_KEY")
    model_id = model or os.getenv("CHUTES_VLM_MODEL") or "Qwen/Qwen2-VL-72B-Instruct"

    if not api_key:
        return {"ok": False, "error": "CHUTES_API_KEY not set"}

    try:
        image_url = _encode_image_base64(image_path)
    except Exception as e:
        return {"ok": False, "error": f"Failed to read image: {e}"}

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ]

    try:
        resp = await acompletion(
            model=model_id,
            api_base=api_base,
            api_key=api_key,
            custom_llm_provider="openai_like",
            messages=messages,
            max_tokens=2048,
            temperature=0.2,
            timeout=timeout,
        )
        content = resp.choices[0].message.content
        return {"ok": True, "content": content, "model": model_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _parse_vlm_content_to_blocks(content: str, image_path: str) -> List[BaseBlock]:
    """Parse VLM description into structured blocks (headings, paragraphs, tables)."""
    blocks: List[BaseBlock] = []
    block_id = 0

    lines = content.strip().split("\n")
    current_paragraph: List[str] = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            # Flush paragraph
            if current_paragraph:
                blocks.append(
                    BaseBlock(
                        id=f"vlm_p_{block_id}",
                        type=BlockType.PARAGRAPH,
                        content="\n".join(current_paragraph),
                        metadata=BlockMetadata(page_number=1),
                    )
                )
                block_id += 1
                current_paragraph = []
            continue

        # Detect markdown headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line_stripped)
        if heading_match:
            # Flush paragraph first
            if current_paragraph:
                blocks.append(
                    BaseBlock(
                        id=f"vlm_p_{block_id}",
                        type=BlockType.PARAGRAPH,
                        content="\n".join(current_paragraph),
                        metadata=BlockMetadata(page_number=1),
                    )
                )
                block_id += 1
                current_paragraph = []

            level = len(heading_match.group(1))
            title = heading_match.group(2)
            blocks.append(
                BaseBlock(
                    id=f"vlm_h_{block_id}",
                    type=BlockType.HEADING,
                    content=title,
                    metadata=BlockMetadata(page_number=1, attributes={"level": level}),
                )
            )
            block_id += 1
            continue

        # Detect numbered headings (e.g., "1. Overview", "1.1 Scope")
        numbered_heading = re.match(r"^(\d+\.(?:\d+\.?)*)\s+(.+)$", line_stripped)
        if numbered_heading and len(line_stripped) < 100:
            if current_paragraph:
                blocks.append(
                    BaseBlock(
                        id=f"vlm_p_{block_id}",
                        type=BlockType.PARAGRAPH,
                        content="\n".join(current_paragraph),
                        metadata=BlockMetadata(page_number=1),
                    )
                )
                block_id += 1
                current_paragraph = []

            blocks.append(
                BaseBlock(
                    id=f"vlm_h_{block_id}",
                    type=BlockType.HEADING,
                    content=line_stripped,
                    metadata=BlockMetadata(page_number=1),
                )
            )
            block_id += 1
            continue

        # Regular text - accumulate
        current_paragraph.append(line_stripped)

    # Flush remaining paragraph
    if current_paragraph:
        blocks.append(
            BaseBlock(
                id=f"vlm_p_{block_id}",
                type=BlockType.PARAGRAPH,
                content="\n".join(current_paragraph),
                metadata=BlockMetadata(page_number=1),
            )
        )

    return blocks


class ImageProvider(BaseProvider):
    """Image provider supporting both standard and legacy initialization patterns.

    Supports optional VLM text extraction when CHUTES_API_KEY is configured.
    Set config={'use_vlm': True} to enable (default: True if API key available).
    """

    def __init__(self, filepath: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize ImageProvider.

        Args:
            filepath: Optional path to image file. If provided, loads immediately (legacy pattern).
                     If None, filepath must be provided to extract_document() (standard pattern).
            config: Optional configuration dictionary.
                    - use_vlm: bool - Enable VLM text extraction (default: True if API key set)
                    - vlm_prompt: str - Custom VLM prompt
                    - vlm_model: str - Override VLM model
                    - vlm_timeout: int - VLM call timeout in seconds (default: 60)
        """
        # Store config for later use
        self._config = config or {}
        self._loaded = False
        self._filepath: Optional[str] = None
        self._image: Optional[Image.Image] = None
        self._image_count = 0
        self._page_lines: ProviderPageLines = {}
        self._page_range: List[int] = []
        self._page_bboxes: Dict[int, List[float]] = {}
        self._fetch_download = None

        # If filepath provided, load immediately (legacy pattern)
        if filepath is not None:
            self._load(filepath)
            # Call BaseProvider init with filepath for compatibility
            super().__init__(str(self._filepath), config)
        else:
            # Deferred loading (standard pattern)
            # Don't call BaseProvider.__init__ yet - will call in _load()
            pass

    def _load(self, filepath: Union[str, Path]) -> None:
        """Load image file and initialize state."""
        if self._loaded:
            return

        resolved_path, fetch_download = ensure_local_source(str(filepath))
        self._filepath = str(resolved_path)
        self._fetch_download = fetch_download

        # Open image and detect if it's multi-page (TIFF, GIF, etc.)
        self._image = Image.open(str(resolved_path))
        self._image_count = getattr(self._image, "n_frames", 1)
        self._page_lines = {i: [] for i in range(self._image_count)}
        self._page_range = list(range(self._image_count))

        # Calculate bboxes for each frame/page
        self._page_bboxes = {}
        for i in self._page_range:
            if self._image_count > 1:
                self._image.seek(i)
            self._page_bboxes[i] = [
                0.0,
                0.0,
                float(self._image.size[0]),
                float(self._image.size[1]),
            ]

        self._loaded = True

    def extract_document(self, filepath: Optional[Union[str, Path]] = None) -> UnifiedDocument:
        """Extract image content to a UnifiedDocument.

        Extraction priority:
        1. VLM (if use_vlm=True and CHUTES_API_KEY is set)
        2. OCR (if use_ocr=True or VLM fails/unavailable, using PaddleOCR/Surya/EasyOCR/Tesseract)
        3. Basic ImageBlock with image reference only

        Args:
            filepath: Path to image file. Required if not provided in __init__.

        Returns:
            UnifiedDocument with extracted blocks.
        """
        # Handle standard pattern: filepath in extract_document
        if not self._loaded:
            if filepath is None:
                raise ValueError(
                    "filepath must be provided either in __init__ or extract_document()"
                )
            self._load(filepath)

        image_path = Path(self._filepath)
        doc_id = image_path.stem

        # Configuration options
        use_vlm = self._config.get("use_vlm", True)
        use_ocr = self._config.get("use_ocr", True)  # Enable OCR fallback by default
        has_api_key = bool(os.getenv("CHUTES_API_KEY"))

        blocks: List[Any] = []
        extraction_method = None

        # Priority 1: VLM (if available and configured)
        if use_vlm and has_api_key:
            vlm_prompt = self._config.get(
                "vlm_prompt",
                "Extract all text content from this image. "
                "Preserve the document structure including headings, paragraphs, and any tables. "
                "Use markdown formatting for headings (# for main titles, ## for sections, etc.). "
                "For numbered sections like '1. Overview', preserve the numbering.",
            )
            vlm_model = self._config.get("vlm_model")
            vlm_timeout = self._config.get("vlm_timeout", 60)

            logger.info(f"Using VLM to extract text from image: {image_path}")
            result = asyncio.run(
                _vlm_describe_image(
                    image_path=image_path,
                    prompt=vlm_prompt,
                    model=vlm_model,
                    timeout=vlm_timeout,
                )
            )

            # Quality check: VLM content should be substantial for document images
            # Minimum 100 chars and 10 words to be considered valid extraction
            vlm_content = result.get("content", "").strip()
            min_chars = self._config.get("vlm_min_chars", 100)
            min_words = self._config.get("vlm_min_words", 10)
            word_count = len(vlm_content.split())

            if result["ok"] and len(vlm_content) >= min_chars and word_count >= min_words:
                logger.info(
                    f"VLM extraction successful using {result.get('model', 'unknown')} ({len(vlm_content)} chars, {word_count} words)"
                )
                text_blocks = _parse_vlm_content_to_blocks(vlm_content, str(image_path))
                blocks.extend(text_blocks)
                blocks.append(
                    ImageBlock(
                        id="img_source",
                        content=(
                            vlm_content[:200] + "..." if len(vlm_content) > 200 else vlm_content
                        ),
                        src=str(self._filepath),
                        metadata=BlockMetadata(
                            page_number=1,
                            attributes={"vlm_extracted": True, "model": result.get("model")},
                        ),
                    )
                )
                extraction_method = "vlm"
            elif result["ok"]:
                logger.warning(
                    f"VLM returned low-quality content ({len(vlm_content)} chars, {word_count} words). Trying OCR fallback."
                )
            else:
                logger.warning(
                    f"VLM extraction failed: {result.get('error', 'empty response')}. Trying OCR fallback."
                )

        # Priority 2: OCR fallback (if VLM failed/unavailable and OCR is enabled)
        if not extraction_method and use_ocr:
            logger.info(f"Attempting OCR extraction for: {image_path}")
            ocr_result = _ocr_extract_text(image_path)

            if ocr_result["ok"] and ocr_result.get("content", "").strip():
                logger.info(
                    f"OCR extraction successful using {ocr_result.get('engine', 'unknown')}"
                )
                text_blocks = _parse_vlm_content_to_blocks(ocr_result["content"], str(image_path))
                blocks.extend(text_blocks)
                blocks.append(
                    ImageBlock(
                        id="img_source",
                        content=(
                            ocr_result["content"][:200] + "..."
                            if len(ocr_result["content"]) > 200
                            else ocr_result["content"]
                        ),
                        src=str(self._filepath),
                        metadata=BlockMetadata(
                            page_number=1,
                            attributes={"ocr_extracted": True, "engine": ocr_result.get("engine")},
                        ),
                    )
                )
                extraction_method = "ocr"
            else:
                logger.warning(f"OCR extraction failed: {ocr_result.get('error', 'empty content')}")

        # Priority 3: Basic image blocks (no text extraction)
        if not extraction_method:
            if use_vlm and not has_api_key:
                logger.debug("VLM requested but CHUTES_API_KEY not set. No OCR available.")

            # Basic extraction: just image blocks without text
            for i in range(self._image_count):
                blocks.append(
                    ImageBlock(
                        id=f"img_{i}",
                        content="",
                        src=str(self._filepath),
                        metadata=BlockMetadata(page_number=i + 1),
                    )
                )

        return UnifiedDocument(
            id=doc_id,
            source_type=SourceType.IMAGE,
            blocks=blocks,
            metadata=DocumentMetadata(title=doc_id),
        )

    # Properties for backwards compatibility
    @property
    def filepath(self) -> Optional[str]:
        return self._filepath

    @filepath.setter
    def filepath(self, value: str) -> None:
        self._filepath = value

    @property
    def image(self) -> Optional[Image.Image]:
        return self._image

    @property
    def image_count(self) -> int:
        return self._image_count

    @property
    def page_lines(self) -> ProviderPageLines:
        return self._page_lines

    @property
    def page_range(self) -> List[int]:
        return self._page_range

    @property
    def fetch_download(self):
        return self._fetch_download

    def __len__(self):
        return self._image_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._image is not None:
            self._image.close()

    def get_images(self, idxs: List[int], dpi: int) -> List[Image.Image]:
        if not self._loaded:
            raise RuntimeError(
                "Image not loaded. Call extract_document() first or provide filepath in __init__."
            )
        images = []
        for i in idxs:
            if self._image_count > 1:
                self._image.seek(i)
            # Create a copy to avoid issues with the original image
            img_copy = self._image.copy()
            images.append(img_copy)
        return images

    def get_page_bbox(self, idx: int) -> Optional[PolygonBox]:
        if not self._loaded:
            return None
        bbox = self._page_bboxes.get(idx)
        if bbox:
            return PolygonBox.from_bbox(bbox)
        return None

    def get_page_lines(self, idx: int) -> List[ProviderOutput]:
        """Image provider does not support text extraction"""
        return self._page_lines.get(idx, [])

    def get_page_refs(self, idx: int) -> List[Reference]:
        return []
