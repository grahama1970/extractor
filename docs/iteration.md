Iteration Loop

1) Capture defect as issue using the template
2) Add a failing test first (contract/golden/smoke)
3) Make smallest fix in prompts/rules/adapter
4) Re-run gates locally; ensure green
5) Open PR linking issue and tests

Ratchet policy

- Golden updates require label `golden-approve` and reviewer note
- No quarantines on main; flakes get `xfail` + auto-issue and are prioritized in stabilize weeks

