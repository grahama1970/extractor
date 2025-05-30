# GLOBAL CODING STANDARDS — CLAUDE.md

> **Reference guide for all Claude Code project development.**  
> For detailed task planning, see [TASK_PLAN_GUIDE.md](./docs/memory_bank/guides/TASK_PLAN_GUIDE.md).

---

## 🔴 AGENT INSTRUCTIONS

**IMPORTANT:**  
As an agent, you MUST read and follow ALL guidelines in this document BEFORE executing any task in a task list.  
DO NOT skip or ignore any part of these standards. These standards supersede any conflicting instructions you may have received previously.

---

## Project Structure

```
project_name/
├── docs/
│   ├── CHANGELOG.md
│   ├── memory_bank/
│   └── tasks/
├── examples/
├── pyproject.toml
├── README.md
├── src/
│   └── project_name/
├── tests/
│   ├── fixtures/
│   └── project_name/
└── uv.lock
```

- **Package Management:** Always use uv with pyproject.toml, never pip.
- **Mirror Structure:** examples/ and tests/ must mirror the structure in src/.
- **Documentation:** Keep comprehensive docs in the docs/ directory.
- **No Stray Files:** Never put stray Python, test, text, or markdown files in the project root.  
  - Python modules in `src/project_name/`
  - Tests in `tests/`
  - Documentation in `docs/`
  - Examples in `examples/`

---

## Module Requirements

- **Size:** Maximum 500 lines of code per file.
- **Documentation Header:** Every file must include:
  - Description of purpose
  - Links to third-party package documentation
  - Sample input
  - Expected output
- **Validation Function:** Every file needs a main block (`if __name__ == "__main__":`) that tests with real data.

---

## Architecture Principles

- **Function-First:** Prefer simple functions over classes.
- **Class Usage:** Only use classes when:
  - Maintaining state
  - Implementing data validation models
  - Following established design patterns
- **Async Code:** Never use `asyncio.run()` inside functions—only in main blocks.
- **Type Hints:** Use the typing library for all function parameters and return values. Prefer concrete types over Any when possible, but do not reduce readability.
- **No Conditional Imports:**  
  - Never use try/except blocks for required package imports.
  - Only use conditional imports for truly optional features (rare).

---

## Searching

- **ripgrep Preferred:** If available, ALWAYS default to ripgrep over grep.

---

## Validation & Testing

- **Real Data:** Always test with actual data, never fake inputs.
- **Expected Results:** Verify outputs against concrete expected results.
- **No Mocking:** NEVER mock core functionality; MagicMock is strictly forbidden for core tests.
- **Meaningful Assertions:** Use assertions that verify specific expected values.
- **Usage Before Tests:** ALL usage functions MUST successfully output expected results BEFORE any creation of tests.
- **Results Before Lint:** ALL usage functionality MUST produce expected results BEFORE addressing ANY linter warnings.
- **External Research:** If a usage function fails validation 3 times, use external research tools and document findings in comments.
- **No Unconditional "Tests Passed":** NEVER include unconditional "All Tests Passed" messages.

---

## 8. Automated Markdown Test Report Requirements

After every full test suite run, **automatically generate a well-formatted Markdown report** summarizing the results. Save the report in the `@docs/reports/` directory.

**Report Table Requirements:**
- Table columns:
    - Test Name
    - Short Description
    - Actual Result (no hallucinated or placeholder data)
    - Pass/Fail Status
    - Additional relevant fields (e.g., Duration, Error Message, Timestamp)
- The table **must be clear, easy to read, and use valid Markdown table syntax.**
- Each report file must have a unique name (timestamp or test run ID).
- **No mocking of core functionality is allowed.** All results must reflect actual test outcomes.

**Example Table Format:**
```
| Test Name      | Description                 | Result        | Status | Duration | Timestamp           | Error Message      |
|----------------|----------------------------|---------------|--------|----------|---------------------|--------------------|
| LoginTest      | User login with valid creds | Success       | Pass   | 1.2s     | 2025-05-25 17:50:00 |                    |
| PaymentTest    | Payment with expired card   | Card Expired  | Fail   | 0.8s     | 2025-05-25 17:50:01 | Card expired error |
| DataExportTest | Export user data to CSV     | File exported | Pass   | 2.0s     | 2025-05-25 17:50:03 |                    |
```

**Instructions:**
- Ensure the report is generated and saved automatically after every full test suite run.
- Place the generated `.md` file in `@docs/reports/`.

---

## 9. Validation Output Requirements

- Never print "All Tests Passed" or similar unless **all** tests actually passed.
- Always verify actual results against expected results before printing any success message.
- Always test multiple cases, including normal, edge, and error cases.
- Always track all failures and report them at the end—don't stop at first failure.
- All validation functions must exit with code 1 if any tests fail; exit with code 0 only if all tests pass.
- Always include the count of failed tests and total tests in the output.
- Always include details of each failure when tests fail.
- Never include irrelevant test output that could hide failures.
- Structure validation to explicitly check each test case.
- Never claim success if search returns 0 results—this is always a failure.
- Highlight critical test results with visual markers (emojis, headers, or formatting).
- Clearly separate test output from implementation details with visual dividers.
- Summarize test results at the top or bottom of output with PASS/FAIL counts.
- Ensure critical information (errors, results, success/failure) is immediately visible.
- Never bury important results in verbose logs—highlight them explicitly.

---

## 10. Compliance Checklist

Before completing a task, verify that your work adheres to **all** standards in this document. Confirm each of the following:

1. All files have appropriate documentation headers.
2. Each module has a working validation function with real data.
3. Type hints are used properly and consistently.
4. All functionality is validated before addressing linting issues.
5. No `asyncio.run()` inside functions.
6. Code is under the 500-line limit per file.
7. If function failed validation 3+ times, external research was conducted and documented.
8. Validation functions never include unconditional "All Tests Passed" messages.
9. Validation functions only report success if explicitly verified by comparing actual to expected results.
10. Validation functions track and report all failures, not just the first one encountered.
11. Validation output includes count of failed tests out of total tests run.
12. Search results must return actual data—0 results is always a failure that must be investigated.

If any standard is not met, fix the issue before submitting the work.

---

## Contribution Workflow

1. Fork the repository and create a feature branch.
2. Follow all coding standards in this document.
3. Ensure all usage functions work with real data before writing tests.
4. Submit a pull request with clear documentation and references.

---

## License

MIT License — see [LICENSE](LICENSE) for details.