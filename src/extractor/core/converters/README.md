# Converters Module

**Role in Pipeline:** 🟢 *Crucial*

The *Converters* transform raw detector/builder output into the internal **Document** model that renderers and output utilities expect.

Typical flow:
```
PDF bytes → detector/ocr → builders/line, paragraph, table → converters/pdf.py → Document
```

Sub-packages:
| File / Dir | Purpose |
|------------|---------|
| `pdf.py` | Main PDF conversion pipeline (calls Surya, Builders) |
| `docx.py` | DOCX → Document |
| `pptx.py` | PPTX → Document |
| `xml.py`  | XML/HTML → Document |

Other files may be experimental; delete or move them only after verifying they are unused.

## Maintainer Notes
* Keep functions stateless where possible.
* Return type must be `extractor.core.schema.document.Document`.
* Ensure each converter registers itself for auto-dispatch in `extractor.api.convert_file()`.
