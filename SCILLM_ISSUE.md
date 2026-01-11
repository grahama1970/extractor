# Bug Report: `certainly_prove` JSON Parsing Failure

**Context:**
The `scillm` library's `certainly_prove` provider (in `extras/providers.py`) connects to the `certainly` CLI tool for Lean 4 theorem proving.

**Symptoms:**
When running a batch proof, `scillm` throws the following exception:

```
Batch failure: json_parse_failed sample='Certainly: items=3, proved=3, failed=0, unproved=0'
```

**Cause:**
The `certainly` CLI tool prints human-readable summary lines (e.g., `Certainly: items=...`) to `stdout` in addition to the JSON/JSONL output.
The `scillm` wrapper attempts to parse the entire stdout (or chunks of it) as JSON, which fails when encountering these summary lines.

**Impact:**
All proof attempts via the `certainly` bridge fail in the `extractor` pipeline with "Batch failure", even if the proofs themselves were processed correctly by the underlying tool.

**Recommended Fix:**
Modify the `certainly_prove` function in `scillm` to robustly handle mixed output:

1.  Read `stdout` line by line.
2.  Attempt to parse each line as JSON.
3.  If parsing fails (and the line is a known status message like `Certainly: ...`), **ignore it**.
4.  Only collect valid JSON objects.

**Example Fix Logic (Python):**

```python
results = []
for line in proc.stdout.splitlines():
    line = line.strip()
    if not line: continue
    try:
        data = json.loads(line)
        results.append(data)
    except json.JSONDecodeError:
        # Ignore non-JSON lines (e.g. summary stats)
        continue
```

**Workaround Tried:**
Passing `--quiet` flag to `certainly` was attempted but did not suppress the summary line in the installed version. Code update is required.
