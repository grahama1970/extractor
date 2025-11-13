from __future__ import annotations

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Pipeline Overlay Viewer</title>
    <link rel="stylesheet" href="viewer.css" />
  </head>
  <body>
    <div id="app">
      <header>
        <h1>Pipeline Overlay Viewer</h1>
        <div class="page-controls">
          <button id="prevPage" aria-label="Previous page">◀</button>
          <span id="pageLabel">Page 1 / 1</span>
          <button id="nextPage" aria-label="Next page">▶</button>
        </div>
      </header>
      <main>
        <section class="stage">
          <div class="image-wrapper">
            <img id="pageImage" alt="Annotated page" />
            <div id="overlayLayer"></div>
          </div>
        </section>
        <aside class="sidebar">
          <h2>Overlays</h2>
          <ul id="overlayList"></ul>
          <div id="overlayMeta"></div>
        </aside>
      </main>
      <footer>
        <p>
          Arrow keys or ◀ ▶ to change pages. Click an overlay to inspect metadata.
        </p>
      </footer>
    </div>
    <script>
      window.__OVERLAY_MAP__ = __OVERLAY_DATA__;
    </script>
    <script src="viewer.js"></script>
  </body>
</html>
"""

VIEWER_JS = """(() => {
  const state = {
    pageIndex: 0,
    selectedId: null,
    data: window.__OVERLAY_MAP__ || { pages: [] },
  };

  const $ = (id) => document.getElementById(id);
  const pageImage = $("pageImage");
  const overlayLayer = $("overlayLayer");
  const overlayList = $("overlayList");
  const overlayMeta = $("overlayMeta");
  const pageLabel = $("pageLabel");

  const KIND_COLORS = {
    section: "rgba(0, 160, 0, 0.35)",
    table: "rgba(228, 59, 59, 0.35)",
    table_merged: "rgba(168, 0, 0, 0.35)",
    figure: "rgba(30, 96, 196, 0.35)",
    requirement: "rgba(255, 191, 0, 0.4)",
    header_candidate: "rgba(255, 0, 255, 0.4)",
    table_rejected: "rgba(90, 90, 90, 0.35)",
    default: "rgba(60, 60, 60, 0.25)",
  };

  function clampPage(index) {
    const pages = state.data.pages || [];
    if (!pages.length) return 0;
    return Math.max(0, Math.min(index, pages.length - 1));
  }

  function setPage(newIndex) {
    state.pageIndex = clampPage(newIndex);
    state.selectedId = null;
    render();
  }

  function render() {
    const pages = state.data.pages || [];
    if (!pages.length) {
      pageLabel.textContent = "No overlays";
      overlayLayer.innerHTML = "";
      overlayList.innerHTML = "";
      overlayMeta.innerHTML = "<p>No overlay_map.json data.</p>";
      return;
    }
    const page = pages[state.pageIndex];
    pageLabel.textContent = `Page ${state.pageIndex + 1} / ${pages.length}`;
    pageImage.src = page.image;
    pageImage.onload = () => updateOverlays(page);
    pageImage.onerror = () => {
      overlayLayer.innerHTML = "";
      overlayMeta.innerHTML = "<p>Failed to load page image.</p>";
    };
    renderOverlayList(page);
  }

  function updateOverlays(page) {
    overlayLayer.innerHTML = "";
    const overlays = page.overlays || [];
    const naturalW = pageImage.naturalWidth || 1;
    const naturalH = pageImage.naturalHeight || 1;
    const displayW = pageImage.clientWidth || naturalW;
    const displayH = pageImage.clientHeight || naturalH;
    const scaleX = displayW / naturalW;
    const scaleY = displayH / naturalH;

    overlayLayer.style.width = displayW + "px";
    overlayLayer.style.height = displayH + "px";

    overlays.forEach((ov) => {
      const [x0, y0, x1, y1] = ov.px_rect || [0, 0, 0, 0];
      const el = document.createElement("div");
      el.className = "overlay-box";
      const ovId = String(ov.id);
      el.dataset.id = ovId;
      const color = KIND_COLORS[ov.kind] || KIND_COLORS.default;
      el.style.left = x0 * scaleX + "px";
      el.style.top = y0 * scaleY + "px";
      el.style.width = Math.max(0, x1 - x0) * scaleX + "px";
      el.style.height = Math.max(0, y1 - y0) * scaleY + "px";
      el.style.backgroundColor = color;
      if (String(state.selectedId) === ovId) {
        el.classList.add("selected");
      }
      el.addEventListener("click", () => {
        state.selectedId = ovId;
        renderOverlayList(page);
        highlightSelection();
      });
      overlayLayer.appendChild(el);
    });
    highlightSelection();
  }

  function renderOverlayList(page) {
    const overlays = page.overlays || [];
    overlayList.innerHTML = "";
    if (!overlays.length) {
      overlayList.innerHTML = "<li>No overlays on this page.</li>";
      overlayMeta.innerHTML = "";
      return;
    }
    overlays.forEach((ov) => {
      const li = document.createElement("li");
      const ovId = String(ov.id);
      li.dataset.id = ovId;
      li.textContent = `${ov.kind || "unknown"} — ${ov.label || ""}`;
      if (String(state.selectedId) === ovId) {
        li.classList.add("selected");
        renderOverlayMeta(ov);
      }
      li.addEventListener("click", () => {
        state.selectedId = ovId;
        renderOverlayList(page);
        highlightSelection();
      });
      overlayList.appendChild(li);
    });
    if (!state.selectedId && overlays.length) {
      state.selectedId = String(overlays[0].id);
      renderOverlayList(page);
    }
  }

  function renderOverlayMeta(ov) {
    const meta = Object.assign({}, ov.meta || {});
    const entries = Object.entries(meta)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => `<dt>${key}</dt><dd>${JSON.stringify(value)}</dd>`)
      .join("");
    overlayMeta.innerHTML = `
      <h3>Overlay ${ov.id}</h3>
      <p><strong>Kind:</strong> ${ov.kind}</p>
      <p><strong>Label:</strong> ${ov.label || "—"}</p>
      <dl>${entries || "<dt>meta</dt><dd>{}</dd>"}</dl>
    `;
  }

  function highlightSelection() {
    const overlays = overlayLayer.querySelectorAll(".overlay-box");
    overlays.forEach((el) => {
      if (String(el.dataset.id) === String(state.selectedId)) {
        el.classList.add("selected");
      } else {
        el.classList.remove("selected");
      }
    });
    const items = overlayList.querySelectorAll("li[data-id]");
    items.forEach((li) => {
      if (String(li.dataset.id) === String(state.selectedId)) {
        li.classList.add("selected");
        const pageData = state.data.pages[state.pageIndex];
        const overlay = (pageData.overlays || []).find(
          (ov) => String(ov.id) === String(state.selectedId)
        );
        if (overlay) {
          renderOverlayMeta(overlay);
        }
      } else {
        li.classList.remove("selected");
      }
    });
  }

  $("prevPage").addEventListener("click", () => setPage(state.pageIndex - 1));
  $("nextPage").addEventListener("click", () => setPage(state.pageIndex + 1));
  window.addEventListener("keydown", (evt) => {
    if (evt.key === "ArrowLeft") {
      setPage(state.pageIndex - 1);
    } else if (evt.key === "ArrowRight") {
      setPage(state.pageIndex + 1);
    }
  });

  render();
})();
"""

VIEWER_CSS = """* {
  box-sizing: border-box;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

body {
  margin: 0;
  background: #f4f5f7;
  color: #202124;
}

#app {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 24px 24px;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

header h1 {
  font-size: 1.25rem;
  margin: 0;
}

.page-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-controls button {
  padding: 4px 8px;
  font-size: 1rem;
}

main {
  display: flex;
  gap: 16px;
}

.stage {
  flex: 3;
  display: flex;
  justify-content: center;
}

.image-wrapper {
  position: relative;
  overflow: hidden;
  background: #fff;
  padding: 12px;
  border: 1px solid #d4d4d4;
  border-radius: 8px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

#pageImage {
  max-width: 100%;
  display: block;
}

#overlayLayer {
  position: absolute;
  top: 12px;
  left: 12px;
  pointer-events: none;
}

.overlay-box {
  position: absolute;
  border: 1.6px solid rgba(0, 0, 0, 0.3);
  border-radius: 2px;
  pointer-events: auto;
  cursor: pointer;
}

.overlay-box.selected {
  border: 2px solid #2962ff;
  box-shadow: 0 0 0 2px rgba(41, 98, 255, 0.35);
}

.sidebar {
  flex: 1.2;
  background: #fff;
  border: 1px solid #d4d4d4;
  border-radius: 8px;
  padding: 12px;
  max-height: 80vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar h2 {
  margin: 0;
  font-size: 1rem;
}

#overlayList {
  list-style: none;
  padding: 0;
  margin: 0;
}

#overlayList li {
  padding: 4px 6px;
  border-radius: 4px;
  margin-bottom: 4px;
  cursor: pointer;
}

#overlayList li.selected {
  background: rgba(41, 98, 255, 0.12);
  color: #0d47a1;
  font-weight: 600;
}

#overlayMeta {
  font-size: 0.9rem;
  border-top: 1px solid #e0e0e0;
  padding-top: 8px;
}

#overlayMeta dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 8px;
  margin: 0;
}

#overlayMeta dt {
  font-weight: 600;
  color: #555;
}

footer {
  margin-top: 16px;
  font-size: 0.85rem;
  color: #555;
}

@media (max-width: 960px) {
  main {
    flex-direction: column;
  }
  .stage {
    justify-content: flex-start;
  }
  .sidebar {
    max-height: none;
  }
}
"""

ASSETS = {
  "viewer.js": VIEWER_JS,
  "viewer.css": VIEWER_CSS,
}
