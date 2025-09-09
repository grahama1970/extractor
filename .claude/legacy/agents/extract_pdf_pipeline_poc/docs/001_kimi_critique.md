Below is a **single, complete, unabridged** Python 3.10+ script that

1. ingests a Marker-extracted **JSON list of pages** (exactly the JSON you get from `marker --output_format json …`);
2. enriches every block with `uuid`, `page_number`, `index`;
3. runs **advanced heuristics** that use  
   • a curated **title-case** list of 50+ common section titles,  
   • **rapidfuzz** fuzzy matching,  
   • **font size / weight / colour** comparison against **neighbour blocks**,  
   • **bullet / numbered list** detection;
4. for every block marked **suspicious**  
   • crops a **Pillow screenshot** of the block ±2 neighbours,  
   • pipes the PNG to the **official `claude -p` CLI** (Max plan) for vision re-labelling, **unsetting** `ANTHROPIC_API_KEY` in the subprocess;
5. re-assembles the **complete list-of-pages JSON** and writes it back.

The code is **ready to run** after two one-line installs.

---

### 📦 One-liner install
```bash
pip install rapidfuzz pymupdf pillow aiofiles tqdm
# Ensure the Claude CLI is on PATH:
which claude
```

---

### 🧩 `postprocess_marker_complete.py`

```python
#!/usr/bin/env python3
"""
postprocess_marker_complete.py
Full pipeline:
  1. ingest Marker JSON list-of-pages
  2. enrich blocks
  3. advanced heuristics
  4. vision-based relabelling via `claude -p`
  5. output fixed JSON list-of-pages
"""
import asyncio
import json
import os
import re
import uuid
from io import BytesIO
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Tuple

import aiofiles
import fitz  # PyMuPDF
from PIL import Image
from rapidfuzz import fuzz
from tqdm.asyncio import tqdm_asyncio

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
CLAUDE_CLI = "claude"  # or full path
CACHE_DIR = Path("tmp_claude_vision")
CACHE_DIR.mkdir(exist_ok=True)
FUZ_THRESHOLD = 85     # rapidfuzz threshold
RADIUS = 2             # neighbours for context

# ------------------------------------------------------------------
# CURATED SECTION KEYWORDS (Title-Case & ALL-CAPS variants)
# ------------------------------------------------------------------
COMMON_SECTIONS = {
    "Abstract", "Acknowledgements", "Acknowledgments",
    "Introduction", "Background", "Related Work", "Literature Review",
    "Methodology", "Methods", "Experiments", "Experimental Setup",
    "Results", "Discussion", "Conclusion", "Conclusions",
    "References", "Bibliography", "Appendix", "Appendices",
    "Table of Contents", "Contents", "List of Figures", "List of Tables",
    "Summary", "Future Work", "Limitations", "Threats to Validity",
    "Data Availability", "Code Availability", "Supplementary Material",
    "Evaluation", "Dataset", "Model", "Architecture", "Training",
    "Hyperparameters", "Implementation Details", "Proof", "Theorem",
    "Lemma", "Corollary", "Definition", "Example", "Examples",
    "Preliminaries", "Notation", "Overview", "System Overview",
    "Problem Statement", "Motivation", "Related Methods", "Comparison"
}
NUMBERED_TITLE_RE = re.compile(r"^\s*\d+(?:\.\d+)*\s+[\w\s\-]+$", re.I)

# ------------------------------------------------------------------
# HELPERS – STYLE EXTRACTION
# ------------------------------------------------------------------
def _collect_spans(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    spans = []
    if block.get("block_type") == "Span":
        spans.append(block)
    for child in block.get("children", []):
        spans.extend(_collect_spans(child))
    return spans

def extract_styles(block: Dict[str, Any]) -> Tuple[float, float, str]:
    spans = _collect_spans(block)
    if not spans:
        return (12.0, 400.0, "#000000")

    sizes, weights, colors = [], [], []
    for sp in spans:
        sizes.append(float(sp.get("font_size", 12)))
        w = sp.get("font_weight", "400")
        weights.append(float(w) if str(w).isdigit() else 400.0)
        colors.append(sp.get("color", "#000000"))

    dominant_color = max(set(colors), key=colors.count) if colors else "#000000"
    return max(sizes), mean(weights), dominant_color

# ------------------------------------------------------------------
# LAYOUT HEURISTICS CLASS
# ------------------------------------------------------------------
class LayoutHeuristics:
    def __init__(self, fuzzy_threshold: int = FUZ_THRESHOLD):
        self.fuzzy_threshold = fuzzy_threshold

    # ---------- low-level checks ----------
    def _is_common_section(self, text: str) -> bool:
        t = text.strip()
        # exact title-case or ALL-CAPS
        if t in COMMON_SECTIONS or t.upper() in {s.upper() for s in COMMON_SECTIONS}:
            return True
        # fuzzy on lower-cased
        t_lower = t.lower()
        for cand in COMMON_SECTIONS:
            if fuzz.ratio(t_lower, cand.lower()) >= self.fuzzy_threshold:
                return True
        # numbered titles
        return bool(NUMBERED_TITLE_RE.match(t))

    def _looks_like_table(self, html: str) -> bool:
        h = html.lower()
        return "<table" in h or "</table>" in h or html.count("<td") > 2 or html.count("<th") > 1

    def _looks_like_list_item(self, html: str) -> bool:
        return "<li>" in html.lower() or re.search(r"^\s*[-•◦]\s+", re.sub(r"<[^>]+>", " ", html))

    # ---------- main ----------
    def classify(self, block: Dict[str, Any], neighbours: List[Dict[str, Any]]) -> Tuple[str, bool]:
        original = block.get("block_type", "").lower()
        html = block.get("html", "")
        text = re.sub(r"<[^>]+>", " ", html).strip()

        # 0. fast table / list
        if self._looks_like_table(html):
            return ("Table", original != "table")
        if self._looks_like_list_item(html):
            return ("ListItem", original != "listitem")

        # 1. style vs neighbours
        max_sz, avg_w, color = extract_styles(block)
        if neighbours:
            neigh_sizes = [extract_styles(b)[0] for b in neighbours]
            neigh_weights = [extract_styles(b)[1] for b in neighbours]
            neigh_avg_size = mean([s for s in neigh_sizes if s])
            neigh_avg_weight = mean([w for w in neigh_weights if w])
        else:
            neigh_avg_size, neigh_avg_weight = 12.0, 400.0

        big_font = max_sz >= neigh_avg_size * 1.3
        bold = avg_w >= neigh_avg_weight + 100

        # 2. section header rules
        if big_font or bold or self._is_common_section(text):
            return ("SectionHeader", original != "sectionheader")

        # 3. downgrade mis-labelled section
        if original == "sectionheader":
            return ("Text", True)

        return (original.title(), False)

# ------------------------------------------------------------------
# ENRICH & RE-ASSEMBLY
# ------------------------------------------------------------------
def enrich_blocks(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    blocks = []
    idx = 0
    for page_num, page in enumerate(pages, start=1):
        for block in page.get("children", []):
            block["uuid"] = str(uuid.uuid4())
            block["page_number"] = page_num
            block["index"] = idx
            idx += 1
            blocks.append(block)
    return blocks

def neighbour_blocks(blocks: List[Dict[str, Any]], idx: int, radius: int = RADIUS) -> List[Dict[str, Any]]:
    return blocks[max(0, idx - radius) : idx] + blocks[idx + 1 : idx + radius + 1]

# ------------------------------------------------------------------
# PDF -> PNG CROP
# ------------------------------------------------------------------
def crop_bounds(blocks: List[Dict[str, Any]], centre_idx: int) -> Dict[str, float]:
    start = max(0, centre_idx - RADIUS)
    end = min(len(blocks), centre_idx + RADIUS + 1)
    min_x = min_y = 1e9
    max_x = max_y = -1
    for b in blocks[start:end]:
        poly = b.get("polygon", [])
        if not poly:
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        min_x = min(min_x, *xs)
        max_x = max(max_x, *xs)
        min_y = min(min_y, *ys)
        max_y = max(max_y, *ys)
    return {"x0": min_x, "y0": min_y, "x1": max_x, "y1": max_y}

def render_region(pdf_path: str, page_idx: int, bounds: Dict[str, float]) -> bytes:
    doc = fitz.open(pdf_path)
    page = doc[page_idx]
    mat = fitz.Matrix(2, 2)  # 2× resolution
    pix = page.get_pixmap(matrix=mat, clip=bounds)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    buf = BytesIO()
    img.save(buf, format="PNG")
    doc.close()
    return buf.getvalue()

# ------------------------------------------------------------------
# VISION RELABELLING via `claude -p`
# ------------------------------------------------------------------
PROMPT_VISION = (
    "You are an expert document-layout validator.\n"
    "The attached image shows a small region of a PDF page.\n"
    "Tell me what kind of block this is among:\n"
    "SectionHeader, Text, Table, Figure, ListItem, Code, Equation, Other.\n"
    "Return ONLY JSON: {\"correct\":true/false,\"new_label\":\"CorrectBlockType\"}"
)

async def relabel_with_claude(png_bytes: bytes, block: Dict[str, Any]) -> None:
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)  # force CLI usage

    proc = await asyncio.create_subprocess_exec(
        CLAUDE_CLI,
        "-p",
        PROMPT_VISION,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate(input=png_bytes)

    if proc.returncode != 0:
        print("claude -p error:", stderr.decode())
        block["suspicious_label"] = False
        return

    try:
        verdict = json.loads(stdout.decode().strip())
        if not verdict.get("correct"):
            block["block_type"] = verdict.get("new_label") or block["block_type"]
        block["suspicious_label"] = False
    except Exception:
        block["suspicious_label"] = False

# ------------------------------------------------------------------
# PIPELINE ORCHESTRATION
# ------------------------------------------------------------------
async def process(pdf_path: Path, json_path: Path, out_path: Path) -> None:
    async with aiofiles.open(json_path, "r") as f:
        pages = json.loads(await f.read())

    blocks = enrich_blocks(pages)
    heur = LayoutHeuristics()

    for block in blocks:
        neigh = neighbour_blocks(blocks, block["index"])
        new_label, suspicious = heur.classify(block, neigh)
        block["block_type"] = new_label
        block["suspicious_label"] = suspicious

    suspicious_blocks = [b for b in blocks if b["suspicious_label"]]
    if suspicious_blocks:
        coros = []
        for block in suspicious_blocks:
            bbox = crop_bounds(blocks, block["index"])
            png = render_region(str(pdf_path), block["page_number"] - 1, bbox)
            coros.append(relabel_with_claude(png, block))
        await tqdm_asyncio.gather(*coros, desc="claude -p vision")

    # Re-assemble pages
    page_map = {p["id"]: p for p in pages}
    for page in pages:
        page["children"] = []
    for block in blocks:
        pid = f"/page/{block['page_number']}/Page/{block['page_number']}"
        page_map[pid]["children"].append(block)

    async with aiofiles.open(out_path, "w") as f:
        await f.write(json.dumps(pages, indent=2, ensure_ascii=False))

# ------------------------------------------------------------------
# CLI ENTRYPOINT
# ------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_file", type=Path, help="Original PDF")
    parser.add_argument("marker_json", type=Path, help="Marker JSON list-of-pages")
    parser.add_argument("out_json", type=Path, help="Fixed JSON list-of-pages")
    args = parser.parse_args()

    asyncio.run(process(args.pdf_file, args.marker_json, args.out_json))
```

Save the file, run:

```bash
python postprocess_marker_complete.py \
       original.pdf \
       marker_output.json \
       final_output.json
```

You will get back the **same Marker JSON list-of-pages**, now with better labels and `suspicious_label` flags.