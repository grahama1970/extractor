# GitHub Copilot: Automatic PR Reviews (Quick Start)

This page describes how to enable “Open a PR → Copilot reviews automatically” in this repository and how to port the setup to other projects.

## 1) Enable Copilot Code Review via Ruleset

UI path (recommended): Repository → Settings → Rules → New ruleset → Target: Branch → Add rule: “Copilot code review”. Enable:
- Automatically request Copilot review on pull requests
- Review new pushes
- (Optional) Review draft pull requests

CLI example (admin token required):

```
OWNER="<owner>"; REPO="<repo>"
read -r -d '' PAYLOAD <<'JSON'
{
  "name": "Copilot Auto Review",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~ALL"], "exclude": [] } },
  "rules": [
    {
      "type": "copilot_code_review",
      "parameters": {
        "review_on_push": true,
        "review_draft_pull_requests": false
      }
    }
  ]
}
JSON

gh api -X POST \
  -H 'Accept: application/vnd.github+json' \
  "/repos/$OWNER/$REPO/rulesets" \
  --input <(echo "$PAYLOAD")
```

Verify:

```
gh api "/repos/$OWNER/$REPO/rulesets?includes_parents=true" | jq
```

You should see a ruleset with:

```
{"type":"copilot_code_review","parameters":{"review_on_push":true}}
```

## 2) Provide Repo‑Scoped Instructions

Add `.github/copilot-instructions.md` on the default branch (template below). Copilot reads this file to understand your repo context and expectations.

Template:

```
# Copilot Code Review Instructions

## Context
- What this repo does and why it exists.

## Review Focus
- Your priorities (reliability, safety, determinism, performance, etc.).

## Key Paths (relative)
- List the most important files/directories to inspect.

## Constraints & Conventions
- Style rules, testing approach, architectural constraints.

## What To Deliver
- Clarifying answers, prioritized findings, unified diffs grouped by concern.

## Repro Commands
- How to build, test, and run demos.
```

## 3) Open a PR (Non‑Draft) and Let Copilot Review

- Use `gh pr create -t "Review: …" -F REVIEW_REQUEST.md` or rely solely on `.github/copilot-instructions.md`.
- Copilot posts review comments shortly after the PR is opened and on every push if enabled.

## Optional: CLI Automation

- Poll for review comments and store locally:

```
PR=$(gh pr view --json number -q .number)
gh pr view "$PR" --comments > local/copilot_pr_review.txt
```

- Add watch + desktop notifications (Linux `notify-send`, macOS `osascript`) as scripts in `scripts/` and wire into `Makefile` targets `copilot-review` and `copilot-watch`.

## Troubleshooting

- No comments? Check ruleset, draft status, and that the PR has diffs.
- Instructions ignored? Ensure `.github/copilot-instructions.md` is committed to the default branch.
- Private repos: confirm Copilot has access in org settings.
