# Extractor Review Request

You are reviewing the extractor project for operational readiness and compliance.

Repository:
https://github.com/grahama1970/extractor

Commit to review:
af31b5ffba78432d03fa9ff33c8ed0bed79a7589

Review goal:
Assess what is broken, missing, aspirational, outstanding, or out of compliance with:

- best-practices-python
- best-practices-skills
- the extractor skill contract

Known local evidence:

- extractor skill sanity passed smoke profile: 12/12 exercised checks passed.
- HTML extractor sanity was skipped because schematron3b is not installed.
- `pytest --collect-only -q` fails after collecting 788 tests.
- Collection failure path:
  - `tests/unit/test_llm_adapter_prompt_stats.py`
  - `src/llm_adapter/adapter.py`
  - `scillm.extras.json_utils`
  - `scillm.extras.__init__`
  - `scillm.extras.multi_agents`
  - missing `litellm.extras`
- `ruff check .` fails with 287 errors.
- Static best-practices scan over `src`, `scripts`, `tests`, `tools`, `scenarios`, and `prototypes` found:
  - 41 Python files over 800 LOC
  - 354 missing module docstrings
  - 209 banned imports: `argparse`, `logging`, `requests`, etc.
  - 25 fat `__init__.py` files
  - 30 async/sync subprocess conflicts
- extractor skill `SKILL.md` is missing required `complies:` metadata.
- extractor skill validator found `os.getenv` without dotenv loading in:
  - `extractor_skill/config.py`
  - `extractor_skill/pipeline_runner.py`
  - `extractor_skill/quality.py`

Important constraints:

- Do not treat smoke success as release readiness.
- Do not recommend broad cleanup or deletion without per-file dependency evidence.
- Separate IMPLEMENTED, BROKEN, MISSING, ASPIRATIONAL, and OUTSTANDING.
- Prioritize narrow, ticket-sized repairs.
- Focus on root causes and proof gates, not generic refactoring advice.

Please return:

1. A concise readiness verdict.
2. Top 10 findings ordered by severity, with file/path references.
3. Which extractor claims are implemented versus aspirational/not established.
4. Which best-practices-python and best-practices-skills rules are violated.
5. A prioritized next-step ticket list, each with:
   - target files
   - current state
   - requested outcome
   - required proof command
6. What should explicitly NOT be done next.
