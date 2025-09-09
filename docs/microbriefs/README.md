Micro‑Briefs Workflow

Purpose
- Capture tiny, testable UI changes with just enough context to ship quickly.
- Keep briefs close to code for easy linking in PRs and patch notes.

Location
- Directory: `docs/microbriefs/`
- Images: `docs/microbriefs/images/`

Naming
- Files: `MB-###-slug.md` (e.g., `MB-012-hud-attach.md`).
- Increment `###` by the next available integer.

Format (Markdown + front matter)
Use `TEMPLATE.md` in this folder. Each brief is a single Markdown file with:
- Front matter: id, route, element, status, date, owner.
- Sections: Context, Friction, Target Feel, Acceptance (checkboxes), Notes, Assets.

Statuses
- `proposed` → `in_progress` → `verify` → `done` (or `blocked`/`rejected`).

Images
- Drop screenshots/GIFs under `docs/microbriefs/images/` and reference relatively:
  - `![HUD](/docs/microbriefs/images/MB-012-hud.png)`

Workflow
1) Create a new brief from the template (or use `scripts/new_microbrief.sh`).
2) Add 1–2 screenshots/GIFs if helpful.
3) I implement and return a short Verify checklist.
4) You check items, mark status to `done` (or add notes), and we archive decisions to `DECISIONS.md` if needed.

PR Linking
- Reference briefs in commit/PR messages: `Implements MB-012`.
