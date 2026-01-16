# Extractor - Self-Correcting Agentic Document Processing System

Advanced multi-format document extraction system with self-correcting AI agents, annotation-guided learning, and continuous improvement through metadata accumulation. Handles PDFs, DOCX, PPTX, XML, HTML, and more with enterprise-grade accuracy.

## 🚀 Key Innovation: Self-Correcting Multi-Stage Pipeline

Unlike traditional extraction systems, this uses a **10-stage pipeline** where each stage contributes metadata, and AI agents make intelligent decisions based on accumulated knowledge.

## 🎯 Quick Start

The Extractor comes with a smart Agent Interface that handles format detection and calibration for you.

### Single Document (Interactive)

To extract any document, simply run:

```bash
./run.sh extract my_document.pdf
```

- **Structured Files (HTML, DOCX, XML)**: The agent extracts them immediately (Frictionless).
- **PDFs (Unknown Layouts)**: The agent pauses and asks for guidance if it doesn't recognize the format.

**Example Interactive Handshake:**

```
⚠️  Unknown Document Layout: 'my_document.pdf'.

[ Scientific ]
[1] ★ Academic papers (2-column, math)

[ Engineering ]
[2] Requirements spec (Boeing/BHT style)

[ Standard ]
[3] Custom Calibration
[4] Fast Mode (Skip Calibration)

Select an option [1]:
```

Selecting a **preset** (1 or 2) calibrates the pipeline and extracts your document with high accuracy.

### Smart Batch Processing (Auto-Detect)

To process a folder of mixed documents without interruption, use the `--auto` flag. The agent will scan each file's content and automatically select the best calibration preset.

```bash
# Process all PDFs in the current directory
for f in *.pdf; do
  ./run.sh extract "$f" --auto
done
```

**What happens?**

- `paper.pdf` -> Detects "Abstract/References" -> Uses [ArXiv] preset -> High Accuracy.
- `reqs.pdf` -> Detects "REQ-001" -> Uses [Requirements] preset -> High Accuracy.
- `meme.png` -> No match -> Skips or uses Fast Mode.

### Extraction Modes

```bash
# Auto mode (default): Step 00 decides based on complexity
./run.sh extract paper.pdf

# Fast mode: PyMuPDF only, no ML/LLM
./run.sh extract paper.pdf --mode fast

# Accurate mode: Uses LLM for complex extraction (tables, math)
./run.sh extract paper.pdf --mode accurate
```

## 📊 Supported Formats & Accuracy

| Format   | Method        | Profile (Preset) | Accuracy Goal    |
| -------- | ------------- | ---------------- | ---------------- |
| **PDF**  | Marker + AI   | ArXiv, Boeing    | 99% (Calibrated) |
| **DOCX** | Native XML    | Fast Path        | 100%             |
| **HTML** | BeautifulSoup | Fast Path        | 100%             |
| **XML**  | Native parser | Fast Path        | 100%             |
| **PPTX** | Native XML    | Fast Path        | 95%              |

## 🔌 API Usage

You can also use the Python API for integration:

```python
from extractor import ExtractorLogic
from pathlib import Path

async def main():
    logic = ExtractorLogic()

    # 1. Auto-Detect preset
    preset = logic.detect_preset(Path("doc.pdf"))

    # 2. Calibrate & Extract
    if preset:
        await logic.calibrate_pdf(Path("doc.pdf"), preset=preset)
        await logic.extract_real(Path("doc.pdf"), strict=True, use_llm=True)
    else:
        # Fallback (fast mode)
        await logic.extract_real(Path("doc.pdf"), strict=False, use_llm=False)
```

## 🧠 Architecture: Preset-First Methodology

For complex PDFs, we use a **Preset-First** approach:

1. **Profile**: Step 00 analyzes the PDF (domain, layout, elements).
2. **Match**: Find the closest preset in the registry (arxiv, requirements_spec).
3. **Calibrate**: Tune the pipeline until it perfectly extracts a test fixture.
4. **Extract**: Apply those tuned settings to your real document.

This ensures **provenance** and **reliability** that generic "chat with PDF" tools cannot match.

### Terminology

| Term        | Definition                                                 |
| :---------- | :--------------------------------------------------------- |
| **Preset**  | Extraction configuration for a document type (user-facing) |
| **Fixture** | Internal test case for verification (developer-facing)     |

## 📝 License

Apache License 2.0 - See [LICENSE](LICENSE) for details.
