#!/usr/bin/env python3
"""
SuspiciousHeaderFixer
---------------------
Deterministic post-processor that merges split headers, demotes
mis-classified blocks, and flags remaining oddities.

Relies on span fonts from the Document graph or optional PyMuPDF lookups
for first-span font comparisons (no dependency on FontCaptureProcessor).
"""

from __future__ import annotations

import re
from typing import List

from rapidfuzz import fuzz  # ≥ 2.2 (MIT license)

from extractor.core.processors import BaseProcessor
from extractor.core.schema.document import Document
from extractor.core.schema.blocks.base import Block
from extractor.core.schema import BlockTypes
from loguru import logger


class SuspiciousHeaderFixer(BaseProcessor):
    """
    Merge split headers, demote wrongly-labelled headers,
    and flag suspicious headers for further review.
    """

    # -----------------------------------------------------------------
    # Legitimate section titles that should *never* be demoted or flagged
    HEADER_WHITELIST: set[str] = {
        "Formal Requirements",
        "Introduction",
        "Conclusion",
        "Discussion",
        "Results",
        "Methods",
        "Methodology",
        "Overview",
        "Background",
        "Abstract",
        "Summary",
        "Acknowledgements",
        "References",
        "Appendix",
        "Notes",
        "Notation",
        "Definitions",
        "Examples",
        "See also",
        "Related work",
        "Limitations",
        "Acknowledgments",
        "Materials and methods",
        "Experimental setup",
        "System overview",
        "Design",
        "Implementation",
        "Evaluation",
        "Future work",
        "Conclusions",
        "Discussion and conclusions",
    }

    # Fuzzy-match threshold (0–100) for whitelist
    WHITELIST_SIMILARITY = 97

    # Strong patterns that indicate a legitimate header
    HEADER_PATTERNS = [
        r"^\d+(?:[.\-]\d+)*(?:[.)])?\s+\S.*$",   # 1, 1.1, 2-3, 3(a), 4.1.2."
        r"^[IVXLCDM]+[.)]?\s+\S.*$",                # Roman numerals I., II, IV)"
        r"^[A-Z][A-Z0-9\s\-/&]+$",                  # ALL-CAPS, e.g., SYSTEM OVERVIEW
    ]

    # -----------------------------------------------------------------
    def __call__(self, document: Document) -> Document:
        fixes = 0
        flags = 0

        # Open PyMuPDF once if available to enable first-span font lookup
        fitz_doc = None
        try:
            import fitz  # PyMuPDF

            try:
                fitz_doc = fitz.open(document.filepath)
            except Exception:
                fitz_doc = None
        except Exception:
            fitz_doc = None

        for page in document.pages:
            # Operate on a copy of the children list to allow safe in-place modification
            children_list = list(page.children)
            # Promote confident numeric/roman outlines to headers (before demotions)
            self._promote_confident_headers(children_list, document)
            fixes += self._fix_split_headers(children_list, document, fitz_doc)
            fixes += self._demote_improper_headers_with_doc(children_list, document)
            flags += self._flag_suspicious_headers(children_list)
            fixes += self._merge_orphaned_tables(children_list)
            fixes += self._demote_sentence_like_tables(children_list)
            # Update the page's children with the modified list
            page.children = children_list

        logger.info(f"SuspiciousHeaderFixer applied {fixes} fixes and raised {flags} flags")
        try:
            if fitz_doc is not None:
                fitz_doc.close()
        except Exception:
            pass
        return document

    # -----------------------------------------------------------------
    def _fix_split_headers(self, blocks: List[Block], document: Document, fitz_doc=None) -> int:
        """Merge adjacent Text blocks that together form a header."""
        count = 0
        i = 0
        while i < len(blocks) - 1:
            a, b = blocks[i], blocks[i + 1]
            if a.block_type != BlockTypes.Text or b.block_type != BlockTypes.Text:
                i += 1
                continue

            # Require similar fonts
            if not self._same_font(a, b, document, fitz_doc):
                i += 1
                continue

            # Get text content - blocks may store text differently
            a_text = getattr(a, "text", "") or ""
            b_text = getattr(b, "text", "") or ""

            combined = f"{a_text.rstrip()} {b_text.lstrip()}"

            # 1. Numbered header split across blocks
            if re.match(r"^\d+(?:\d+)*\s+\w.*\($", a_text) and b_text.rstrip().endswith(")"):
                if hasattr(a, "text"):
                    a.text = combined
                a.block_type = BlockTypes.SectionHeader
                del blocks[i + 1]
                count += 1
                continue

            # 2. Generic header pattern - DISABLED: Too aggressive, creates false headers
            # The _looks_headerish function marks any text with <10 words as a header
            # which is clearly wrong for sentences like "For any HW configuration,"
            # if self._looks_headerish(combined):
            #     if hasattr(a, 'text'): a.text = combined
            #     a.block_type = BlockTypes.SectionHeader
            #     del blocks[i + 1]
            #     count += 1
            #     continue

            i += 1
        return count


    def _promote_confident_headers(self, blocks: List[Block], document: Document) -> None:
        import re as _re
        def is_outline(txt: str) -> bool:
            t=(txt or '').strip()
            return bool(_re.match(r'^\d+(?:[.\-](?:\d+|[A-Za-z]+))*[.)]?\s+\S', t) or _re.match(r'^[IVXLCDM]+[.)]?\s+\S', t))
        for b in blocks:
            if b.block_type != BlockTypes.Text:
                continue
            t=(getattr(b,'text','') or '').strip()
            if not t:
                continue
            if not is_outline(t):
                continue
            # do not promote labels or sentences
            try:
                if t.endswith(':') and self._is_bold(b, document):
                    continue
            except Exception:
                pass
            if self._looks_sentence(t):
                continue
            b.block_type = BlockTypes.SectionHeader

    def _demote_improper_headers_with_doc(self, blocks: List[Block], document: Document) -> int:
        """Demote SectionHeader blocks unless whitelisted or pattern-matched."""
        count = 0
        for b in blocks:
            if b.block_type != BlockTypes.SectionHeader:
                continue

            # Get text content for analysis
            # First try direct text attribute
            text = getattr(b, "text", "").strip()

            # If no direct text but has raw_text method, use that
            if not text and hasattr(b, "raw_text"):
                try:
                    # Pass document to get text from structure
                    text = b.raw_text(document).strip()
                except:
                    text = ""

            # If block has no text but has structure, it will get text later
            # Check if it looks like a proper header based on structure
            if not text and hasattr(b, "structure") and b.structure:
                # For now, keep it as SectionHeader if it has structure
                # The SectionHeaderProcessor will mark it as ignore_for_output if empty
                continue

            # If we have text, check if it's a confident header
            if text and self._is_confident_header(b):
                continue
            # Demote sentence-like lines (not headers)
            if text and self._looks_sentence(text):
                b.block_type = BlockTypes.Text
                count += 1
                continue

            # Rule: Bold text ending with a colon is NOT a section header
            try:
                if text.endswith(":") and self._is_bold(b, document):
                    b.block_type = BlockTypes.Text
                    count += 1
                    continue
            except Exception:
                pass


            # Check for obvious non-headers
            if text:
                # Short sentences ending with comma or starting with lowercase
                if (
                    text.endswith(",")
                    or (text[0].islower() and not text.startswith("●"))
                    or text.startswith("As ")
                    or text.startswith("For ")
                ):
                    # Definitely not a header
                    b.block_type = BlockTypes.Text
                    count += 1
                    continue

            # Empty blocks with no structure should be demoted
            if not text and (not hasattr(b, "structure") or not b.structure):
                b.block_type = BlockTypes.Text
                count += 1

        return count

    def _flag_suspicious_headers(self, blocks: List[Block]) -> int:
        """
        For all blocks that are still SectionHeaders, flag any that
        seem out of place based on content or context.
        """
        count = 0
        for i, block in enumerate(blocks):
            # Only process SectionHeaders
            if block.block_type == BlockTypes.SectionHeader:
                is_suspicious = False
                reasons = []
                text = getattr(block, "text", "").strip()

                # Rule 1: Header is immediately preceded by another header, figure, or table.
                # This is a strong indicator of a misclassification (e.g., a table caption).
                if i > 0:
                    prev_block = blocks[i - 1]
                    if prev_block.block_type in {
                        BlockTypes.SectionHeader,
                        BlockTypes.Figure,
                        BlockTypes.Table,
                    }:
                        # Exempt stacked headings when both look like legitimate headers
                        if not (prev_block.block_type == BlockTypes.SectionHeader and self._is_confident_header(prev_block) and self._is_confident_header(block)):
                            is_suspicious = True
                            reasons.append("preceded_by_header_figure_or_table")

                # Rule 2: Header text ends in a period (but not ...), suggesting a sentence.
                if text.endswith(".") and not text.endswith(".."):
                    if not any(__import__("re").fullmatch(p, text) for p in self.HEADER_PATTERNS):
                        is_suspicious = True
                        reasons.append("ends_with_period")

                # Rule 3: The header is all lowercase. Very unusual for a section title.
                if text and text.islower():
                    is_suspicious = True
                    reasons.append("all_lowercase")

                # If it's suspicious, but it's also a high-confidence header, we trust our confidence.
                if is_suspicious and not self._is_confident_header(block):
                    # Use the base Block class's suspicion fields
                    block.mark_suspicious(
                        reason="suspicious_header_pattern",
                        confidence=0.8,
                        metadata={"patterns": reasons},
                    )
                    count += 1
        return count


    def _demote_sentence_like_tables(self, blocks: List[Block]) -> int:
        """Demote tables that are clearly sentence-like text (not real tables)."""
        count = 0
        for b in blocks:
            if b.block_type != BlockTypes.Table:
                continue
            t = (getattr(b, "text", "") or "").strip()
            try:
                if t and self._looks_sentence(t):
                    b.block_type = BlockTypes.Text
                    count += 1
            except Exception:
                pass
        return count

    def _table_sanity_score(self, t: str) -> float:
        """Cheap score: lines/structure vs sentence-like patterns.
        Returns 0..1; lower means likely not a real table.
        """
        try:
            raw = (t or '').strip()
            if not raw:
                return 0.0
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            nlines = len(lines)
            # structural hints
            sep_mark = sum(1 for ln in lines if ('|' in ln) or (ln.count('  ')>=2))
            numeric_mark = sum(1 for ln in lines if any(ch.isdigit() for ch in ln))
            # sentence-like penalty on first line
            first = lines[0] if lines else raw
            def looks_sentence(u: str) -> bool:
                import re as _re
                words = u.split()
                letters = [ch for ch in u if ch.isalpha()]
                lower_ratio = (sum(ch.islower() for ch in letters)/len(letters)) if letters else 0.0
                has_term = u.endswith('.') or u.endswith(';') or u.endswith('?')
                verbs = {'is','are','was','were','be','been','being','has','have','had','can','could','should','may','might','will','shall','must','does','do','did'}
                has_verb = any(w.lower().strip(',.;:!?') in verbs for w in words)
                return (has_term or has_verb) and (len(words)>=4 or lower_ratio>=0.5)
            pen = 0.0
            if looks_sentence(first): pen += 0.6
            if nlines<=1: pen += 0.2
            # structure score
            struct = 0.0
            if nlines>=2: struct += 0.3
            if sep_mark>=1: struct += 0.3
            if numeric_mark>=2: struct += 0.2
            # final
            sc = max(0.0, min(1.0, struct - pen + 0.5))
            return sc
        except Exception:
            return 0.0

    def _demote_sentence_like_tables(self, blocks: List[Block]) -> int:
        """Demote tables that are clearly sentence-like or fail sanity score."""
        count = 0
        import os
        try:
            thr = float(os.getenv('STAGE02_TABLE_SCORE_MIN','0.6'))
        except Exception:
            thr = 0.6
        for b in blocks:
            if b.block_type != BlockTypes.Table:
                continue
            t = (getattr(b, 'text', '') or '').strip()
            try:
                if t:
                    score = self._table_sanity_score(t)
                    if score < thr:
                        b.block_type = BlockTypes.Text
                        count += 1
            except Exception:
                pass
        return count

    def _merge_orphaned_tables(self, blocks: List[Block]) -> int:
        """Glue consecutive Table blocks with ≤ 2 pt vertical gap."""
        count = 0
        i = 0
        while i < len(blocks) - 1:
            a, b = blocks[i], blocks[i + 1]
            if a.block_type != BlockTypes.Table or b.block_type != BlockTypes.Table:
                i += 1
                continue

            # --- FIX: Defensively check for polygon existence ---
            # A block might be classified as a Table but be empty or malformed.
            if not getattr(a, "polygon", None) or not getattr(b, "polygon", None):
                i += 1
                continue
            # --- END FIX ---

            # PolygonBox uses bbox array [x0, y0, x1, y1]
            gap = abs(a.polygon.bbox[3] - b.polygon.bbox[1])
            if gap < 2:
                if hasattr(a, "text") and hasattr(b, "text"):
                    a_text = getattr(a, "text", "") or ""
                    b_text = getattr(b, "text", "") or ""
                    a.text = a_text + "\n" + b_text
                # Union the polygons
                a.polygon = a.polygon.merge([b.polygon])
                del blocks[i + 1]
                count += 1
                # After a merge, re-evaluate the current block 'a' against the next one
                # without incrementing i.
                continue
            i += 1
        return count

    # -----------------------------------------------------------------
    # Helper methods
    # -----------------------------------------------------------------
    def _is_bold(self, b: Block, document: Document, fitz_doc=None) -> bool:
        try:
            spans = b.contained_blocks(document, (BlockTypes.Span,))
            if spans:
                s0 = spans[0]
                formats = getattr(s0, "formats", []) or []
                if "bold" in formats:
                    return True
                # Some providers expose font_weight or font name containing 'Bold'
                fw = getattr(s0, "font_weight", None)
                if fw is not None:
                    try:
                        if float(fw) >= 600:
                            return True
                    except Exception:
                        pass
                fname = getattr(s0, "font", "") or ""
                if "bold" in fname.lower():
                    return True
        except Exception:
            pass
        # Fallback via PyMuPDF if available (best-effort)
        # Not strictly required; return False by default
        return False

    def _is_confident_header(self, b: Block) -> bool:
        """Checks if a block is a high-confidence header based on text content."""
        txt = getattr(b, "text", "").strip()
        if not txt:
            return False

        # 1. Exact whitelist match
        if txt in self.HEADER_WHITELIST:
            return True

        # 2. Fuzzy whitelist match
        if any(
            fuzz.ratio(txt.lower(), w.lower()) >= self.WHITELIST_SIMILARITY
            for w in self.HEADER_WHITELIST
        ):
            return True

        # 3. Strong pattern match
        if any(re.fullmatch(p, txt) for p in self.HEADER_PATTERNS):
            return True

        return False

    def _looks_sentence(self, txt: str) -> bool:
        """Heuristic: a sentence-like line is not a section header.
        Avoid heavyweight deps; use light cues and optional NLTK when available.
        """
        if not txt:
            return False
        t = (txt or '').strip()
        # If it already matches confident header patterns, it's not a sentence here
        import re as _re
        for p in self.HEADER_PATTERNS:
            try:
                if _re.fullmatch(p, t):
                    return False
            except Exception:
                pass
        # Quick cues: terminal punctuation, length, lowercase ratio
        if t.endswith('.') or t.endswith(';') or t.endswith('?'):
            pass_mark = True
        else:
            pass_mark = False
        words = t.split()
        if len(words) >= 6:
            pass_mark = True or pass_mark
        # proportion of lowercase letters
        letters = [ch for ch in t if ch.isalpha()]
        lower_ratio = (sum(ch.islower() for ch in letters)/len(letters)) if letters else 0.0
        if lower_ratio >= 0.5:
            lower_mark = True
        else:
            lower_mark = False
        # verb cue list (cheap)
        VERBS = {'is','are','was','were','be','been','being','has','have','had','can','could','should','may','might','will','shall','must','does','do','did'}
        verb_mark = any(w.lower().strip(',.;:!?') in VERBS for w in words)
        # Optional NLTK sentence tokenizer
        try:
            import nltk
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                nltk.download('punkt', quiet=True)
            sents = nltk.tokenize.sent_tokenize(t)
            if len(sents) >= 1 and (sents[0].endswith('.') or len(sents[0].split()) >= 6):
                punkt_mark = True
            else:
                punkt_mark = False
        except Exception:
            punkt_mark = False
        score = sum([1 if pass_mark else 0, 1 if lower_mark else 0, 1 if verb_mark else 0, 1 if punkt_mark else 0])
        return score >= 2


    def _same_font(self, a: Block, b: Block, document: Document, fitz_doc=None) -> bool:
        """Compare first-span font sizes of two blocks.

        Preference order: PyMuPDF (if available) → provider spans → validation_metadata fallback.
        """

        def _first_span_font_from_doc(block: Block):
            try:
                spans = block.contained_blocks(document, (BlockTypes.Span,))
                if spans:
                    s0 = spans[0]
                    return {
                        "name": getattr(s0, "font", None),
                        "size": float(getattr(s0, "font_size", 0) or 0),
                    }
            except Exception:
                pass
            return None

        def _first_span_font_from_pymupdf(block: Block):
            if fitz_doc is None:
                return None
            try:
                page = fitz_doc[block.page_id or 0]
                bbox = (
                    getattr(block, "polygon", None).bbox
                    if getattr(block, "polygon", None)
                    else None
                )
                if not bbox:
                    return None
                x0, y0, x1, y1 = bbox

                def _overlap(b1, b2):
                    ax0, ay0, ax1, ay1 = b1
                    bx0, by0, bx1, by1 = b2
                    if ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0:
                        return False
                    return True

                td = page.get_text("dict")
                for blk in td.get("blocks", []):
                    if blk.get("type") != 0:
                        continue
                    bb = blk.get("bbox")
                    if not bb or not _overlap(bb, bbox):
                        continue
                    for line in blk.get("lines", []):
                        for span in line.get("spans", []):
                            name = span.get("font")
                            size = span.get("size")
                            if name is not None and size is not None:
                                return {"name": name, "size": float(size)}
                return None
            except Exception:
                return None

        def _first_span_font(block: Block):
            # Prefer PyMuPDF when available
            fsf = _first_span_font_from_pymupdf(block)
            if fsf:
                return fsf
            # Fallback to provider spans
            fsf = _first_span_font_from_doc(block)
            if fsf:
                return fsf
            # Final fallback: validation_metadata (legacy)
            vm = getattr(block, "validation_metadata", {}) or {}
            fsf = vm.get("first_span_font")
            if isinstance(fsf, dict) and "size" in fsf:
                try:
                    fsf["size"] = float(fsf["size"] or 0)
                except Exception:
                    fsf["size"] = 0.0
                return fsf
            return {"name": None, "size": 0.0}

        f1 = _first_span_font(a)
        f2 = _first_span_font(b)
        try:
            return abs(float(f1.get("size", 0) or 0) - float(f2.get("size", 0) or 0)) < 1.0
        except Exception:
            # If we cannot compute, assume same to avoid over-merging
            return True

    @staticmethod
    def _looks_headerish(txt: str) -> bool:
        return bool(
            re.match(r"^\d+(?:\d+)*\s+\S+.*$", txt) or txt.isupper() or len(txt.split()) < 10
        )


# =================================================================
# DEBUGGING BLOCK
# To run, execute this file directly from the project root:
# python -m src.extractor.core.processors.suspicious_header_fixer
# =================================================================
if __name__ == "__main__":
    from dataclasses import dataclass
    from typing import Optional

    # --- Mocks for required data structures ---
    # These lightweight mocks simulate the real schema objects for isolated testing.

    @dataclass
    class MockPolygon:
        y0: float
        y1: float

        def union(self, other: "MockPolygon") -> "MockPolygon":
            """A simplified union for testing vertical merging."""
            return MockPolygon(y0=min(self.y0, other.y0), y1=max(self.y1, other.y1))

    # A debug version of the Block class with just the necessary attributes.
    class DebugBlock:
        def __init__(
            self,
            id: int,
            block_type: BlockTypes,
            text: str = "",
            polygon: Optional[MockPolygon] = None,
            validation_metadata: Optional[dict] = None,
        ):
            self.id = id
            self.block_type = block_type
            self.text = text
            self.polygon = polygon
            self.validation_metadata = (
                validation_metadata if validation_metadata is not None else {}
            )
            # The processor expects this field to exist, so we initialize it.
            self.suspicious_header = False

        def __repr__(self):
            return f"Block(id={self.id}, type='{self.block_type.value}')"

    # --- Helper function to display block states ---
    def print_blocks_state(title: str, blocks: list[DebugBlock]):
        print(f"\n{'='*10} {title.upper()} {'='*10}")
        for i, b in enumerate(blocks):
            suspicious_flag = " [SUSPICIOUS]" if getattr(b, "suspicious_header", False) else ""
            text_preview = repr((getattr(b, "text", "") or "N/A")[:45])
            print(
                f"  {i+1:02d}. ID={b.id:<2} Type={b.block_type.value:<15} Text={text_preview:<50}{suspicious_flag}"
            )
        print("=" * (22 + len(title)))

    # --- Main debug execution ---
    def run_debug_test():
        print(">>> Running SuspiciousHeaderFixer in self-test debug mode <<<")

        # 1. Define a list of mock blocks to test various scenarios.
        mock_blocks = [
            # Case 1: A confident, whitelisted header. Should not be changed.
            DebugBlock(
                id=1,
                block_type=BlockTypes.SectionHeader,
                text="Introduction",
                polygon=MockPolygon(y0=50, y1=60),
            ),
            # Case 2: A header that should be demoted (looks like a sentence).
            DebugBlock(
                id=2,
                block_type=BlockTypes.SectionHeader,
                text="This is not a real header.",
                polygon=MockPolygon(y0=80, y1=90),
            ),
            # Case 3 & 4: A split header that needs merging.
            DebugBlock(
                id=3,
                block_type=BlockTypes.Text,
                text="2.1 A Split Header (",
                validation_metadata={"first_span_font": {"size": 14}},
                polygon=MockPolygon(y0=100, y1=110),
            ),
            DebugBlock(
                id=4,
                block_type=BlockTypes.Text,
                text="Continued)",
                validation_metadata={"first_span_font": {"size": 14}},
                polygon=MockPolygon(y0=111, y1=121),
            ),
            # Case 5: A confident ALL-CAPS header. Should not be changed.
            DebugBlock(
                id=5,
                block_type=BlockTypes.SectionHeader,
                text="METHODOLOGY",
                polygon=MockPolygon(y0=140, y1=150),
            ),
            # Case 6: A table to provide context for the next block.
            DebugBlock(
                id=6,
                block_type=BlockTypes.Table,
                text="Table 1...",
                polygon=MockPolygon(y0=160, y1=200),
            ),
            # Case 7: A header immediately following a table. Should be flagged as suspicious.
            DebugBlock(
                id=7,
                block_type=BlockTypes.SectionHeader,
                text="Possibly a table title",
                polygon=MockPolygon(y0=210, y1=220),
            ),
            # Case 8 & 9: Two adjacent tables that should be merged.
            DebugBlock(
                id=8,
                block_type=BlockTypes.Table,
                text="Table part A.",
                polygon=MockPolygon(y0=240, y1=260),
            ),
            DebugBlock(
                id=9,
                block_type=BlockTypes.Table,
                text="Table part B.",
                polygon=MockPolygon(y0=261.5, y1=280),
            ),  # 1.5pt gap
            # Case 10 (THE BUG): A valid table followed by a table with no polygon. Should NOT crash.
            DebugBlock(
                id=10,
                block_type=BlockTypes.Table,
                text="This table is fine.",
                polygon=MockPolygon(y0=300, y1=320),
            ),
            DebugBlock(
                id=11,
                block_type=BlockTypes.Table,
                text="This one is missing geometry.",
                polygon=None,
            ),
        ]

        # 2. Assemble the mock document structure.
        mock_page = type("MockPage", (), {"children": mock_blocks})
        mock_document = type("MockDocument", (), {"pages": [mock_page]})

        # 3. Print the initial state.
        print_blocks_state("Initial State", mock_page.children)

        # 4. Initialize and run the processor.
        print("\n[INFO] Running processor...")
        fixer = SuspiciousHeaderFixer()
        fixed_document = fixer(mock_document)
        print("[INFO] Processor finished.")

        # 5. Print the final state to see the changes.
        print_blocks_state("Final State", fixed_document.pages[0].children)
        print("\n>>> Debug run complete. Check 'Final State' for expected changes. <<<")

    # Execute the debug test when the script is run directly.
    run_debug_test()
