#!/usr/bin/env bash
set -euo pipefail

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Parity smokes
python3 scripts/smokes/pipeline/smoke_parity_docx.py
python3 scripts/smokes/pipeline/smoke_parity_html.py
python3 scripts/smokes/pipeline/smoke_parity_pptx.py
python3 scripts/smokes/pipeline/smoke_parity_spreadsheet.py
python3 scripts/smokes/pipeline/smoke_parity_rst.py
python3 scripts/smokes/pipeline/smoke_parity_epub.py
python3 scripts/smokes/pipeline/smoke_parity_xml.py
python3 scripts/smokes/pipeline/smoke_parity_markdown.py

# Provider capability smokes
python3 scripts/smokes/pipeline/smoke_html_img_caption.py
python3 scripts/smokes/pipeline/smoke_html_generator_meta.py
python3 scripts/smokes/pipeline/smoke_html_nested_lists.py
python3 scripts/smokes/pipeline/smoke_html_table_headers.py

python3 scripts/smokes/pipeline/smoke_pptx_sections_vs_slidecount.py
python3 scripts/smokes/pipeline/smoke_pptx_notes_and_picture.py

python3 scripts/smokes/pipeline/smoke_xml_parse_wrapped_root.py
python3 scripts/smokes/pipeline/smoke_xml_sect_title.py

python3 scripts/smokes/pipeline/smoke_spreadsheet_headers.py
python3 scripts/smokes/pipeline/smoke_spreadsheet_multisheet_context.py

python3 scripts/smokes/pipeline/smoke_docx_numbering_promotion.py

python3 scripts/smokes/pipeline/smoke_epub_no_toc_headings.py
python3 scripts/smokes/pipeline/smoke_epub_images_tables.py

python3 scripts/smokes/pipeline/smoke_markdown_code_and_lists.py

echo "All provider smokes completed."
