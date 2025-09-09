Gold Annotator (Streamlit)

Purpose
- A minimal, fast annotator to draw boxes on PDF pages and author gold JSON for tables/sections without the complexity of Label Studio.
- Writes gold files directly into your repo (e.g., data/gold_standards/tables/*.json), using the same schema your pipeline expects.

Quick start
1) Install deps (in a virtualenv):
   - pip install -r tools/gold_annotator/requirements.txt
2) Run:
   - streamlit run tools/gold_annotator/app.py
3) In the UI:
   - Choose a PDF or an images folder (data/labelstudio/images/<doc>/)
   - Render pages if needed (PyMuPDF)
   - Select a page (left sidebar)
   - Draw a box (drag on the canvas)
   - Fill: type, id, expected_json, part_idx (optional)
   - For tables: enter columns (comma separated) and use the rows grid editor (add rows as needed)
   - Click Save Gold → writes the JSON to the expected_json path
   - Boxes are persisted to <doc>.boxes.json next to your images for later editing

Gold schema
- Table:
  {
    "type": "table",
    "id": "bht_table_001",
    "columns": ["Name","Direction","Type","Description"],
    "rows": [["clk_i","in","logic","SubSystem Clock"]]
  }
- Section:
  {
    "type": "section",
    "id": "bht_header_001",
    "title": "INFERRED: …",
    "columns": [],
    "rows": []
  }

Merging contiguous table blocks
- Use the same expected_json path for all parts of the same table (e.g., data/gold_standards/tables/bht_table_001.json).
- Use part_idx (1,2,3) to indicate reading order if needed.

Notes
- The annotator reads/writes relative to your repo root; ensure expected_json paths are inside the repo.
- The rows editor uses Streamlit’s data_editor; use the Columns input to set headers.

