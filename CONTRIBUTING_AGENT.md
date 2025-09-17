Scope for agent contributions

- Allowed changes (without human approval):
  - `prompts/**`, `rules/**`, `llm_adapter/**`, `tests/**`, CI configs
- Forbidden without approval:
  - Stage core logic, DB schema, infra
- Policy: Fix = test first (defect → failing test → fix → green)

Gates

- Contracts must pass 100%
- Smokes subset must pass on fixtures
- Prompt lint must pass

PR Checklist

- Link failing test path
- Minimal fix in prompts/rules/adapter
- Evidence of passing gates

