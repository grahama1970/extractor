from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd
import streamlit as st
from PIL import Image

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from streamlit_drawable_canvas import st_canvas
except Exception:
    st_canvas = None


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Box:
    page: int
    x: float
    y: float
    w: float
    h: float
    type: str = "table"  # table|requirements|section|figure
    id: str = ""
    expected_json: str = ""
    part_idx: Optional[int] = None


def render_pdf_to_images(pdf_path: Path, out_dir: Path, dpi: int = 300) -> List[Path]:
    if fitz is None:
        st.error("PyMuPDF (fitz) not installed. `pip install pymupdf`.\n")
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    images: List[Path] = []
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    for p in range(len(doc)):
        page = doc[p]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_path = out_dir / f"page_{p+1:03d}.png"
        pix.save(img_path.as_posix())
        images.append(img_path)
    doc.close()
    return images


def list_images(images_dir: Path) -> List[Path]:
    if not images_dir.exists():
        return []
    pngs = sorted(images_dir.glob("*.png"))
    jpgs = sorted(images_dir.glob("*.jpg"))
    return pngs or jpgs


def load_boxes_state(state_path: Path) -> List[Box]:
    if not state_path.exists():
        return []
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return [Box(**b) for b in data]
    except Exception:
        return []


def save_boxes_state(state_path: Path, boxes: List[Box]):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps([asdict(b) for b in boxes], indent=2), encoding="utf-8")


def validate_table_json(obj: dict) -> Tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "Table JSON must be an object"
    if obj.get("type") != "table":
        return False, "type must be 'table'"
    if not isinstance(obj.get("columns", []), list):
        return False, "columns must be a list"
    rows = obj.get("rows", [])
    if not isinstance(rows, list):
        return False, "rows must be a list"
    return True, "OK"


def write_gold_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        bkp = path.with_suffix(path.suffix + ".orig.json")
        if not bkp.exists():
            bkp.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def default_table_json(box: Box, columns: List[str], rows: List[List[str]]):
    return {
        "type": "table",
        "id": box.id or "",
        "columns": columns,
        "rows": rows,
    }


def app():
    st.set_page_config(page_title="Gold Annotator", layout="wide")
    st.title("Gold Annotator (PDF → Boxes → Gold JSON)")
    st.write("Draw boxes, edit gold JSON, save directly to your repo")

    # Sidebar: choose input
    with st.sidebar:
        st.header("Input")
        pdf_file = st.file_uploader("Choose PDF", type=["pdf"], accept_multiple_files=False)
        images_dir_str = st.text_input("Or images folder (relative to repo)", "data/labelstudio/images/BHT_CV32A65X_marked")
        images_dir = (REPO_ROOT / images_dir_str).resolve()
        dpi = st.number_input("Render DPI", value=300, step=50)
        render_btn = st.button("Render PDF → images")

    # Render PDF on demand
    if render_btn and pdf_file is not None:
        tmp_pdf = REPO_ROOT / "data" / "_tmp_pdf_upload.pdf"
        tmp_pdf.parent.mkdir(parents=True, exist_ok=True)
        tmp_pdf.write_bytes(pdf_file.read())
        out_dir = images_dir
        images = render_pdf_to_images(tmp_pdf, out_dir, dpi=int(dpi))
        if images:
            st.success(f"Rendered {len(images)} pages to {out_dir}")

    images = list_images(images_dir)
    if not images:
        st.warning("No images found. Render a PDF or point to an images folder.")
        st.stop()

    # Session state
    if "page_idx" not in st.session_state:
        st.session_state.page_idx = 0
    page = st.session_state.page_idx
    page = st.slider("Page", 1, len(images), value=page + 1) - 1
    st.session_state.page_idx = page

    img_path = images[page]
    pil_img = Image.open(img_path)
    W, H = pil_img.size

    # Boxes state file
    state_path = images_dir / f"{images_dir.name}.boxes.json"
    boxes = load_boxes_state(state_path)

    # Canvas
    st.subheader(f"Page {page+1} — {img_path.name}")
    if st_canvas is None:
        st.error("streamlit-drawable-canvas not installed. `pip install streamlit-drawable-canvas`.\n")
        st.stop()

    canvas_res = st_canvas(
        fill_color="rgba(0, 0, 0, 0)",
        stroke_width=3,
        background_image=pil_img,
        height=H,
        width=W,
        drawing_mode="rect",
        key=f"canvas_{page}",
    )

    # Convert new rectangle to Box (if present)
    new_box: Optional[Box] = None
    if canvas_res and canvas_res.json_data is not None:
        for obj in canvas_res.json_data.get("objects", []):
            if obj.get("type") == "rect" and obj.get("version") is None:
                x, y = float(obj["left"]), float(obj["top"])
                w, h = float(obj["width"]), float(obj["height"])
                new_box = Box(page=page + 1, x=x / W, y=y / H, w=w / W, h=h / H)
                break

    # Right panel: editor
    with st.sidebar:
        st.header("Selection")
        # list existing boxes on this page
        page_boxes = [b for b in boxes if b.page == page + 1]
        idx = st.selectbox("Existing boxes on page", options=list(range(len(page_boxes))), format_func=lambda i: page_boxes[i].id or f"box_{i+1}") if page_boxes else None
        active_box = page_boxes[idx] if idx is not None else new_box
        if active_box is None:
            st.info("Draw a rectangle to start annotating.")
        else:
            active_box.type = st.selectbox("type", ["table","requirements","section","figure"], index=["table","requirements","section","figure"].index(active_box.type) if active_box.type in ["table","requirements","section","figure"] else 0)
            active_box.id = st.text_input("id", value=active_box.id)
            active_box.expected_json = st.text_input("expected_json (repo-relative path)", value=active_box.expected_json or f"data/gold_standards/tables/{images_dir.name}_table.json")
            part_str = st.text_input("part_idx (optional)", value=str(active_box.part_idx or ""))
            active_box.part_idx = int(part_str) if part_str.strip().isdigit() else None

            if active_box.type == "table":
                st.markdown("**Table Gold**")
                cols_str = st.text_input("Columns (comma-separated)", value="Name,Direction,Type,Description")
                cols = [c.strip() for c in cols_str.split(",") if c.strip()]
                # rows editor
                st.caption("Rows (edit cells; add/remove rows)")
                default_rows = pd.DataFrame([[""] * max(1, len(cols))], columns=cols or ["col1"])
                df_key = f"rows_df_{page}_{active_box.id}"
                df = st.data_editor(default_rows, num_rows="dynamic", use_container_width=True, key=df_key)
                rows = df.values.tolist()

                if st.button("Save Gold", type="primary"):
                    # Validate path inside repo
                    try:
                        out_path = (REPO_ROOT / active_box.expected_json).resolve()
                        if not str(out_path).startswith(str(REPO_ROOT)):
                            st.error("expected_json path must be inside repo")
                        else:
                            obj = default_table_json(active_box, cols, rows)
                            ok, msg = validate_table_json(obj)
                            if not ok:
                                st.error(msg)
                            else:
                                write_gold_json(out_path, obj)
                                st.success(f"Wrote {out_path}")
                    except Exception as e:
                        st.error(str(e))
            else:
                st.markdown("**Section/Requirements Gold**")
                title = st.text_input("title (optional; defaults to INFERRED:id)")
                if st.button("Save Gold", type="primary"):
                    out_path = (REPO_ROOT / active_box.expected_json).resolve()
                    if not str(out_path).startswith(str(REPO_ROOT)):
                        st.error("expected_json path must be inside repo")
                    else:
                        obj = {
                            "type": "section",
                            "id": active_box.id,
                            "title": title or f"INFERRED: {active_box.id}",
                            "columns": [],
                            "rows": [],
                        }
                        write_gold_json(out_path, obj)
                        st.success(f"Wrote {out_path}")

            # Save/Update box to state
            if st.button("Save Box (coords + meta)"):
                # insert or update in boxes list
                found = False
                for i, b in enumerate(boxes):
                    if b.page == active_box.page and b.id == active_box.id:
                        boxes[i] = active_box
                        found = True
                        break
                if not found:
                    boxes.append(active_box)
                save_boxes_state(state_path, boxes)
                st.success(f"Saved box to {state_path}")

    # Show existing boxes (summary)
    st.subheader("Boxes on this doc")
    if boxes:
        df = pd.DataFrame([asdict(b) for b in boxes])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("No saved boxes yet.")


if __name__ == "__main__":
    app()

