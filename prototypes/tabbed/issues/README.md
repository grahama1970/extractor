# Issues (Tabbed)

## Template

Copy this into a new `NNN_slug.md` file (use the “Issue: Scaffold (tabbed)” task for convenience):

```
# url:

## Issue
Location: __FILL_ME__
Task: __FILL_ME__

## Context
Short context and screenshot.

## Desired Behavior
What the user expects to see/do.

## Acceptance
- [ ] Failing smoke exists and passes after fix
- [ ] Verified on /classic
- [ ] Artifacts linked below

## Routes
- /classic

## Selectors (if known)
- __FILL_ME__

## Smokes to add
- scripts/smokes/issue_NNN.mjs

## Artifacts
- scripts/artifacts/issue_NNN_*.{log,png}

## Meta
- id: NNN
- created_at: YYYY-MM-DD

Last_smoke_at: (pending)
Last_suite_at: (pending)
Status: Open
```

## Workflow
- For single issues, create via “Issue: Scaffold (tabbed)” (auto-creates a smoke stub + VS Code task).
- For very simple issues, use “Issue: Quick (tabbed)” and supply route, selector, and optional contains text — it creates a minimal issue and a presence smoke automatically.
- For multi-topic drafts, drop a raw md into `prototypes/tabbed/issues/incoming/` and run “Issues: Promote incoming (tabbed)”. The promoter splits into atomic issues and smokes.
- Fill acceptance; keep it objective (DOM selectors, visibility, behavior).
- Agent implements smoke first (failing), then code, then artifacts back to the issue.
