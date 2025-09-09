# OCR Architecture in the Extractor Project

## Overview

The extractor doesn't just do simple OCR - it performs **selective intelligence** by combining visual layout analysis with embedded PDF text extraction. Here's how it works:

## The Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         PDF Document                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────┐        ┌───────────────────────────┐    │
│  │  Visual Layer     │        │  Text Layer (Embedded)     │    │
│  │  (What you see)   │        │  (PDF text objects)        │    │
│  │                   │        │                             │    │
│  │  ╔═══════════╗    │        │  "4.1.5.4. BHT (Branch..." │    │
│  │  ║  Title    ║    │        │  x: 70.5, y: 81.9          │    │
│  │  ╚═══════════╝    │        │                             │    │
│  │                   │        │  "BHT is implemented as..." │    │
│  │  ┌─────────────┐  │        │  x: 70.5, y: 116.25        │    │
│  │  │   Text      │  │        │                             │    │
│  │  └─────────────┘  │        │  [No text for figure area]  │    │
│  │                   │        │                             │    │
│  │  ┌─────────────┐  │        │  "The BHT is never..."     │    │
│  │  │   Figure    │  │        │  x: 72.5, y: 575.8         │    │
│  │  │  [Image]    │  │        │                             │    │
│  │  └─────────────┘  │        │  [Table text fragmented]    │    │
│  │                   │        │                             │    │
│  │  ┌─────────────┐  │        │                             │    │
│  │  │   Table     │  │        │                             │    │
│  │  └─────────────┘  │        │                             │    │
│  └───────────────────┘        └───────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                    ↓                              ↓
         ┌──────────────────┐            ┌──────────────────┐
         │  Surya Layout    │            │  PDF Extraction  │
         │  Detection       │            │  (PyMuPDF)       │
         └──────────────────┘            └──────────────────┘
                    ↓                              ↓
```

## Step-by-Step Process

### 1. **Dual Extraction**
The system performs two parallel extractions:

#### Visual Analysis (Surya Layout Detection)
```python
# Surya sees the visual structure
{
    "detections": [
        {
            "bbox": [70.5, 81.9, 315.0, 95.5],
            "label": "Title",
            "score": 0.95
        },
        {
            "bbox": [49.5, 334.4, 564.3, 498.6],
            "label": "Figure",
            "score": 0.78
        }
    ]
}
```

#### PDF Text Extraction
```python
# PyMuPDF extracts embedded text
[
    {
        "text": "4.1.5.4. BHT (Branch History Table) submodule",
        "x0": 70.5, "y0": 81.9,
        "x1": 315.0, "y1": 95.5
    }
]
```

### 2. **Bounding Box Intersection**
The magic happens through `matrix_intersection_area`:

```python
def matrix_intersection_area(boxes1, boxes2):
    # Calculate intersection area between all box pairs
    min_x = np.maximum(boxes1[..., 0], boxes2[..., 0])
    min_y = np.maximum(boxes1[..., 1], boxes2[..., 1])
    max_x = np.minimum(boxes1[..., 2], boxes2[..., 2])
    max_y = np.minimum(boxes1[..., 3], boxes2[..., 3])
    
    width = np.maximum(0, max_x - min_x)
    height = np.maximum(0, max_y - min_y)
    
    return width * height  # Intersection area matrix
```

### 3. **Decision Tree for Each Region**

```
For each Surya detection:
│
├─> Is there PDF text at these coordinates?
│   │
│   ├─> YES: Check text quality
│   │   │
│   │   ├─> Complete & reliable → Use PDF text
│   │   │
│   │   └─> Fragmented/suspicious → Run OCR
│   │
│   └─> NO: This is likely an image/figure
│       │
│       ├─> If labeled "Figure" → Extract as image block
│       │
│       └─> If labeled "Table" → Run table-specific OCR
```

### 4. **Selective OCR Activation**

OCR is NOT always used. It's activated selectively:

- **Figure regions with no text**: Correctly identified as images
- **Tables with fragmented text**: OCR extracts proper structure
- **Scanned PDFs**: Full OCR on all regions
- **Suspicious text**: When PDF text seems corrupted

### 5. **Task-Based Architecture**

Marker uses different extraction strategies:

```python
# From marker's internals
if has_good_pdf_text:
    task = "text_with_boxes"  # Use PDF text + layout
elif is_scanned:
    task = "ocr_with_boxes"   # Full OCR + layout
else:
    task = "ocr_without_boxes" # Pure OCR (rare)
```

## Real Example from BHT PDF

```
Visual Detection: "Title" at [70.5, 81.9, 315.0, 95.5]
     ↓
PDF Text Found: "4.1.5.4. BHT (Branch History Table) submodule"
     ↓
Bbox Match: 100% overlap!
     ↓
Decision: Use PDF text (perfect match)
     ↓
Output: SectionHeader block with PDF text

---

Visual Detection: "Figure" at [49.5, 334.4, 564.3, 498.6]
     ↓
PDF Text Found: None
     ↓
Decision: This is an image
     ↓
Output: Figure block (no OCR needed)

---

Visual Detection: "Table" at [72.0, 611.0, 541.0, 686.0]
     ↓
PDF Text Found: Fragmented pieces
     ↓
Decision: Run table-specific OCR
     ↓
Output: Table block with OCR'd structure
```

## Key Insights

1. **It's NOT Simple OCR**: The system intelligently chooses between embedded text and visual OCR
2. **Always Visual First**: Surya layout detection runs on EVERY page regardless of text presence
3. **Bbox Coordinates are Key**: Everything is matched by spatial intersection
4. **Quality Assessment**: The system evaluates text quality before deciding to use OCR
5. **Specialized Models**: Different Surya models for different tasks (layout, OCR, tables, error detection)

## The Models

```python
{
    "layout_model": LayoutPredictor(),      # Visual structure detection
    "recognition_model": RecognitionPredictor(), # Text OCR
    "table_rec_model": TableRecPredictor(), # Table structure
    "detection_model": DetectionPredictor(), # Text line detection
    "ocr_error_model": OCRErrorPredictor(), # Quality assessment
}
```

This architecture allows the extractor to handle:
- Native PDFs with perfect text
- Scanned documents needing full OCR
- Mixed documents (some text, some images)
- Corrupted PDFs with unreliable text
- Complex layouts with tables and figures

The beauty is that it adapts to each document's characteristics, using the best extraction method for each region.