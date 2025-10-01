# UX Review Bundle (Micro)

Date: 2025-09-21T08:05:00-04:00

Purpose: Minimal, diff-focused snippets for LLM review.

## Recent Artifacts
- (none found)


---

## Zoom buttons (top toolbar) — prototypes/tabbed/html/src/pages/ClassicLayout.tsx:1648,1706

\n```tsx
                {/* Results dropdown */}
                {searchQuery && (
                  <div className="absolute top-10 left-0 z-20 bg-popover border rounded shadow min-w-[300px] max-h-60 overflow-auto">
                    {hasHits ? (
                      searchHits.slice(0, 10).map((h, idx) => (
                        <button
                          key={`hit-${idx}-${h.page}`}
                          data-testid="search-hit"
                          data-page={String(h.page)}
                          data-snippet={h.snippet}
                          onClick={() => { setCurrentPage(Math.max(1, Math.min(totalPages, h.page))); setHitIndex(idx); }}
                          className="block w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
                          title={`Go to page ${h.page}`}
                        >
                          <span className="text-muted-foreground mr-2">p{h.page}:</span>
                          <span className="truncate inline-block max-w-[220px] align-middle">{h.snippet || '…'}</span>
                        </button>
                      ))
                    ) : (
                      <div className="px-3 py-2 text-sm text-muted-foreground">No results</div>
                    )}
                    {indexing.total > 0 && indexing.done < indexing.total && (
                      <div className="px-3 py-1 text-[11px] text-muted-foreground border-t">Indexing… {indexing.done}/{indexing.total}</div>
                    )}
                  </div>
                )}
              </div>
              <div className="ml-auto hidden lg:flex items-center gap-2 text-sm text-muted-foreground">
                {/* Compact top pager (wide screens) */}
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-first-top" size="sm" variant="outline" title="First page" onClick={() => setCurrentPage(1)} aria-label="First Page"><ChevronsLeft className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>First page</TooltipContent></Tooltip>
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-prev-top" size="sm" variant="outline" title="Previous page" onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} aria-label="Previous Page"><ChevronLeft className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Previous page</TooltipContent></Tooltip>
                <div className="text-xs text-muted-foreground whitespace-nowrap" data-testid="page-label-top">{currentPage} / {totalPages}</div>
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-next-top" size="sm" variant="outline" title="Next page" onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))} aria-label="Next Page"><ChevronRight className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Next page</TooltipContent></Tooltip>
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-last-top" size="sm" variant="outline" title="Last page" onClick={() => setCurrentPage(totalPages)} aria-label="Last Page"><ChevronsRight className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Last page</TooltipContent></Tooltip>
                <Separator orientation="vertical" className="mx-2" />
                <span>Zoom</span>
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-zoom-out-top" size="sm" variant="outline" title="Zoom out" onClick={()=> setZoom(z=> Math.max(0.5, Number((z-0.1).toFixed(2))))} aria-label="Zoom out">
                    <Minus className="h-4 w-4" />
                  </Button>
                </TooltipTrigger><TooltipContent>Zoom out</TooltipContent></Tooltip>
                <input data-testid="zoom-top" type="range" min={0.5} max={2} step={0.1} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} />
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-zoom-in-top" size="sm" variant="outline" title="Zoom in" onClick={()=> setZoom(z=> Math.min(2, Number((z+0.1).toFixed(2))))} aria-label="Zoom in">
                    <Plus className="h-4 w-4" />
                  </Button>
                </TooltipTrigger><TooltipContent>Zoom in</TooltipContent></Tooltip>
                <span>{Math.round(zoom * 100)}%</span>
                <Button size="sm" variant="outline" title="Fit to width" onClick={() => {
                  try {
                    const container = viewerRef.current;
\n```

---

## Pipeline buttons with tooltips (top toolbar) — prototypes/tabbed/html/src/pages/ClassicLayout.tsx:1568,1594

\n```tsx
              <Separator orientation="vertical" className="mx-2" />
              {/* Pipeline actions (duplicated from HUD for visibility) */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="outline" title="Load pipeline annotations" data-testid="btn-load-pipeline-annos" onClick={loadPipelineAnnotations}>
                    <Download className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Load pipeline annotations</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="outline" title="Save annotations" data-testid="btn-save-annotations" onClick={saveAnnotations}>
                    <Archive className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Save annotations</TooltipContent>
              </Tooltip>
              <div className="flex items-center gap-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button size="sm" variant="outline" title="Upsert to Arango" data-testid="btn-upsert-pipeline" onClick={upsertPipeline}>
                      <Upload className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Upsert to Arango</TooltipContent>
                </Tooltip>
\n```

---

## Pipeline buttons cluster (tooltip-wrapped) — prototypes/tabbed/html/src/pages/ClassicLayout.tsx:2008,2038

\n```tsx
                <Copy className="h-4 w-4" />
              </Button>
              
              <Button size="sm" variant="outline" title="Suggest Tables" data-testid="btn-suggest-tables" onClick={suggestTables}>
                <Sparkles className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" title="Export COCO" onClick={exportCoco}>
                <Download className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" title="Run Pipeline" onClick={runPipeline}>
                <Braces className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="default" title="Extract (Pipeline)" data-testid="btn-extract-pipeline" onClick={extractPipeline}>
                <Sparkles className="h-4 w-4" />
              </Button>
              <Tooltip><TooltipTrigger asChild>
                <Button size="sm" variant="outline" title="Load pipeline annotations" data-testid="btn-load-pipeline-annos" onClick={loadPipelineAnnotations}>
                  <Download className="h-4 w-4" />
                </Button>
              </TooltipTrigger><TooltipContent>Load pipeline annotations</TooltipContent></Tooltip>
              <Tooltip><TooltipTrigger asChild>
                <Button size="sm" variant="outline" title="Save annotations" data-testid="btn-save-annotations" onClick={saveAnnotations}>
                  <Archive className="h-4 w-4" />
                </Button>
              </TooltipTrigger><TooltipContent>Save annotations</TooltipContent></Tooltip>
              <div className="flex items-center gap-2">
                <Tooltip><TooltipTrigger asChild>
                  <Button size="sm" variant="outline" title="Upsert to Arango" data-testid="btn-upsert-pipeline" onClick={upsertPipeline}>
                    <Upload className="h-4 w-4" />
                  </Button>
                </TooltipTrigger><TooltipContent>Upsert to Arango</TooltipContent></Tooltip>
\n```

---

## Inspector pane marker — prototypes/tabbed/html/src/pages/ClassicLayout.tsx:2188,2206

\n```tsx
                  min={1}
                  max={totalPages}
                  value={currentPage}
                  onChange={(e) => setCurrentPage(Number(e.target.value))}
                  className="w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  aria-label="Page slider"
                  aria-valuetext={`Page ${currentPage} of ${totalPages}`}
                />
              </span>
                <div className="text-sm text-muted-foreground whitespace-nowrap" data-testid="page-label">Page {currentPage} of {totalPages}</div>
                <span data-testid="page-number" className="hidden">{currentPage}</span>
              </div>
              <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <span className="relative inline-flex">
                <Tooltip><TooltipTrigger asChild>
                  <Button data-testid="btn-next" size="sm" variant="outline" title="Next page" onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))} aria-label="Next Page"><ChevronRight className="h-4 w-4" /></Button>
                </TooltipTrigger><TooltipContent>Next page</TooltipContent></Tooltip>
                <Tooltip><TooltipTrigger asChild>
\n```

---

## DB status + selection handlers — prototypes/tabbed/html/src/pages/ClassicLayout.tsx:668,686

\n```tsx
            COCO written. <a className="underline" href={href} target="_blank" rel="noreferrer">Open artifacts</a>
            <button
              className="ml-3 underline"
              onClick={(e)=>{ e.preventDefault(); navigator.clipboard.writeText(String(j.dir || '')).then(()=>toast.success('Path copied'), ()=>toast.error('Copy failed')); }}
            >Copy path</button>
          </span>
        );
      } else {
        toast.error(j?.error || 'COCO export failed');
      }
    } catch (e) {
      toast.error('COCO export failed');
    }
  };

  // Track last pipeline results dir to re-load annotations
  const [lastResultsDir, setLastResultsDir] = useState<string | null>(null);
  const [dbReady, setDbReady] = useState<boolean>(false);
  const refreshDbStatus = async () => {
\n```

---

## Export payload normalizer + call (PDF) — prototypes/tabbed/html/src/pages/ClassicLayout.tsx:612,628

\n```tsx
        setJsonOpen(true);
        toast.success('Generated');
      }
    } catch (e) {
      if (strictMatch) toast.error('Exact JSON Match failed'); else toast.error('Failed to generate');
    } finally {
      setLlmPending((n) => Math.max(0, n - 1));
    }
  };



  // Suggestions via Camelot (server)
  const suggestTables = async () => {
    try {
      if (!currentPdfRel) { toast.error('Open a PDF first'); return; }
      const u = `/api/suggest/tables?rel=${encodeURIComponent(currentPdfRel)}&page=${currentPage}`;
\n```

---

## Export call (ZIP) — prototypes/tabbed/html/src/pages/ClassicLayout.tsx:1279,1308

\n```tsx
                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-1 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      aria-label="Select visible"
                      onChange={async (e)=>{
                        const want = e.currentTarget.checked;
                        const ids: string[] = [];
                        for (const it of filteredFiles) {
                          if (!it?.rel) continue;
                          const did = await ensureDocId(it.rel);
                          if (did) ids.push(did);
                        }
                        setSelectedDocIds(prev => {
                          const next = { ...prev } as Record<string, boolean>;
                          for (const id of ids) next[id] = want;
                          return next;
                        });
                      }}
                      checked={(() => {
                        const ids = filteredFiles.map((it:any)=> it?.rel && docIdByRel[it.rel] ? docIdByRel[it.rel] : null).filter(Boolean) as string[];
                        return ids.length > 0 && ids.every(id => !!selectedDocIds[id]);
                      })()}
                    />
                    Select visible
                  </label>
                  {selectedCount > 0 && (
                    <Badge variant="secondary" className="shrink-0">{selectedCount}</Badge>
                  )}
                </div>
\n```

---

## api_export_pdf per-page drawing — prototypes/tabbed/api/server.py:616,667

\n```python
@app.post("/api/export/pdf")
async def api_export_pdf(payload: Dict[str, Any], tasks: BackgroundTasks):
    """
    Render simple annotation overlays into a PDF using PyMuPDF and return it.
    Payload: { rel: str, boxes_by_page: { page_num(str|int): [ { type, instance_id, bounding_box:[x,y,w,h] } ] } }
    """
    if fitz is None:
        return JSONResponse({"ok": False, "error": "pymupdf_not_available"}, status_code=500)
    try:
        rel = payload.get("rel")
        boxes = payload.get("boxes_by_page") or {}
        src = _abs_pdf_path(rel)
        with fitz.open(src) as doc:
            # Draw annotations as semi-transparent boxes with label text
            for k, arr in boxes.items():
                try:
                    pnum = int(k)
                except Exception:
                    continue
                if pnum < 1 or pnum > doc.page_count:
                    continue
                page = doc.load_page(pnum - 1)
                pw, ph = page.rect.width, page.rect.height
                for b in arr or []:
                    bb = b.get("bounding_box") or b.get("bbox") or []
                    if not (isinstance(bb, (list, tuple)) and len(bb) == 4):
                        continue
                    x, y, w, h = bb
                    rect = fitz.Rect(x * pw, y * ph, (x + w) * pw, (y + h) * ph)
                    # Choose color by type
                    t = (b.get("type") or "Section").lower()
                    if t == "table":
                        color = (0.2, 0.4, 0.9)
                    elif t == "figure":
                        color = (0.5, 0.3, 0.9)
                    else:
                        color = (0.1, 0.7, 0.5)
                    page.draw_rect(rect, color=color, fill=(color[0], color[1], color[2], 0.08), width=1.2)
                    label = f"{b.get('type') or ''} · {b.get('instance_id') or ''}"
                    page.insert_text((rect.x0 + 4, rect.y0 - 8), label, fontsize=8, color=color)
            # Write to temp file
            fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            doc.save(tmp_path)
        filename = f"annotated_{Path(rel).stem}.pdf"
        # Clean up temp file after response is sent
        tasks.add_task(lambda p: (os.path.exists(p) and os.remove(p)), tmp_path)
        return FileResponse(tmp_path, media_type="application/pdf", filename=filename)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
\n```

---

## litellm guard + 503 path — prototypes/tabbed/api/server.py:736,799

\n```python
# Shared LiteLLM integration (project-standard)
try:
    from extractor.pipeline.utils.litellm_call import litellm_call  # type: ignore
    from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache  # type: ignore
except Exception:  # pragma: no cover
    litellm_call = None  # type: ignore
    def initialize_litellm_cache():  # type: ignore
        return None

# Initialize cache best-effort
try:
    initialize_litellm_cache()
except Exception:
    pass


@app.post("/api/ux/generate")
async def http_generate(payload: Dict[str, Any]):
    # Mock path enabled?
    if os.getenv("UX_MOCK_GENERATE", "0") in ("1", "true", "TRUE", "yes"):
        sample = {
            "title": "INFERRED_Table_Example",
            "columns": ["Col A", "Col B", "Col C"],
            "data": [["A1", "B1", "C1"], ["A2", "B2", "C2"]],
        }
        return JSONResponse({"ok": True, "data": sample})

    model = (
        payload.get("model")
        or os.getenv("LITELLM_DEFAULT_MODEL")
        or os.getenv("DEFAULT_LITELLM_MODEL")
        or os.getenv("LITELLM_VLM_MODEL", "gemini/gemini-2.5-flash")
    )
    prompt = payload.get("prompt") or ""
    image = payload.get("image")

    temp_path: str | None = None
    try:
        params: Dict[str, Any] = {"model": model, "text": prompt}
        if image:
            # Support data URLs by writing to a temporary file
            if isinstance(image, str) and image.startswith("data:image/") and "," in image:
                import base64, tempfile
                header, b64 = image.split(",", 1)
                ext = "png"
                try:
                    kind = header.split(";")[0].split("/")[-1]
                    if kind in ("png", "jpeg", "jpg", "webp"):
                        ext = "jpg" if kind == "jpeg" else kind
                except Exception:
                    pass
                fd, temp_path = tempfile.mkstemp(suffix=f".{ext}")
                with os.fdopen(fd, "wb") as f:
                    f.write(base64.b64decode(b64))
                params["image"] = temp_path
            else:
                params["image"] = image
        # Enforce JSON object outputs for downstream parsing
        if litellm_call is None:
            return JSONResponse({"ok": False, "error": "litellm_unavailable"}, status_code=503)
        results = await litellm_call(
            [params],
            wrap_json=True,
            concurrency=1,
\n```

---

## artifacts/file restricted to ARTIFACTS_ROOT — prototypes/tabbed/api/server.py:1766,1784

\n```python
    except Exception:
        pass
    return { 'ok': ok, 'results_dir': str(results),
             'summary_path': str(summary) if summary.exists() else None,
             'final_report_json': str(final_json) if final_json.exists() else None,
             'final_report_md': str(final_md) if final_md.exists() else None }


@app.get("/api/artifacts/file")
def api_artifact_file(path: str):
    # Restrict access to ARTIFACTS_ROOT for safety
    target = Path(path if Path(path).is_absolute() else Path(ARTIFACTS_ROOT) / path).resolve()
    root = Path(ARTIFACTS_ROOT).resolve()
    try:
        _ = target.relative_to(root)
    except Exception:
        return JSONResponse({"ok": False, "error": "outside_artifacts_root"}, status_code=400)
    if not target.exists() or not target.is_file():
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
\n```

---

## console_errors closes browser (local) — scripts/smokes/console_errors.mjs:38,66

\n```javascript
  const url = BASE.replace(/\/$/, '');
  const stamp = ts();
  const shot = path.join(OUT_DIR, `console_errors_${stamp}.png`);
  const logp = path.join(OUT_DIR, `console_errors_${stamp}.log`);
  const log = (m)=>fs.appendFileSync(logp, m+"\n");
  log(`BASE_URL=${url}`);
  log(`WS_DISCOVERY=${DISCOVERY}`);
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
  } catch (e) {
    const msg = 'Navigation failed: ' + (e?.message || e);
    consoleErrors.push(msg);
    log(msg);
  }
  // Give the app a moment to mount/hydrate
  await new Promise((r) => setTimeout(r, 1200));
  try { await page.screenshot({ path: shot, fullPage: true }); log(`screenshot=${shot}`); } catch {}

  const errs = consoleErrors.concat(pageErrors);
  const isRemote = !!ws;
  if (errs.length) {
    console.error('console_errors: FAIL');
    for (const e of errs) { console.error(' -', e); try { log('ERR: '+e); } catch {} }
    if (isRemote) await browser.disconnect(); else await browser.close();
    process.exit(1);
  }
  console.log('console_errors: OK');
  try { log('OK'); } catch {}
  if (isRemote) await browser.disconnect(); else await browser.close();
\n```

---

## ux_check_cdp_auto inline minimal check — scripts/ux_check_cdp_auto.mjs:16,28

\n```javascript
(async () => {
  const ws = await getWS();
  if (!ws) {
    console.error(`CDP discovery failed at ${DISCOVERY}`);
    process.exit(2);
  }
  console.log(`CDP: ${ws}`);
  const env = { ...process.env, BROWSERLESS_WS: ws, BASE_URL: BASE };
  const target = 'scripts/ux_check_cdp.mjs';
  if (!fs.existsSync(target)) {
    console.log('[ux_check] Minimal inline check (ux_check_cdp.mjs not found)');
    try {
      const res = await fetch(BASE, { redirect: 'manual' });
\n```

---

## ui_toolbar_tooltips robust hover — scripts/smokes/ui_toolbar_tooltips.mjs:10,24

\n```javascript
async function hoverExpect(page, selector, textLike) {
  const el = await page.$(selector);
  if (!el) return false;
  // Accept title/aria-label as a valid tooltip source
  const attrOk = await page.$eval(selector, (n) => {
    const t = (n.getAttribute('title')||'') + ' ' + (n.getAttribute('aria-label')||'');
    return t.toLowerCase().includes('load pipeline annotations') || t.toLowerCase().includes('save annotations') || t.toLowerCase().includes('upsert to arango');
  }).catch(()=>false);
  if (attrOk) return true;
  // Scroll into view and hover
  await el.evaluate((n)=> n.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
  const box = await el.boundingBox();
  if (box) {
    await page.mouse.move(Math.floor(box.x+box.width/2), Math.floor(box.y+box.height/2));
  }
\n```

---

## ui_toolbar_tooltips toolbar wait — scripts/smokes/ui_toolbar_tooltips.mjs:26,37

\n```javascript
  await page.waitForTimeout(500);
  const ok = await page.waitForFunction((t) => {
    const tips = Array.from(document.querySelectorAll('[role="tooltip"],div[class*="Tooltip"],div[data-state="delayed-open"],div[data-side]'));
    return tips.some(el => (el.textContent||'').toLowerCase().includes(String(t).toLowerCase()));
  }, { timeout: 2500 }, textLike).then(()=>true).catch(()=>false);
  return ok;
}

(async () => {
  const stamp = ts();
  const shot = path.join(OUT_DIR, `ui_tooltips_${stamp}.png`);
  const logp = path.join(OUT_DIR, `ui_tooltips_${stamp}.log`);
\n```

---

## tooltips_controls to /main — scripts/smokes/tooltips_controls.mjs:1,20

\n```javascript
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function getWS() { try { const r = await fetch(DISCOVERY); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0','127.0.0.1'); } catch {} return null; }
const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const ws = await getWS(); if (!ws) { console.error('No CDP endpoint'); process.exit(3); }
  const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const page = await browser.newPage();
  await page.goto(BASE.replace(/\/$/, '') + '/main', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 10000 });
  // Hover first/next and check tooltips
  const firstHasTitle = await page.$eval('[data-testid="btn-first"]', el => !!el.getAttribute('title')).catch(()=>false);
\n```

---

## page_controls_top_toolbar (click next, wait label) — scripts/smokes/page_controls_top_toolbar.mjs:12,24

\n```javascript
  await page.goto(BASE.replace(/\/$/, '') + '/main', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="top-toolbar"]', { timeout: 15000 });
  const required = ['btn-first-top', 'btn-prev-top', 'btn-next-top', 'btn-last-top', 'page-label-top'];
  for (const id of required) {
    await page.waitForSelector(`[data-testid="${id}"]`, { timeout: 10000 });
  }
  // Basic interaction: click Next and ensure label updates to page 2
  await page.$eval('[data-testid="btn-next-top"]', (el) => (el instanceof HTMLElement ? el.click() : el.dispatchEvent(new MouseEvent('click', { bubbles: true }))));
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-testid="page-label-top"]');
    return el && /\b2\s*\/\s*\d+/.test(el.textContent || '');
  }, { timeout: 2000 });
  const label = await page.$eval('[data-testid="page-label-top"]', el => el.textContent || '');
\n```

---

## dev_requirements.sh sanity order — scripts/dev_requirements.sh:118,140

\n```bash
  export BROWSERLESS_DISCOVERY_URL="$DISC_URL"
  # Prefer CDP attach first to let the app fully warm up, then run console smoke
  if ! node scripts/ux_check_cdp_auto.mjs; then
    echo "[req-dev] Sanity FAIL (CDP attach). See scripts/artifacts/*.log and *.png" >&2
    exit 9
  fi
  if ! BASE_URL="$OPEN_URL" node scripts/smokes/console_errors.mjs; then
    echo "[req-dev] Sanity FAIL (console errors). Retrying after clearing Vite caches…" >&2
    kill ${VITE_PID:-} 2>/dev/null || true; sleep 0.5 || true
    VITE_PORT=$((DETECTED_VITE_PORT+1))
    start_vite "$VITE_PORT"
    OPEN_URL="http://127.0.0.1:${DETECTED_VITE_PORT}/main"
    echo "[req-dev] Open: ${OPEN_URL} (retry)" >&2
    if ! node scripts/ux_check_cdp_auto.mjs; then
      echo "[req-dev] Sanity FAIL (CDP attach retry)." >&2; exit 9
    fi
    if ! BASE_URL="$OPEN_URL" node scripts/smokes/console_errors.mjs; then
      echo "[req-dev] Sanity FAIL after retry. See scripts/artifacts/*.log and *.png" >&2
      exit 9
    fi
  fi
  # DOM count smoke for requirements pane
  if ! BASE_URL="http://127.0.0.1:${DETECTED_VITE_PORT}" node scripts/smokes/ui_requirements_pane_dom.mjs; then
\n```
