MB: /main Labels — Add Label dialog (name, icon, color, description)

Assignees:
Labels: micro-brief, status:proposed

Context
- Route/Element: /main · HUD → Label palette
- Loom: https://www.loom.com/share/330c21dc88314360a61923ee6bd69527

Friction
- The palette is hard-coded to few labels (Section/Table/Figure). There is no way to add a new label type interactively.

Target Feel
- A clear “Add Label” action (button in the palette) opens a dialog consistent with shadcn UI.
- Dialog fields (all required except Description):
  - Label Name (e.g., “Figure”)
  - Icon (Lucide icon select or searchable list)
  - Color/Style (choose from annotation-* presets)
  - Description (short helpful text)
- Live preview chip updates as fields change.
- Save adds the label to the registry, closes the dialog, and the new label appears in the palette immediately.
- Persist labels to localStorage (prototype) so they survive reload; later we can back this with app storage.
- Prevent duplicates by name (case-insensitive), show inline validation.
- ESC closes dialog. Enter on Save when valid.

Acceptance
- [ ] “Add Label” is visible in the label palette and opens a dialog
- [ ] Required fields validate; duplicate names rejected; Save is disabled until valid
- [ ] After Save, the new label appears in the palette and sets the selected box type when clicked
- [ ] Added label persists across reload (stored in localStorage)
- [ ] ESC closes dialog; Enter triggers Save when valid

Verify (60–120s)
1) Open palette → click “Add Label” → dialog appears; type Name=Equation, select Icon=Sigma (or similar), pick color; Save → palette shows “Equation” and clicking applies it to selected box
2) Reload page → palette still shows “Equation”
3) Try adding “Equation” again → duplicate validation appears; Save disabled
4) ESC key closes dialog without changes; Enter saves when valid

Automated check (Puppeteer)
- Start dev server: `cd prototypes/tabbed/html && npm run dev`
- Run (after feature implementation): `node scripts/ux_mb007.mjs`
- Script asserts:
  - “Add Label” button exists (data-testid="label-add")
  - Dialog opens (data-testid="label-add-dialog"), accept Name/Icon/Color
  - Save persists label; palette renders button (data-testid="label-item-equation")
  - Reload → label remains
  - Attempt duplicate → validation prevents Save

Implementation notes
- Add labels registry `src/lib/labels.ts`:
  - export const DEFAULT_LABELS = [{ id:'Section', color:'annotation-section', icon:'Heading' }, { id:'Table', color:'annotation-table', icon:'Table' }, { id:'Figure', color:'annotation-figure', icon:'Image' }]
  - export function loadLabels(): DEFAULT_LABELS + local additions (from localStorage)
  - export function saveLabel(label)
- Palette renders from `loadLabels()`; dialog writes via `saveLabel()`.

