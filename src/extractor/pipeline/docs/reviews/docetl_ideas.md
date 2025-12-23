Yes—there are several **DocETL ideas (and some code patterns)** that would likely improve `grahama1970/extractor` if you adapt them _selectively_ to extractor’s philosophy (deterministic stages, rich artifacts, CI-friendly, metadata-first). Below are the highest-leverage transfers, framed as **incremental improvements** rather than a rewrite.

### 1) “Directives” as a safe, composable way to evolve the pipeline

DocETL’s _reasoning optimizer directives_ (e.g., chaining, gleaning, change-model, doc-summarization) are essentially **named transformations** you can apply to a pipeline operation/config.

**Why useful to extractor**

- Extractor already has “stages” and “workers”; adding a **directive layer** would let you introduce improvements without hardcoding new stage variants.
- This fits your branch theme (`merge-metadata-prop`) because directives can be **metadata-driven**: “if metadata says X, apply directive Y”.

**Concrete extractor adaptation**

- Define directives like:
  - `gleaning_validate_section`: add N-round critique/repair loop _only_ for sections with low confidence / suspicious blocks.
  - `chain_table_repair`: replace one “AI enhance” call with 2–3 smaller calls (detect → repair → verify).
  - `change_model_for_tables`: route table-heavy sections to a stronger model, keep others cheap.
- Implement directives as pure transforms on a stage config + deterministic “plan” artifact, so CI can snapshot the plan even if execution is gated.

**Incremental path**

- Start with 2 directives that only affect **Stage 8 planning**, not earlier deterministic extraction.

---

### 2) Gleaning (multi-round validation) as a _targeted_ quality booster

DocETL’s “gleaning” pattern is a generalized “generate → validate → revise” loop.

**Why useful to extractor**

- Extractor already does suspicious detection and gold validation; gleaning can be inserted _between_ “agent enhancement” and “finalize” to reduce obvious errors when confidence is low.
- Key is to keep it **conditional**, not global (cost control, predictability).

**Concrete extractor adaptation**

- For each section:
  - If `surya_confidence < t` OR `suspicious_blocks` non-empty OR “table continues across pages” flag:
    - run gleaning with a strict rubric that references extractor metadata (expected headers, table schema, annotation hints).
- Store the gleaning transcript as structured metadata (round-by-round diffs, validation failures), which strengthens the “learning” stage later.

---

### 3) “Instantiate schemas” (structured LLM outputs) to harden Stage 8/repair steps

DocETL uses Pydantic schemas as the **contract** for what the LLM must output when configuring/applying a directive.

**Why useful to extractor**

- Extractor already talks about stable artifacts (`final_report.json` with schema validation). Extending schema discipline _upstream_ (into agent steps) reduces brittleness and makes downstream merging/metadata accumulation cleaner.

**Concrete extractor adaptation**

- For LLM-based enhancements, require schema like:
  - `SectionRepairPlan`: list of tool invocations to run, expected improvement, failure modes
  - `TableRepair`: normalized header map + row reconciliation steps + confidence estimate
  - `MergeMetadataPatch`: explicit JSON Patch / merge strategy outputs (very relevant to `merge-metadata-prop`)
- Validate immediately; if invalid, fallback deterministically (skip / mark as needs review).

---

### 4) Operation-level test harness: “directive tests” → “stage behavior tests”

DocETL’s directives include test cases (input config, expected behavior). That’s a very practical pattern.

**Why useful to extractor**

- Extractor has lots of moving parts; adding a lightweight **behavioral spec** for stage transforms would make iterative improvement safer than adding more end-to-end tests.

**Concrete extractor adaptation**

- Add “stage contract tests” for:
  - metadata merge semantics (idempotence, commutativity where intended, precedence rules)
  - section splitting/merging invariants
  - table normalization invariants
- Keep them offline and fast; run in CI for every change.

---

### 5) A “pipeline authoring UI” is _not_ the first thing—but a “plan diff viewer” might be

DocETL’s UI (DocWrangler) is a major differentiator, but adopting a full UI would be heavy.

**What _is_ useful for extractor**

- A minimal UI (or static HTML) to view:
  - per-section metadata timeline across stages
  - what changed between runs (diff of artifacts)
  - why a directive fired / why a repair was chosen

Extractor already has scenario artifacts and a report generator; you’re close. The DocETL lesson is: **tight iteration loops win**. For extractor, the best loop is “run pipeline → inspect diffs → adjust heuristics/prompts”.

---

### 6) Model routing / “change-model” as first-class config (cost + reliability)

DocETL’s “change model” directive formalizes model switching.

**Why useful to extractor**

- Extractor has heterogeneous tasks (OCR-ish cleanup vs complex table repair vs Lean4 formalization). Treating model routing as a first-class concern will reduce cost and improve consistency.

**Concrete extractor adaptation**

- Add a router that chooses model per section based on metadata:
  - tables/math/diagrams → stronger model
  - plain text cleanup → cheaper model
- Record routing decision into metadata for later learning.

---

### 7) “Doc summarization” directive maps to extractor’s long-context pressure points

DocETL’s doc summarization directive is about preprocessing before heavy operations.

**Why useful to extractor**

- If Stage 8 sometimes faces context limits, a deterministic summarization/pre-chunk step (or LLM summary under strict schema) can stabilize outputs.

**Concrete extractor adaptation**

- For very large sections, generate:
  - `section_synopsis`
  - `entities/glossary`
  - `table_index`
    and feed that to subsequent repair calls.

---

## What I would _not_ port (or only later)

- Full DocWrangler-style pipeline builder UI: high effort, unclear payoff vs extractor’s current pipeline-centric design.
- General “pipeline as YAML for everything” unless you have a strong need; extractor’s stage architecture is already opinionated and valuable.

---

## Suggested order of adoption (iterative, low-risk)

1. **Schema-first LLM outputs** for the most fragile steps (repair/merge/table).
2. Add **gleaning** only for sections flagged by suspicious/confidence metadata.
3. Add a small **directive system** that transforms “Stage 8 plan” (not the whole pipeline).
4. Add **directive/stage behavior tests** (especially metadata merge invariants).
5. Add **model routing** + record decisions into metadata.

If you want, I can propose a concrete design that matches extractor’s current structure (where directives live, what the Pydantic schemas look like, and how to wire it so stages 01–09 remain deterministic by default).

--- continued
Agreed: **extractor already has the key capability DocETL is gesturing at**—dynamic model switching—because SciLLM (LiteLLM-like) + Router gives you _runtime routing_ without custom wrappers.

So the useful “DocETL idea” here isn’t “dynamic model switching exists”; it’s **how to make model switching an explicit, testable, metadata-driven policy** rather than an ad-hoc choice sprinkled through code.

Here’s what’s worth taking (and how it fits your paved-path contract):

## What DocETL adds conceptually (that extractor can still benefit from)

### 1) Make “model switching” a _first-class directive/policy_

DocETL’s “change model” directive is basically: _modify the operation config to use a different model_.

In extractor terms, you already can switch models via SciLLM, but you can improve by making routing decisions:

- **explicit** (recorded in artifacts/metadata)
- **explainable** (why this model was chosen)
- **replayable** (planner output stable; executor optional)
- **testable** (unit tests for routing thresholds/conditions)

This is orthogonal to SciLLM’s Router and works perfectly with it.

### 2) Switch models based on _task/section metadata_ (better than document-type)

DocETL tends to switch per _operation_ (step) rather than per “PDF vs DOCX”.

Extractor can do better because you have rich signals:

- table-heavy, math-heavy, OCR confidence, suspicious blocks, cross-page merges needed, etc.

So: **route per section/per step based on metadata**, not “document type”.

### 3) Separate “deterministic plan” from “execution”

DocETL’s directives transform configs before execution. For extractor, this maps to:

- Stage 8 (planner) decides: which model(s), which steps, which validation loops
- Stage 8 (executor) calls SciLLM accordingly

This preserves your determinism goals.

## How to apply this while respecting your SciLLM paved-path contract

Your contract already says:

- DO use `scillm.Router` / `chutes_router_json` (no reimplementation)
- DO preflight with `sanity_preflight`
- DON’T do manual headers / raw HTTP
- DON’T implement your own fallback hacks

So the “DocETL-inspired” improvement becomes:

### Proposed extractor pattern

1. **Routing policy (pure function, deterministic)**:

- Input: `SectionContext` (metadata signals)
- Output: `RoutingDecision`:
  - primary model id
  - optional model_list for Router
  - timeouts / max_tokens
  - reason string(s)

2. **Preflight** (as you already require) for the chosen primary (and optionally alternates).

3. **Execution** uses only:

- `scillm.acompletion` / `parallel_acompletions`
- or `chutes_router_json` if you want Router-managed alternates

4. **Record routing decision into section metadata**:

- `metadata.llm.routing = {model, model_list?, reasons, preflight_summary_hash}`

That’s the concrete “DocETL” value: not the switching itself, but making it structured and auditable.

## Direct answer to the underlying question

- If you mean “is DocETL’s defining differentiator that it switches models by document type?” → **no**.
- If you mean “does DocETL include the idea/pattern of switching models dynamically to improve quality/cost?” → **yes**, via its _change-model_ optimization concept.
- For extractor, since SciLLM already enables this, the win is: **policy + artifacts + tests + metadata-driven routing**, not new switching mechanics.

If you tell me where in extractor you currently choose models (e.g., Stage 07/08 modules), I can sketch the exact `RoutingDecision` schema and the deterministic routing function that plugs into your existing SciLLM calls without violating any of the DevOps contract rules.

Scillm handles all the timeouts with a very robust tenacity feature
Copilot said: Right—SciLLM’s tenacity-backed retries/timeouts mean you don’t need
Right—SciLLM’s tenacity-backed retries/timeouts mean you don’t need DocETL-style “robustness logic” (and per your contract you shouldn’t reimplement it anyway).

So if timeouts/retries are already handled, the remaining high-value ideas to port from DocETL are about control, observability, and safe iteration, not resiliency:

1. Make model choice a recorded decision (even if it’s always the env default)
   Even with a single model (Kimi-K2) and SciLLM handling retries, you still benefit from stamping every LLM call (or at least every stage/section) with:

model
task_kind (what this call was for)
attempt_count / wall_time_s (SciLLM often exposes enough to infer this)
success/failure classification (timeout vs validation fail vs parse fail)
This turns “we use Kimi” from a hidden assumption into an analyzable signal for iterative improvement.

2. Port the DocETL idea of “operation-level policies” (not wrappers)
   DocETL’s “change-model” directive is basically: policy modifies config for an operation.

In extractor, the analogous improvement is:

Define task kinds (table repair, header merge, gleaning validate, Lean4 formalize…)
Define a policy map: task_kind → settings (model from env, max_tokens, response_format strict JSON, temperature)
Calls still go straight to SciLLM paved-path functions—no wrappers around HTTP—just a tiny “policy selection” step that returns kwargs.
This is compatible with your “no hacks / no wrappers” stance because you’re not wrapping SciLLM, you’re selecting parameters deterministically.

3. Prefer “validation/gleaning loops” over “fallback models” when calls/day are limited
   Since your cost constraint is calls/day (not tokens), switching models doesn’t save budget. If you want higher quality per call, the most DocETL-like lever is:

structured outputs + validation (and only re-try when validation fails)
That’s essentially the gleaning concept, but you can implement it in extractor as:

run one call with strict schema
if schema/validator fails, do one corrective call (bounded)
record both attempts in metadata
It’s “iterative improvement” without introducing model churn.

4. Deterministic “plan first” remains useful even with SciLLM retries
   Retries don’t address the big pipeline problem: why did we decide to call the LLM here at all?

A deterministic planner artifact (even minimal) helps you:

gate LLM calls only to sections flagged by suspicious metadata
measure “LLM calls avoided”
reproduce behavior changes across commits
SciLLM handles execution robustness; the planner handles pipeline discipline.

Practical next step (tiny, low risk)
If you want one concrete, immediately useful change that aligns with all this:

Introduce task_kind tagging for every SciLLM call (even if it’s just a string passed through your own call site metadata logging), and record {task_kind, model, section_id, success} into your existing per-stage JSON outputs.
No changes to retries, no new routing logic, no wrappers—just better signals so you can iteratively improve extractor with evidence.

If you point me to the primary module(s) that invoke SciLLM in the pipeline (paths), I can suggest exactly where to add the task_kind stamping with minimal code churn.
