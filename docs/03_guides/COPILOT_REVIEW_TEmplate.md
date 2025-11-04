# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**AGENT INSTRUCTIONS**
- Remember to git commit and push the current branch to the repo first
- DO NOT INCLUDE this instruction in  IN THE REVIEW REQUEST
- This template is the *prompt you send to Copilot*. Leave the `UNIFIED_DIFF` and `ANSWERS`
  blocks **empty**—Copilot must fill them in. Do not paste your own diff/output into those
  sections when making the request.



**Project**

* Fork/Repo: `<OWNER/REPO>` (the external github repo)
* Branch: `<BRANCH>`
* Path: `<GIT_SOURCE_WITH_BRANCH>`  *(e.g., `git@github.com:<OWNER>/<REPO>.git#<BRANCH>`)*

**Task**

* `<ONE-LINE SUMMARY OF THE CHANGE YOU WANT>`

**Context (brief, optional)**

* `<WHY this change is needed / what’s broken / desired outcome>`
* `<Any operational constraints or runtime modes>`

**Review Scope (relative paths)**

* Primary:

  * `<path/to/file1>`
  * `<path/to/file2>`
* Also check (if needed):

  * `<scripts/tests/docs/etc>`

**Objectives**

* `<Objective 1 (what to add/fix/harden)>`
* `<Objective 2>`
* `<Objective 3>`

**Constraints**

* **Unified diff only**, inline inside a single fenced block.
* **No PRs, no hosted links, no URLs, no extra commentary.**
* Include a **one-line commit subject** inside the patch.
* **Numeric hunk headers only** (`@@ -old,+new @@`), no symbolic headers.
* Patch must apply cleanly on branch `<BRANCH>`.
* Preserve plan→execute semantics; avoid destructive defaults.

**Acceptance (we will validate)**

* `<Acceptance criterion 1 (artifacts produced / command succeeds)>`
* `<Acceptance criterion 2 (content present / counts match)>`
* `<Acceptance criterion 3 (tests/smokes pass)>`

**Deliverables (STRICT — inline only; exactly these sections, in this order)**

> When sending the request, leave the fenced blocks empty; Copilot will replace the
> placeholders with its unified diff and answers.

1. **UNIFIED_DIFF:**

```diff
<entire unified diff here>
```

2. **ANSWERS:**

* `<Answer to Q1>`
* `<Answer to Q2>`
* `<Answer to Q3>`
* `…`

**Clarifying Questions (answer succinctly in the ANSWERS section; if unknown, reply `TBD` + minimal dependency needed)**

* Dependencies/data sources: Do we need to pin inputs/models/versions for repeatability?
* Schema drift: Should exporters/parsers tolerate missing/renamed columns with failing smokes?
* Safety: Are all mutating paths gated behind `--execute`? Any missing guards?
* Tests/smokes: Which deterministic smokes must pass (counts > 0, report count==pairs, strict formats)?
* Performance: Any batch sizes, rate limits, or timeouts/retries to honor?
* Observability: What summary lines should the CLI print on completion?

**Output Format (must match exactly; no extra text):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

* `<bullet answers in order of the clarifying questions>`

---

## Quick “Drop-In” Mini Version

**Request:** Produce a **single unified diff** (inline) for `<OWNER/REPO>#<BRANCH>` that achieves: `<brief objectives>`.
**Scope:** `<paths…>`
**Constraints:** No PRs/links; include a one-line commit subject; numeric hunk headers only; patch applies cleanly.
**Acceptance:** `<bullets>`

**Output (exact):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

* `<answers to: deps, schema drift, safety, tests, performance, observability>`

---

## Optional Toggles (copy/paste as needed)

* **Strict JSON Mode:** “All generated configs/snippets must be strict JSON: no comments, no trailing commas, no markdown/codefences inside the JSON.”
* **Flag-First DX:** “Commands and code must use explicit flag-first configuration; no hidden env defaults.”
* **Worker/Batching Defaults:** “Default ≤3 workers; batch size 10–15; retries with exponential backoff.”
* **Determinism:** “Seeded or deterministic outputs where feasible; produce minified JSON artifacts.”
* **MBOX Variant (if you ever switch modes):** Replace the UNIFIED_DIFF block with:
  **Output (exact):**
  `MBOX:` *(paste full git-format patch series; no code fences)*

---

### Placeholder Key

* `<OWNER/REPO>`: Repository identifier
* `<BRANCH>`: Target branch name
* `<GIT_SOURCE_WITH_BRANCH>`: Fetchable ref (SSH/HTTPS) with `#<BRANCH>` if helpful to your tools
* `<paths…>`: Narrow file list to focus Copilot
* `<brief objectives>` / `<Acceptance>`: What “done” looks like
