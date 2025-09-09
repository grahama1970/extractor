# Surya Label Mapping in the Extractor

## Yes, you're absolutely correct!

Surya converts PDF pages into labeled regions with bounding box coordinates. Here's exactly how it works:

## Surya's Output Labels

Surya's LayoutPredictor outputs visual labels like:
- `"Title"`
- `"Text"`
- `"Figure"`
- `"Table"`
- `"Caption"`
- `"Footnote"`
- `"Formula"`
- `"List-item"`
- `"Page-header"`
- `"Page-footer"`
- `"Section-header"`

## The Direct Mapping

In marker's `LayoutBuilder.surya_layout()`, line 141:
```python
block_cls = get_block_class(BlockTypes[bbox.label])
```

This means Surya's labels must match marker's BlockTypes enum **exactly** (case-sensitive)!

## Marker's BlockTypes

From `marker/schema/__init__.py`:
```python
class BlockTypes(str, Enum):
    Caption = auto()
    Code = auto()
    Figure = auto()
    Footnote = auto()
    Form = auto()
    Equation = auto()
    ListItem = auto()
    PageFooter = auto()
    PageHeader = auto()
    Picture = auto()
    SectionHeader = auto()
    Table = auto()
    Text = auto()
    # ... and more
```

## The Mapping Process

```
Surya Label → Direct Enum Lookup → Marker BlockType
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Title"         → BlockTypes["Title"]      → ❌ ERROR (no Title in enum)
"Section-header"→ BlockTypes["Section-header"] → ❌ ERROR (hyphen issue)
"SectionHeader" → BlockTypes["SectionHeader"] → ✅ BlockTypes.SectionHeader
"Text"          → BlockTypes["Text"]       → ✅ BlockTypes.Text
"Table"         → BlockTypes["Table"]      → ✅ BlockTypes.Table
"Figure"        → BlockTypes["Figure"]     → ✅ BlockTypes.Figure
```

## Important Notes

1. **Case Sensitive**: "text" won't work, must be "Text"
2. **No Hypens**: "Section-header" won't work, must be "SectionHeader"
3. **Direct Mapping**: No translation layer - Surya labels must match BlockTypes exactly
4. **Title Problem**: Surya might output "Title" but marker expects "SectionHeader"

## How It Actually Works

1. Surya analyzes the page visually and outputs:
```json
{
    "bbox": [70.5, 81.9, 315.0, 95.5],
    "label": "Text",  // or "SectionHeader" if trained that way
    "score": 0.95
}
```

2. Marker creates the appropriate block type:
```python
if bbox.label == "Text":
    block = Text(polygon=bbox.polygon)
elif bbox.label == "SectionHeader":
    block = SectionHeader(polygon=bbox.polygon)
# etc.
```

3. Then checks if PDF text exists at those coordinates to decide on content source

## The Answer

So yes, **Surya is converting the page to labels with bbox coordinates**, but:
- The labels must match marker's BlockTypes enum exactly
- Some visual concepts (like "Title") might need to map to different block types (like "SectionHeader")
- The bbox coordinates are then used to match with PDF text objects

This is why the extractor has processors like `SectionHeaderProcessor` that might relabel blocks after initial detection based on content analysis.