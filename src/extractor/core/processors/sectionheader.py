import os
import re
import warnings
from typing import Annotated, Dict, List

import numpy as np
from sklearn.cluster import KMeans
from sklearn.exceptions import ConvergenceWarning

from extractor.core.processors import BaseProcessor
from extractor.core.schema import BlockTypes
from extractor.core.schema.document import Document

# Ignore sklearn warning about not converging
warnings.filterwarnings("ignore", category=ConvergenceWarning)


class SectionHeaderProcessor(BaseProcessor):
    """
    A processor for recognizing section headers in the document.
    """

    block_types = (BlockTypes.SectionHeader,)
    level_count: Annotated[
        int,
        "The number of levels to use for headings.",
    ] = 4
    merge_threshold: Annotated[
        float,
        "The minimum gap between headings to consider them part of the same group.",
    ] = 0.25
    default_level: Annotated[
        int,
        "The default heading level to use if no heading level is detected.",
    ] = 2
    height_tolerance: Annotated[
        float,
        "The minimum height of a heading to consider it a heading.",
    ] = 0.99

    def __call__(self, document: Document):
        line_heights: Dict[int, float] = {}
        for page in document.pages:
            # Iterate children to grab all section headers
            for block in page.children:
                if block.block_type not in self.block_types:
                    continue
                if block.structure is not None:
                    line_heights[block.id] = block.line_height(document)
                else:
                    line_heights[block.id] = 0
                    block.ignore_for_output = True  # Don't output an empty section header

        flat_line_heights = list(line_heights.values())
        heading_ranges = self.bucket_headings(flat_line_heights)

        for page in document.pages:
            for block in page.children:
                if block.block_type not in self.block_types:
                    continue
                block_height = line_heights.get(block.id, 0)
                if block_height > 0:
                    for idx, (min_height, max_height) in enumerate(heading_ranges):
                        if block_height >= min_height * self.height_tolerance:
                            block.heading_level = idx + 1
                            break
                if block.heading_level is None:
                    block.heading_level = self.default_level
                score = self._header_score(block, document)
                try:
                    setattr(block, "header_score", score)
                except Exception:
                    pass

    def bucket_headings(self, line_heights: List[float], num_levels=4):
        if len(line_heights) <= self.level_count:
            return []

        data = np.asarray(line_heights).reshape(-1, 1)
        labels = KMeans(n_clusters=num_levels, random_state=0, n_init="auto").fit_predict(data)
        data_labels = np.concatenate([data, labels.reshape(-1, 1)], axis=1)
        data_labels = np.sort(data_labels, axis=0)

        cluster_means = {
            int(label): float(np.mean(data_labels[data_labels[:, 1] == label, 0]))
            for label in np.unique(labels)
        }
        label_max = None
        label_min = None
        heading_ranges = []
        prev_cluster = None
        for row in data_labels:
            value, label = row
            value = float(value)
            label = int(label)
            if prev_cluster is not None and label != prev_cluster:
                prev_cluster_mean = cluster_means[prev_cluster]
                cluster_mean = cluster_means[label]
                if cluster_mean * self.merge_threshold < prev_cluster_mean:
                    heading_ranges.append((label_min, label_max))
                    label_min = None
                    label_max = None

            label_min = value if label_min is None else min(label_min, value)
            label_max = value if label_max is None else max(label_max, value)
            prev_cluster = label

        if label_min is not None:
            heading_ranges.append((label_min, label_max))

        heading_ranges = sorted(heading_ranges, reverse=True)

        return heading_ranges


    # ----------------------- helpers -----------------------
    def _text(self, block, document: Document) -> str:
        try:
            if hasattr(block, "raw_text"):
                t = block.raw_text(document)
            else:
                t = getattr(block, "text", "")
            return (t or "").strip()
        except Exception:
            return (getattr(block, "text", "") or "").strip()

    def _numbering_depth(self, t: str) -> int:
        t = (t or "").strip()
        if re.match(r"^\d+(?:[.\-]\d+)*(?:[.)])?\s+\S", t):
            core = t.split()[0]
            parts = re.split(r"[.\-]", re.sub(r"[.)]$", "", core))
            return max(1, len([p for p in parts if p]))
        if re.match(r"^[IVXLCDM]+[.)]?\s+\S", t):
            return 1
        return 0

    def _is_all_caps(self, t: str) -> bool:
        letters = [ch for ch in t if ch.isalpha()]
        if not letters:
            return False
        return all(ch.isupper() for ch in letters)

    def _is_bold(self, block, document: Document) -> bool:
        try:
            spans = block.contained_blocks(document, (BlockTypes.Span,))
            if spans:
                s0 = spans[0]
                formats = getattr(s0, "formats", []) or []
                if "bold" in formats:
                    return True
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
        return False

    def _looks_sentence(self, t: str) -> bool:
        t = (t or "").strip()
        if not t:
            return False
        if re.match(r"^\d+(?:[.\-]\d+)*(?:[.)])?\s+\S", t) or re.match(r"^[IVXLCDM]+[.)]?\s+\S", t):
            return False
        words = t.split()
        letters = [ch for ch in t if ch.isalpha()]
        lower_ratio = (sum(ch.islower() for ch in letters) / len(letters)) if letters else 0.0
        has_terminal = t.endswith('.') or t.endswith(';') or t.endswith('?')
        common_verbs = {"is","are","was","were","be","been","being","has","have","had","can","could","should","may","might","will","shall","must","does","do","did"}
        has_verb = any(w.lower().strip(',.;:!?') in common_verbs for w in words)
        score = 0
        if has_terminal:
            score += 1
        if len(words) >= 6:
            score += 1
        if lower_ratio >= 0.5:
            score += 1
        if has_verb:
            score += 1
        return score >= 2

    def _header_score(self, block, document: Document) -> float:
        t = self._text(block, document)
        if not t:
            return 0.0
        score = 0.0
        depth = self._numbering_depth(t)
        if depth >= 1:
            score += 0.35
            if depth >= 2:
                score += 0.10
        if self._is_all_caps(t):
            score += 0.25
        if self._is_bold(block, document):
            score += 0.15
        try:
            if getattr(block, "polygon", None) and getattr(block.polygon, "bbox", None):
                _, y0, _, _ = block.polygon.bbox
                if y0 <= 100:
                    score += 0.10
        except Exception:
            pass
        if t.endswith(':') and self._is_bold(block, document):
            score -= 0.30
        if self._looks_sentence(t):
            score -= 0.40
        return max(0.0, min(1.0, score))
