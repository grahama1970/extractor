Here are the **complete, unabridged diffs** to (A) fix the right-pane clipping/scroll and (B) move + optimize Chat into the left rail (and gate Conflicts). All changes are in a single file unless noted.

---

### 1) `prototypes/tabbed/html/src/pages/ClassicLayout.tsx`

```diff
diff --git a/prototypes/tabbed/html/src/pages/ClassicLayout.tsx b/prototypes/tabbed/html/src/pages/ClassicLayout.tsx
index 1a2b3cd..9f7a6e0 100644
--- a/prototypes/tabbed/html/src/pages/ClassicLayout.tsx
+++ b/prototypes/tabbed/html/src/pages/ClassicLayout.tsx
@@ -1,6 +1,6 @@
 import React, { useEffect, useMemo, useRef, useState } from "react";
 import {
-  Upload, Search, Archive, Copy, Trash2, Plus, SquareDashed, Loader2, Minus,
+  Upload, Search, Archive, Copy, Trash2, Plus, SquareDashed, Loader2, Minus,
   ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ChevronDown,
   Edit, Sparkles, ArrowLeft, Tag, Moon, Info, Braces, FileText, Download, MoreHorizontal,
   Check, X
@@ -126,6 +126,13 @@ const ClassicLayout = () => {
   const [labels, setLabels] = useState<LabelDef[]>(() => (typeof window !== 'undefined' ? loadLabels() : DEFAULT_LABELS));
   useEffect(() => { setLabels(loadLabels()); }, []);
 
+  // Feature flags / compact UX toggles
+  const showConflicts = React.useMemo(() => {
+    try {
+      // Vite env or localStorage override
+      return Boolean((import.meta as any)?.env?.VITE_SHOW_CONFLICTS ?? (localStorage.getItem('show_conflicts') === '1'));
+    } catch { return false; }
+  }, []);
   const [jsonOpen, setJsonOpen] = useState(false);
   const [jsonText, setJsonText] = useState("{}");
   const [notesText, setNotesText] = useState("");
@@ -649,7 +656,7 @@ const ClassicLayout = () => {
 
       <SidebarProvider defaultOpen>
-      <div className="relative flex h-[calc(100vh-4rem)]" onPointerMove={paneOnDragMove} onPointerUp={paneEndDrag}>
+      <div className="relative flex h-[calc(100vh-4rem)] min-w-0" onPointerMove={paneOnDragMove} onPointerUp={paneEndDrag}>
         {appReady && <div data-testid="app-ready" className="hidden" aria-hidden />}
         {/* Explorer Panel */}
         <Sidebar side="left" collapsible="icon" className="bg-card">
@@ -672,6 +679,40 @@ const ClassicLayout = () => {
                   </label>
                   {selectedCount > 0 && (
                     <Badge variant="secondary" className="shrink-0">{selectedCount}</Badge>
                   )}
                 </div>
               </div>
+
+              {/** ---------------------  Chat (relocated to LEFT rail) ---------------------- */}
+              <div className="rounded-md border bg-background p-2">
+                <label className="text-xs font-medium mb-1 block">Chat (current PDF)</label>
+                <div className="flex items-center gap-2">
+                  <Input
+                    value={chatQ}
+                    onChange={(e)=>setChatQ(e.target.value)}
+                    placeholder="Ask a question…"
+                    onKeyDown={(e)=>{ if (e.key==='Enter') askChat(); }}
+                    className="h-8"
+                  />
+                  <Button size="sm" onClick={askChat}>Ask</Button>
+                </div>
+                {chatA && (
+                  <div className="mt-2 text-[12px] text-foreground/90 whitespace-pre-wrap">
+                    {chatA}
+                    {chatCites?.length ? (
+                      <div className="mt-1 text-[11px] text-muted-foreground">
+                        Cites: {chatCites.slice(0,3).map((c,i)=>`p${c.page} ${c.type}`).join(', ')}
+                      </div>
+                    ) : null}
+                  </div>
+                )}
+              </div>
+              {/** -------------------------------------------------------------------------- */}
+
             </div>
           </SidebarHeader>
 
@@ -1492,7 +1533,14 @@ const ClassicLayout = () => {
         </div>
 
         {/* Drag handle (right) – visual line with enlarged hit area */}
         <div className="relative w-1.5 bg-border hover:bg-primary transition-colors" aria-hidden="true">
@@ -1508,7 +1556,10 @@ const ClassicLayout = () => {
         </div>
 
         {/* Inspector Panel */}
-        <div className="border-l bg-card p-6 flex flex-col" style={{ width: rightW }} data-testid="inspector-pane">
+        <div
+          className="border-l bg-card p-6 flex flex-col shrink-0 overflow-y-auto min-h-0"
+          style={{ width: rightW, minWidth: 220, maxWidth: 480 }}
+          data-testid="inspector-pane"
+        >
 
           <div className="space-y-3 flex-1">
             <div>
@@ -1595,7 +1646,7 @@ const ClassicLayout = () => {
 
             {/* Notes */}
             <div className="flex-1 flex flex-col min-h-0 relative">
               <label className="text-sm font-medium mb-2 block">Notes</label>
               <Textarea
                 data-testid="notes-input"
-                className="flex-1 min-h-[100px] resize-none"
+                className="flex-1 min-h-[72px] resize-y"
                 placeholder="Add your notes here... Use @ to mention"
                 value={notesText}
                 onChange={(e)=>{
@@ -1630,7 +1681,8 @@ const ClassicLayout = () => {
               )}
             </div>
 
-            {/* Conflicts (load + list) */}
+            {/* Conflicts (load + list) – gated to reduce clutter in the inspector */}
+            {showConflicts && (
             <div className="mt-3">
               <div className="flex items-center justify-between mb-2">
                 <div className="text-sm font-medium">Conflicts</div>
@@ -1669,7 +1721,8 @@ const ClassicLayout = () => {
                   </div>
                 ))}
               </div>
             </div>
+            )}
 
             {/* Requirements (empty-state stub with refresh) */}
             <div className="mt-4" data-testid="req-pane">
@@ -1706,7 +1759,7 @@ const ClassicLayout = () => {
             </div>
           </div>
 
-          <div className="mt-4 pt-4 border-t">
+          <div className="mt-4 pt-4 border-t">
             <div className="text-xs text-muted-foreground space-y-1 text-center">
               <p><span className="bg-muted px-2 py-1 rounded">N</span>: New Box</p>
               <p><span className="bg-muted px-2 py-1 rounded">Ctrl+D</span>: Duplicate Box</p>
               <p><span className="bg-muted px-2 py-1 rounded">[</span> / <span className="bg-muted px-2 py-1 rounded">]</span>: Navigate</p>
             </div>
           </div>
 
-          {/* Chat (MVP) */}
-          <div className="mt-4 border-t pt-3">
-            <label className="text-sm font-medium mb-1 block">Chat (current PDF)</label>
-            <div className="flex items-center gap-2">
-              <Input value={chatQ} onChange={(e)=>setChatQ(e.target.value)} placeholder="Ask a question…" onKeyDown={(e)=>{ if (e.key==='Enter') askChat(); }} />
-              <Button size="sm" onClick={askChat}>Ask</Button>
-            </div>
-            {chatA && (
-              <div className="mt-2 text-sm whitespace-pre-wrap">
-                {chatA}
-                {chatCites?.length ? (
-                  <div className="mt-2 text-xs text-muted-foreground">Citations: {chatCites.slice(0,3).map((c,i)=>`p${c.page} ${c.type}`).join(', ')}</div>
-                ) : null}
-              </div>
-            )}
-          </div>
+          {/* Chat moved to left rail to keep inspector focused */}
         </div>
 
         {/* Non-blocking only: blocking dialog removed */}
```

> What this diff does
>
> * **Right pane won’t get cut off**: adds `shrink-0 overflow-y-auto min-h-0` and width clamps (`minWidth:220`, `maxWidth:480`).
> * **Row won’t squeeze children**: adds `min-w-0` to the main flex row.
> * **Chat moved to left rail**: compact, always-available chat widget under the file filter.
> * **Inspector simplified**: Notes made shorter (`min-h-[72px]`, `resize-y`), **Conflicts hidden by default** behind `showConflicts` flag.

---

### 2) (Optional, but useful) Enable the Conflicts view when needed

You can toggle the conflicts section in two ways:

* At build time (Vite):

```bash
# .env
VITE_SHOW_CONFLICTS=1
```

* Or at runtime in dev tools:

```js
localStorage.setItem('show_conflicts', '1') // show
localStorage.removeItem('show_conflicts')   // hide
```

---

## That’s it

Apply the diff above and rebuild. You’ll get:

* a stable, non-truncating inspector with its own
 scroll,
* chat placed where it won’t force inspector scrolling,
* a cleaner right rail with conflicts gated behind a flag.
